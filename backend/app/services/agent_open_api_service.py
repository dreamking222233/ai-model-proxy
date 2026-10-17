"""Agent open-API recharge idempotency and bounded synchronous payment wait."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import BoundedSemaphore

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.database import SessionLocal
from app.models.agent import AgentOpenApiIdempotency
from app.models.log import UserBalance
from app.models.payment import PaymentRechargeOrder
from app.models.user import SysUser
from app.services.agent_open_api_key_service import AgentOpenApiPrincipal
from app.services.agent_service import AgentService
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class AgentOpenApiService:
    """Open API operations whose authorization is bound to an agent key."""

    IDEMPOTENCY_RETENTION = timedelta(days=30)
    IDEMPOTENCY_LEASE = timedelta(minutes=10)
    WAIT_SECONDS = 120
    WAIT_CLOSE_BUDGET_SECONDS = 18
    WAIT_CLOSE_TRIGGER_SECONDS = 36
    WAIT_NETWORK_TIMEOUT_SECONDS = 8
    WAIT_PAID_BALANCE_BUDGET_SECONDS = 4
    WAIT_RESPONSE_BUDGET_SECONDS = 0.5
    WAIT_POLL_INTERVAL_SECONDS = 2
    MAX_CONCURRENT_WAITERS = 32
    MAX_CONCURRENT_PROVIDER_CALLS = 16
    MAX_CONCURRENT_RATE_LIMIT_CALLS = 8

    _wait_slots = BoundedSemaphore(MAX_CONCURRENT_WAITERS)
    _provider_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_PROVIDER_CALLS, thread_name_prefix="agent-open-payment")
    _provider_slots = BoundedSemaphore(MAX_CONCURRENT_PROVIDER_CALLS)
    # AuthRateLimitService uses synchronous Redis calls. Keep them away from
    # the async event loop and from the payment worker pool so a slow Redis
    # connection cannot block payment polling or exhaust its capacity.
    _rate_limit_pool = ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_RATE_LIMIT_CALLS,
        thread_name_prefix="agent-open-rate-limit",
    )
    _rate_limit_slots = BoundedSemaphore(MAX_CONCURRENT_RATE_LIMIT_CALLS)
    _last_idempotency_cleanup_at = 0.0

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _iso(value) -> str | None:
        return value.isoformat() if value else None

    @classmethod
    def _validate_idempotency_key(cls, value: str | None) -> str:
        key = str(value or "")
        if not 8 <= len(key) <= 128 or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise ServiceException(400, "Idempotency-Key 必须是 8–128 位可见 ASCII 字符", "IDEMPOTENCY_KEY_INVALID")
        return key

    @classmethod
    def _check_rate_code(cls, code: str, settlement_rate: Decimal, custom_enabled: bool) -> Decimal:
        rate = PaymentService.OPEN_API_RECHARGE_RATES.get(str(code or "").lower())
        if rate is None:
            raise ServiceException(400, "充值比例代码无效", "RECHARGE_RATE_CODE_INVALID")
        if code != "e" and not custom_enabled:
            raise ServiceException(403, "当前代理未开启自定义充值比例", "AGENT_CUSTOM_RECHARGE_RATE_DISABLED")
        if rate > settlement_rate:
            raise ServiceException(400, "充值比例不能高于代理结算比例", "AGENT_CUSTOM_RECHARGE_RATE_EXCEEDS_SETTLEMENT")
        return rate

    @classmethod
    def create_recharge_order(
        cls,
        *,
        principal: AgentOpenApiPrincipal,
        user_id: int,
        amount_cny,
        payment_channel: str,
        recharge_rate_code: str,
        idempotency_key: str,
        request_ip: str,
    ) -> dict:
        key = cls._validate_idempotency_key(idempotency_key)
        channel = PaymentService._normalize_payment_channel(payment_channel)
        amount = PaymentService._normalize_cny(amount_cny)
        if amount < Decimal("1.00") or amount > Decimal("10000.00"):
            raise ServiceException(400, "充值金额范围为 1.00–10000.00 元", "INVALID_RECHARGE_AMOUNT")
        rate_code = str(recharge_rate_code or "e").strip().lower()
        AuthRateLimitService.check(
            AuthRateLimitService.build_key(f"agent-open-recharge-key-{principal.key_id}", request_ip, str(user_id)),
            limit=6,
            window_seconds=60,
        )

        db = SessionLocal()
        try:
            user = db.query(SysUser).filter(SysUser.id == int(user_id), SysUser.agent_id == int(principal.agent_id), SysUser.role == "user", SysUser.status == 1).first()
            if user is None:
                raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
            site_context = AgentService.get_open_api_site_context(db, principal.agent_id)
            policy = AgentService.resolve_user_recharge_policy(db, user)
            business_request = {
                "agent_id": int(principal.agent_id),
                "key_id": int(principal.key_id),
                "user_id": int(user_id),
                "amount_cny": str(amount.quantize(PaymentService.CNY_SCALE)),
                "payment_channel": channel,
                "recharge_rate_code": rate_code,
            }
            fingerprint_json = json.dumps(business_request, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            fingerprint = cls._sha256(fingerprint_json)
            idem_hash = cls._sha256(key)
            now = datetime.utcnow()
            # Completed idempotency reservations are retained for 30 days.
            # Throttle global pruning so each request does not scan the table.
            monotonic_now = time.monotonic()
            if monotonic_now - cls._last_idempotency_cleanup_at >= 300:
                db.query(AgentOpenApiIdempotency).filter(
                    AgentOpenApiIdempotency.completed_at.isnot(None),
                    AgentOpenApiIdempotency.completed_at < now - cls.IDEMPOTENCY_RETENTION,
                ).delete(synchronize_session=False)
                db.commit()
                cls._last_idempotency_cleanup_at = monotonic_now
            reservation = (
                db.query(AgentOpenApiIdempotency)
                .filter(
                    AgentOpenApiIdempotency.key_id == int(principal.key_id),
                    AgentOpenApiIdempotency.user_id == int(user_id),
                    AgentOpenApiIdempotency.idempotency_hash == idem_hash,
                )
                .with_for_update()
                .first()
            )
            if reservation and reservation.completed_at and reservation.completed_at < now - cls.IDEMPOTENCY_RETENTION:
                db.delete(reservation)
                db.commit()
                reservation = None

            if reservation:
                if reservation.request_fingerprint != fingerprint:
                    raise ServiceException(409, "同一 Idempotency-Key 已用于不同请求参数", "IDEMPOTENCY_CONFLICT")
                if reservation.status == "ready":
                    order = db.query(PaymentRechargeOrder).filter(
                        PaymentRechargeOrder.order_no == reservation.order_no,
                        PaymentRechargeOrder.user_id == int(user_id),
                        PaymentRechargeOrder.agent_id == int(principal.agent_id),
                    ).first()
                    if order is None:
                        raise ServiceException(503, "幂等订单状态暂不可恢复", "IDEMPOTENCY_ORDER_MISSING")
                    # The order snapshot remains authoritative when agent rate configuration changes.
                    db.expunge(order)
                    db.expunge(reservation)
                    replay = {"reservation": reservation, "order": order, "user": user, "site_context": site_context}
                    db.close()
                    return cls._replay_reservation(replay)
                if reservation.status in {"reserved", "provisioning"} and reservation.lease_until > now:
                    retry_after = max(
                        1,
                        min(
                            int((reservation.lease_until - now).total_seconds() + 0.999),
                            int(cls.IDEMPOTENCY_LEASE.total_seconds()),
                        ),
                    )
                    raise ServiceException(
                        409,
                        "相同充值请求仍在处理中，请稍后使用原 Idempotency-Key 重试",
                        "IDEMPOTENCY_IN_PROGRESS",
                        headers={"Retry-After": str(retry_after)},
                    )
                # A stale lease is recovered using the original amount, ratio,
                # settlement snapshot and order number.
                try:
                    saved = json.loads(reservation.request_json)
                except (TypeError, ValueError) as exc:
                    raise ServiceException(500, "幂等请求快照无效", "IDEMPOTENCY_SNAPSHOT_INVALID") from exc
                if reservation.status == "retryable_failed":
                    old_order = db.query(PaymentRechargeOrder.id).filter(PaymentRechargeOrder.order_no == reservation.order_no).first()
                    if old_order:
                        raise ServiceException(409, "该充值请求存在待恢复订单，请稍后重试", "IDEMPOTENCY_IN_PROGRESS")
                    reservation.order_no = PaymentService._generate_order_no(channel)
                reservation.status = "provisioning"
                reservation.lease_until = now + cls.IDEMPOTENCY_LEASE
                reservation.attempts = int(reservation.attempts or 0) + 1
                reservation.completed_at = None
                db.commit()
                db.refresh(reservation)
                db.expunge(reservation)
                saved_request = saved
                order_no = str(reservation.order_no)
            else:
                if not policy.online_recharge_enabled:
                    raise ServiceException(403, "当前代理未开启在线充值", "AGENT_ONLINE_RECHARGE_DISABLED")
                if not AgentService.normalize_host(site_context.host):
                    raise ServiceException(500, "代理未配置前台域名，无法创建支付回跳地址", "PAYMENT_RETURN_HOST_MISSING")
                user_rate = cls._check_rate_code(rate_code, policy.balance_agent_settlement_rate, policy.custom_recharge_rate_enabled)
                settlement_rate = Decimal(str(policy.balance_agent_settlement_rate))
                request_document = {
                    **business_request,
                    "user_recharge_rate": str(user_rate),
                    "agent_settlement_rate": str(settlement_rate),
                }
                canonical = json.dumps(request_document, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                order_no = PaymentService._generate_order_no(channel)
                reservation = AgentOpenApiIdempotency(
                    agent_id=int(principal.agent_id),
                    key_id=int(principal.key_id),
                    user_id=int(user_id),
                    idempotency_hash=idem_hash,
                    request_fingerprint=fingerprint,
                    request_json=canonical,
                    user_recharge_rate_code=rate_code,
                    user_recharge_rate=user_rate,
                    agent_settlement_rate=settlement_rate,
                    order_no=order_no,
                    status="provisioning",
                    lease_until=now + cls.IDEMPOTENCY_LEASE,
                    attempts=1,
                )
                db.add(reservation)
                try:
                    db.commit()
                except IntegrityError as exc:
                    db.rollback()
                    winner = db.query(AgentOpenApiIdempotency).filter(
                        AgentOpenApiIdempotency.key_id == int(principal.key_id),
                        AgentOpenApiIdempotency.user_id == int(user_id),
                        AgentOpenApiIdempotency.idempotency_hash == idem_hash,
                    ).first()
                    retry_after = 1
                    if winner and winner.lease_until:
                        seconds_left = (winner.lease_until - datetime.utcnow()).total_seconds()
                        if seconds_left > 0:
                            retry_after = min(int(seconds_left + 0.999), int(cls.IDEMPOTENCY_LEASE.total_seconds()))
                    raise ServiceException(
                        409,
                        "相同充值请求正在并发创建，请使用原 Idempotency-Key 重试",
                        "IDEMPOTENCY_IN_PROGRESS",
                        headers={"Retry-After": str(max(1, retry_after))},
                    ) from exc
                db.refresh(reservation)
                db.expunge(reservation)
                saved_request = request_document
            # Use immutable reservation values after releasing the transaction.
            user_id_snapshot = int(user.id)
            db.expunge(user)
            db.close()
        except Exception:
            db.close()
            raise

        try:
            payload = cls._provision_order(
                principal=principal,
                user_id=user_id_snapshot,
                order_no=order_no,
                request_document=saved_request,
                idempotency_hash=idem_hash,
                existing_order=None,
            )
        except Exception:
            cls._mark_reservation_failure(principal.key_id, user_id, idem_hash, order_no)
            raise
        cls._mark_reservation_ready(principal.key_id, user_id, idem_hash, order_no)
        return payload

    @classmethod
    def _mark_reservation_ready(cls, key_id: int, user_id: int, idem_hash: str, order_no: str) -> None:
        db = SessionLocal()
        try:
            row = db.query(AgentOpenApiIdempotency).filter(
                AgentOpenApiIdempotency.key_id == key_id,
                AgentOpenApiIdempotency.user_id == user_id,
                AgentOpenApiIdempotency.idempotency_hash == idem_hash,
                AgentOpenApiIdempotency.order_no == order_no,
            ).with_for_update().first()
            if row:
                row.status = "ready"
                row.completed_at = datetime.utcnow()
                row.lease_until = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    @classmethod
    def _mark_reservation_failure(cls, key_id: int, user_id: int, idem_hash: str, order_no: str) -> None:
        db = SessionLocal()
        try:
            row = db.query(AgentOpenApiIdempotency).filter(
                AgentOpenApiIdempotency.key_id == key_id,
                AgentOpenApiIdempotency.user_id == user_id,
                AgentOpenApiIdempotency.idempotency_hash == idem_hash,
                AgentOpenApiIdempotency.order_no == order_no,
            ).with_for_update().first()
            if row:
                has_order = db.query(PaymentRechargeOrder.id).filter(PaymentRechargeOrder.order_no == order_no).first()
                if not has_order:
                    row.status = "retryable_failed"
                    row.lease_until = datetime.utcnow()
                    row.completed_at = datetime.utcnow()
                    db.commit()
        finally:
            db.close()

    @classmethod
    def _provision_order(
        cls,
        *,
        principal,
        user_id: int,
        order_no: str,
        request_document: dict,
        idempotency_hash: str | None = None,
        existing_order=None,
    ) -> dict:
        """Persist the local snapshot first, then create/recover provider credentials."""
        db = SessionLocal()
        try:
            user = db.query(SysUser).filter(
                SysUser.id == user_id,
                SysUser.agent_id == int(principal.agent_id),
                SysUser.role == "user",
                SysUser.status == 1,
            ).first()
            if user is None:
                raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
            order = db.query(PaymentRechargeOrder).filter(
                PaymentRechargeOrder.order_no == order_no,
                PaymentRechargeOrder.user_id == user_id,
                PaymentRechargeOrder.agent_id == int(principal.agent_id),
            ).first()
            if order is not None:
                db.expunge(order)
                db.close()
                recovered = cls._recover_existing_order(order, allow_reserved_order_replacement=bool(idempotency_hash))
                if recovered.get("_replace_reserved_order"):
                    replacement = cls._replace_reserved_order_no(
                        principal.key_id,
                        user_id,
                        idempotency_hash,
                        order.order_no,
                        provider_closed_confirmed=True,
                    )
                    return cls._provision_order(
                        principal=principal,
                        user_id=user_id,
                        order_no=replacement,
                        request_document=request_document,
                        idempotency_hash=idempotency_hash,
                    )
                return recovered
            site_context = AgentService.get_open_api_site_context(db, principal.agent_id, require_recharge=True)
            response = PaymentService.create_recharge_order(
                db,
                user=user,
                amount_cny=Decimal(request_document["amount_cny"]),
                payment_channel=request_document["payment_channel"],
                recharge_type="balance",
                site_context=site_context,
                user_recharge_rate_override=Decimal(request_document["user_recharge_rate"]),
                user_recharge_rate_code=request_document["recharge_rate_code"],
                agent_settlement_rate_override=Decimal(request_document["agent_settlement_rate"]),
                trusted_rate_snapshot=True,
                reserved_order_no=order_no,
                defer_external_request=True,
            )
            return cls._to_open_order_payload(response["order"], response)
        finally:
            # create_recharge_order(defer_external_request=True) already closes
            # this Session; Session.close() is safe to call again.
            db.close()

    @classmethod
    def _recover_existing_order(
        cls,
        order: PaymentRechargeOrder,
        *,
        allow_reserved_order_replacement: bool = False,
    ) -> dict:
        if order.status == "closed" and order.payment_channel == "wechat" and allow_reserved_order_replacement and not order.wechat_code_url:
            upstream = PaymentService.query_wechat_order(order.order_no)
            trade_state = str(upstream.get("trade_state") or "").strip().upper()
            if trade_state in PaymentService.WECHAT_SUCCESS_STATES:
                db = SessionLocal()
                try:
                    result = PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
                    return cls._to_open_order_payload(result, {})
                finally:
                    db.close()
            if trade_state in PaymentService.WECHAT_CLOSED_STATES or trade_state == "NOT_FOUND":
                return {"_replace_reserved_order": True}
            if trade_state not in PaymentService.WECHAT_PENDING_STATES:
                raise ServiceException(503, "微信订单状态暂不可恢复，请稍后使用原 Idempotency-Key 重试", "WECHAT_ORDER_RECOVERY_UNCERTAIN")

            # A local closed state alone is insufficient: a provider query may
            # still report a chargeable order. Close it, then query again and
            # replace the reservation only after the provider confirms safety.
            try:
                PaymentService.close_wechat_order(order.order_no)
            except Exception:
                logger.info("WeChat close was not acknowledged for order %s; checking provider state", order.order_no, exc_info=True)
            try:
                final_state = PaymentService.query_wechat_order(order.order_no)
            except Exception as exc:
                raise ServiceException(503, "微信订单关单结果未确认，请稍后使用原 Idempotency-Key 重试", "WECHAT_CLOSE_UNCERTAIN") from exc
            final_trade_state = str(final_state.get("trade_state") or "").strip().upper()
            if final_trade_state in PaymentService.WECHAT_SUCCESS_STATES:
                db = SessionLocal()
                try:
                    result = PaymentService._apply_paid_order(db, order.order_no, final_state, source="query")
                    return cls._to_open_order_payload(result, {})
                finally:
                    db.close()
            if final_trade_state in PaymentService.WECHAT_CLOSED_STATES or final_trade_state == "NOT_FOUND":
                return {"_replace_reserved_order": True}
            raise ServiceException(503, "微信订单关单结果未确认，请稍后使用原 Idempotency-Key 重试", "WECHAT_CLOSE_UNCERTAIN")

        if order.status != "pending":
            return cls._to_open_order_payload(PaymentService.serialize_order(order), {})
        if order.payment_channel == "alipay":
            upstream = PaymentService.query_alipay_order(order.order_no, timeout=PaymentService.ALIPAY_HTTP_TIMEOUT_SECONDS)
            trade_status = str(upstream.get("trade_status") or "").strip()
            if trade_status in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES:
                db = SessionLocal()
                try:
                    result = PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
                    return cls._to_open_order_payload(result, {})
                finally:
                    db.close()
            if trade_status == "TRADE_CLOSED":
                db = SessionLocal()
                try:
                    result = PaymentService._mark_order_terminal(db, order.order_no, "closed", trade_status, upstream, "query")
                    return cls._to_open_order_payload(result, {})
                finally:
                    db.close()
            pay_url = PaymentService.build_alipay_page_pay_url(order, order.return_url_snapshot or "")
            return cls._to_open_order_payload(PaymentService.serialize_order(order), {"pay_url": pay_url})
        # Query before replaying a saved credential so a remote payment that
        # raced its notification is reflected in the local order state.
        upstream = PaymentService.query_wechat_order(order.order_no)
        trade_state = str(upstream.get("trade_state") or "").strip().upper()
        if trade_state in PaymentService.WECHAT_SUCCESS_STATES:
            db = SessionLocal()
            try:
                result = PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
                return cls._to_open_order_payload(result, {})
            finally:
                db.close()
        if trade_state in PaymentService.WECHAT_CLOSED_STATES:
            db = SessionLocal()
            try:
                result = PaymentService._mark_order_terminal(db, order.order_no, "closed", trade_state, upstream, "query")
                if allow_reserved_order_replacement and not order.wechat_code_url:
                    return {"_replace_reserved_order": True}
                return cls._to_open_order_payload(result, {})
            finally:
                db.close()
        if trade_state == "NOT_FOUND":
            # No remote chargeable order exists, so creation with the reserved
            # order number is safe.
            credential = PaymentService.create_wechat_native_order(None, order)
            cls._save_wechat_code_url(order.order_no, credential.get("wechat_code_url"))
            return cls._to_open_order_payload(PaymentService.serialize_order(order), credential)
        if trade_state in PaymentService.WECHAT_PENDING_STATES:
            if order.wechat_code_url:
                return cls._to_open_order_payload(
                    PaymentService.serialize_order(order),
                    {"wechat_code_url": order.wechat_code_url},
                )
            recovery_url = str(upstream.get("code_url") or "").strip()
            if recovery_url:
                cls._save_wechat_code_url(order.order_no, recovery_url)
                order.wechat_code_url = recovery_url
                return cls._to_open_order_payload(PaymentService.serialize_order(order), {"wechat_code_url": recovery_url})
            try:
                closed = PaymentService.close_wechat_order(order.order_no)
            except Exception:
                # The close response may be lost after the provider applied
                # it. Resolve the state with a fresh query before deciding.
                logger.info("WeChat close was not acknowledged for order %s; checking provider state", order.order_no, exc_info=True)
            try:
                final_state = PaymentService.query_wechat_order(order.order_no)
            except Exception as exc:
                raise ServiceException(503, "微信订单二维码恢复失败，关单结果未确认，请稍后重试", "WECHAT_CLOSE_UNCERTAIN") from exc
            final_trade_state = str(final_state.get("trade_state") or "").strip().upper()
            if final_trade_state in PaymentService.WECHAT_SUCCESS_STATES:
                db = SessionLocal()
                try:
                    result = PaymentService._apply_paid_order(db, order.order_no, final_state, source="query")
                    return cls._to_open_order_payload(result, {})
                finally:
                    db.close()
            if final_trade_state not in {*PaymentService.WECHAT_CLOSED_STATES, "NOT_FOUND"}:
                raise ServiceException(503, "微信订单关单结果暂不可确认，请稍后使用原 Idempotency-Key 重试", "WECHAT_CLOSE_UNCERTAIN")
            db = SessionLocal()
            try:
                if final_trade_state != "NOT_FOUND":
                    result = PaymentService._mark_order_terminal(db, order.order_no, "closed", final_trade_state or "CLOSED", final_state, "query")
                else:
                    result = PaymentService.serialize_order(order)
                if allow_reserved_order_replacement:
                    return {"_replace_reserved_order": True}
                return cls._to_open_order_payload(result, {})
            finally:
                db.close()
        raise ServiceException(503, "微信订单状态暂不可恢复，请稍后使用原 Idempotency-Key 重试", "WECHAT_ORDER_RECOVERY_UNCERTAIN")

    @classmethod
    def _replace_reserved_order_no(
        cls,
        key_id: int,
        user_id: int,
        idempotency_hash: str,
        current_order_no: str,
        *,
        provider_closed_confirmed: bool,
    ) -> str:
        """Move a provisioning reservation only after its old WeChat order is confirmed closed."""
        if not provider_closed_confirmed:
            raise ServiceException(409, "微信旧订单尚未确认关闭，不能替换预留订单号", "WECHAT_CLOSE_UNCERTAIN")
        db = SessionLocal()
        try:
            reservation = (
                db.query(AgentOpenApiIdempotency)
                .filter(
                    AgentOpenApiIdempotency.key_id == int(key_id),
                    AgentOpenApiIdempotency.user_id == int(user_id),
                    AgentOpenApiIdempotency.idempotency_hash == idempotency_hash,
                )
                .with_for_update()
                .first()
            )
            if reservation is None or reservation.order_no != current_order_no:
                raise ServiceException(409, "充值订单恢复状态已变化，请使用原 Idempotency-Key 重试", "IDEMPOTENCY_IN_PROGRESS")
            if reservation.status not in {"reserved", "provisioning"}:
                raise ServiceException(409, "充值订单已完成恢复，请使用原 Idempotency-Key 重试", "IDEMPOTENCY_IN_PROGRESS")

            for _ in range(3):
                replacement = PaymentService._generate_order_no("wechat")
                exists = db.query(PaymentRechargeOrder.id).filter(PaymentRechargeOrder.order_no == replacement).first()
                reservation_exists = db.query(AgentOpenApiIdempotency.id).filter(
                    AgentOpenApiIdempotency.order_no == replacement,
                ).first()
                if not exists and not reservation_exists:
                    break
            else:  # pragma: no cover - random order collisions are extraordinarily unlikely
                raise ServiceException(503, "暂时无法分配新的充值订单号", "RECHARGE_ORDER_NO_UNAVAILABLE")

            reservation.order_no = replacement
            reservation.lease_until = datetime.utcnow() + cls.IDEMPOTENCY_LEASE
            reservation.attempts = int(reservation.attempts or 0) + 1
            reservation.completed_at = None
            db.commit()
            return replacement
        finally:
            db.close()

    @classmethod
    def _save_wechat_code_url(cls, order_no: str, code_url: str | None) -> None:
        if not code_url:
            raise ServiceException(503, "微信支付未返回二维码信息", "WECHAT_PAY_CODE_URL_MISSING")
        db = SessionLocal()
        try:
            row = db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.order_no == order_no).with_for_update().first()
            if row and row.status == "pending":
                row.wechat_code_url = code_url
                db.commit()
        finally:
            db.close()

    @classmethod
    def _to_open_order_payload(cls, order_data: dict, payment: dict) -> dict:
        status = str(order_data.get("status") or "pending")
        result = {
            "order_no": order_data.get("order_no"),
            "status": status,
            "amount_cny": order_data.get("amount_cny"),
            "credited_usd": order_data.get("credited_usd"),
            "user_recharge_rate": order_data.get("user_recharge_rate"),
            "user_recharge_rate_code": order_data.get("user_recharge_rate_code"),
            "expired_at": order_data.get("expired_at"),
            "payment_channel": order_data.get("payment_channel"),
        }
        if status == "pending":
            if payment.get("pay_url"):
                result["pay_url"] = payment["pay_url"]
            code_url = payment.get("wechat_code_url") or payment.get("code_url")
            if code_url:
                result["wechat_code_url"] = code_url
        elif status == "paid":
            result["paid_at"] = order_data.get("paid_at")
        else:
            result["retry_with_new_idempotency_key"] = True
        return result

    @classmethod
    def _replay_reservation(cls, replay: dict) -> dict:
        order = replay["order"]
        return cls._recover_existing_order(order)

    @classmethod
    async def _run_provider_call(cls, function, *args, wait_timeout: float | None = None):
        if not cls._provider_slots.acquire(blocking=False):
            raise ServiceException(429, "支付查单并发已满，请稍后重试", "PAYMENT_WAIT_CAPACITY_REACHED")
        loop = asyncio.get_running_loop()
        future = cls._provider_pool.submit(function, *args)
        future.add_done_callback(lambda _: cls._provider_slots.release())
        wrapped = asyncio.wrap_future(future, loop=loop)
        if wait_timeout is None:
            return await wrapped
        return await asyncio.wait_for(asyncio.shield(wrapped), timeout=wait_timeout)

    @classmethod
    async def _check_wait_rate_limit(cls, key: str, *, deadline: float) -> None:
        """Run the synchronous Redis/memory limiter without blocking asyncio."""
        remaining = deadline - time.monotonic()
        if remaining <= cls.WAIT_RESPONSE_BUDGET_SECONDS:
            return
        if not cls._rate_limit_slots.acquire(blocking=False):
            raise ServiceException(429, "支付等待限流并发已满，请稍后重试", "PAYMENT_WAIT_CAPACITY_REACHED")
        loop = asyncio.get_running_loop()
        future = cls._rate_limit_pool.submit(
            AuthRateLimitService.check,
            key,
            limit=12,
            window_seconds=60,
        )
        future.add_done_callback(lambda _: cls._rate_limit_slots.release())
        wrapped = asyncio.wrap_future(future, loop=loop)
        # RedisClient's socket timeout is bounded, but keep the await bounded
        # by the request deadline as well. The worker is allowed to finish in
        # the background after a timeout and releases its slot on completion.
        timeout = min(5.0, max(0.0, remaining - cls.WAIT_RESPONSE_BUDGET_SECONDS))
        try:
            await asyncio.wait_for(asyncio.shield(wrapped), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise ServiceException(503, "限流服务暂不可用，请稍后重试", "RATE_LIMIT_SERVICE_TIMEOUT") from exc

    @staticmethod
    def _read_wait_order(order_no: str, user_id: int, agent_id: int) -> dict | None:
        db = SessionLocal()
        try:
            order = db.query(PaymentRechargeOrder).filter(
                PaymentRechargeOrder.order_no == order_no,
                PaymentRechargeOrder.user_id == int(user_id),
                PaymentRechargeOrder.agent_id == int(agent_id),
                PaymentRechargeOrder.recharge_type == "balance",
            ).first()
            if not order:
                return None
            result = PaymentService.serialize_order(order)
            result["wechat_code_url"] = order.wechat_code_url
            return result
        finally:
            db.close()

    @staticmethod
    def _read_balance(user_id: int) -> float:
        db = SessionLocal()
        try:
            balance = db.query(UserBalance.balance).filter(UserBalance.user_id == int(user_id)).scalar()
            return float(balance or 0)
        finally:
            db.close()

    @classmethod
    def _query_and_apply(cls, order_no: str, user_id: int, agent_id: int, timeout: float) -> dict | None:
        local = cls._read_wait_order(order_no, user_id, agent_id)
        if local is None or local.get("status") != "pending":
            return local
        channel = local.get("payment_channel")
        try:
            if channel == "alipay":
                upstream = PaymentService.query_alipay_order(order_no, timeout=timeout)
                trade_status = str(upstream.get("trade_status") or "")
                if trade_status in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES:
                    db = SessionLocal()
                    try:
                        return PaymentService._apply_paid_order(db, order_no, upstream, source="query")
                    finally:
                        db.close()
                if trade_status == "TRADE_CLOSED":
                    db = SessionLocal()
                    try:
                        return PaymentService._mark_order_terminal(db, order_no, "closed", trade_status, upstream, "query")
                    finally:
                        db.close()
            else:
                upstream = PaymentService.query_wechat_order(order_no, timeout=timeout)
                trade_state = str(upstream.get("trade_state") or "").strip().upper()
                if trade_state in PaymentService.WECHAT_SUCCESS_STATES:
                    db = SessionLocal()
                    try:
                        return PaymentService._apply_paid_order(db, order_no, upstream, source="query")
                    finally:
                        db.close()
                if trade_state in PaymentService.WECHAT_CLOSED_STATES:
                    db = SessionLocal()
                    try:
                        return PaymentService._mark_order_terminal(db, order_no, "closed", trade_state, upstream, "query")
                    finally:
                        db.close()
                if trade_state in PaymentService.WECHAT_FAILED_STATES:
                    db = SessionLocal()
                    try:
                        return PaymentService._mark_order_terminal(db, order_no, "failed", trade_state, upstream, "query")
                    finally:
                        db.close()
        except ServiceException:
            logger.info("Open API recharge query is temporarily unavailable for order %s", order_no, exc_info=True)
        except Exception:
            logger.info("Open API recharge query failed for order %s", order_no, exc_info=True)
        return cls._read_wait_order(order_no, user_id, agent_id)

    @classmethod
    def _close_order(cls, order_no: str, user_id: int, agent_id: int, channel: str, timeout: float) -> tuple[bool, dict | None]:
        close_request_confirmed = False
        try:
            if channel == "alipay":
                close_request_confirmed = PaymentService.close_alipay_order(order_no, timeout=timeout)
            else:
                close_request_confirmed = PaymentService.close_wechat_order(order_no, timeout=timeout)
        except Exception:
            # The channel may reject a close because the user paid concurrently.
            # Always query before treating an exception as an unknown outcome.
            logger.info("Open API provider close was not acknowledged for order %s", order_no, exc_info=True)
        try:
            # Resolve the provider-side close/payment race before changing the
            # durable order state. A successful payment always wins.
            if channel == "alipay":
                upstream = PaymentService.query_alipay_order(order_no, timeout=timeout)
                state = str(upstream.get("trade_status") or "").strip()
            else:
                upstream = PaymentService.query_wechat_order(order_no, timeout=timeout)
                state = str(upstream.get("trade_state") or "").strip().upper()
            payment_succeeded = (
                state in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES
                if channel == "alipay"
                else state in PaymentService.WECHAT_SUCCESS_STATES
            )
            if payment_succeeded:
                db = SessionLocal()
                try:
                    paid = PaymentService._apply_paid_order(db, order_no, upstream, source="query")
                    return True, paid
                finally:
                    db.close()
            closed_states = {"TRADE_CLOSED", "NOT_FOUND"} if channel == "alipay" else {*PaymentService.WECHAT_CLOSED_STATES, "NOT_FOUND"}
            if state not in closed_states:
                return False, cls._read_wait_order(order_no, user_id, agent_id)
            db = SessionLocal()
            try:
                order = db.query(PaymentRechargeOrder).filter(
                    PaymentRechargeOrder.order_no == order_no,
                    PaymentRechargeOrder.user_id == int(user_id),
                    PaymentRechargeOrder.agent_id == int(agent_id),
                ).first()
                if order is None:
                    return None, None
                result = PaymentService._mark_order_terminal(db, order_no, "closed", state or "CLOSED", upstream, "query")
                return bool(close_request_confirmed or state in closed_states), result
            finally:
                db.close()
        except Exception:
            logger.info("Open API recharge close is uncertain for order %s", order_no, exc_info=True)
            return False, cls._read_wait_order(order_no, user_id, agent_id)

    @classmethod
    async def wait_for_recharge(
        cls,
        *,
        principal: AgentOpenApiPrincipal,
        user_id: int,
        order_no: str,
        request_ip: str,
        deadline: float | None = None,
    ) -> dict:
        deadline = deadline if deadline is not None else time.monotonic() + cls.WAIT_SECONDS
        rate_limit_key = AuthRateLimitService.build_key(
            f"agent-open-wait-key-{principal.key_id}", request_ip, str(user_id),
        )
        await cls._check_wait_rate_limit(rate_limit_key, deadline=deadline)
        # Acquire synchronously and non-blocking so a full pool rejects
        # immediately instead of queuing and consuming the caller's deadline.
        if not cls._wait_slots.acquire(blocking=False):
            raise ServiceException(429, "同步等待请求已满，请稍后重试", "PAYMENT_WAIT_CAPACITY_REACHED")
        close_result = "not_attempted"
        last_local = None
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= cls.WAIT_RESPONSE_BUDGET_SECONDS:
                    return cls._wait_timeout_payload(order_no, last_local, close_result)
                try:
                    local = await cls._run_provider_call(
                        cls._read_wait_order, order_no, user_id, principal.agent_id,
                        wait_timeout=min(8.0, remaining - cls.WAIT_RESPONSE_BUDGET_SECONDS),
                    )
                except asyncio.TimeoutError:
                    local = last_local
                    if remaining <= cls.WAIT_CLOSE_TRIGGER_SECONDS and local and local.get("status") == "pending":
                        close_result, closed_order = await cls._try_close_before_deadline(
                            order_no, user_id, principal.agent_id, local.get("payment_channel"), deadline,
                        )
                        if closed_order and closed_order.get("status") == "paid":
                            return await cls._paid_wait_result(closed_order, user_id, close_result="uncertain", deadline=deadline)
                        if close_result == "confirmed":
                            return {"wait_result": "closed", "close_result": "confirmed", "order_status": "closed", "order_no": order_no}
                        return cls._wait_timeout_payload(order_no, local, "uncertain")
                    sleep_for = min(cls.WAIT_POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic() - cls.WAIT_RESPONSE_BUDGET_SECONDS))
                    if sleep_for > 0:
                        await asyncio.sleep(sleep_for)
                    continue
                if local is None:
                    raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
                last_local = local
                if local.get("status") == "paid":
                    return await cls._paid_wait_result(local, user_id, deadline=deadline)
                if local.get("status") == "closed":
                    return {"wait_result": "closed", "close_result": "confirmed", "order_status": "closed", "order_no": order_no}
                if local.get("status") == "failed":
                    return {"wait_result": "failed", "close_result": close_result, "order_status": "failed", "order_no": order_no}
                remaining = deadline - time.monotonic()
                if remaining <= cls.WAIT_CLOSE_TRIGGER_SECONDS:
                    close_result, closed_order = await cls._try_close_before_deadline(
                        order_no, user_id, principal.agent_id, local.get("payment_channel"), deadline,
                    )
                    if closed_order and closed_order.get("status") == "paid":
                        return await cls._paid_wait_result(closed_order, user_id, close_result="uncertain", deadline=deadline)
                    if close_result == "confirmed":
                        return {"wait_result": "closed", "close_result": "confirmed", "order_status": "closed", "order_no": order_no}
                    return cls._wait_timeout_payload(order_no, local, "uncertain")

                # Keep enough time after every channel query for a bounded
                # close attempt, the balance read and response serialization.
                query_timeout = min(cls.WAIT_NETWORK_TIMEOUT_SECONDS, remaining - cls.WAIT_CLOSE_BUDGET_SECONDS - cls.WAIT_PAID_BALANCE_BUDGET_SECONDS - cls.WAIT_RESPONSE_BUDGET_SECONDS)
                if query_timeout <= 0:
                    return cls._wait_timeout_payload(order_no, local, close_result)
                try:
                    updated = await cls._run_provider_call(
                        cls._query_and_apply, order_no, user_id, principal.agent_id, query_timeout,
                        wait_timeout=min(query_timeout + 2, remaining - cls.WAIT_CLOSE_BUDGET_SECONDS - cls.WAIT_PAID_BALANCE_BUDGET_SECONDS - cls.WAIT_RESPONSE_BUDGET_SECONDS),
                    )
                except asyncio.TimeoutError:
                    updated = None
                if updated and updated.get("status") == "paid":
                    return await cls._paid_wait_result(updated, user_id, deadline=deadline)
                if updated and updated.get("status") == "closed":
                    return {"wait_result": "closed", "close_result": "confirmed", "order_status": "closed", "order_no": order_no}
                if updated and updated.get("status") == "failed":
                    return {"wait_result": "failed", "close_result": "not_attempted", "order_status": "failed", "order_no": order_no}
                sleep_for = min(cls.WAIT_POLL_INTERVAL_SECONDS, max(0, deadline - time.monotonic() - cls.WAIT_RESPONSE_BUDGET_SECONDS))
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
        finally:
            cls._wait_slots.release()

    @classmethod
    async def _try_close_before_deadline(
        cls,
        order_no: str,
        user_id: int,
        agent_id: int,
        channel: str,
        deadline: float,
    ) -> tuple[str, dict | None]:
        remaining = deadline - time.monotonic()
        reserve = cls.WAIT_PAID_BALANCE_BUDGET_SECONDS + cls.WAIT_RESPONSE_BUDGET_SECONDS
        if remaining <= reserve + 0.5:
            return "uncertain", None
        # _close_order performs a close and a confirming query. Bound both
        # real provider calls, then leave a small balance/response reserve.
        provider_timeout = min(cls.WAIT_NETWORK_TIMEOUT_SECONDS, (remaining - reserve - 0.25) / 2)
        if provider_timeout <= 0:
            return "uncertain", None
        wait_timeout = min(provider_timeout * 2 + 0.25, remaining - reserve)
        try:
            confirmed, order = await cls._run_provider_call(
                cls._close_order,
                order_no,
                user_id,
                agent_id,
                channel,
                provider_timeout,
                wait_timeout=wait_timeout,
            )
        except (asyncio.TimeoutError, ServiceException):
            return "uncertain", None
        if confirmed and isinstance(order, dict):
            return "confirmed", order
        return "uncertain", order if isinstance(order, dict) else None

    @staticmethod
    def _wait_timeout_payload(order_no: str, order: dict | None, close_result: str) -> dict:
        status = str((order or {}).get("status") or "pending")
        if status != "pending":
            status = "pending"
        return {"wait_result": "wait_timeout", "close_result": close_result, "order_status": status, "order_no": order_no}

    @classmethod
    async def _paid_wait_result(
        cls,
        order: dict,
        user_id: int,
        close_result: str = "not_attempted",
        deadline: float | None = None,
    ) -> dict:
        balance_timeout = 8.0
        if deadline is not None:
            balance_timeout = min(
                balance_timeout,
                deadline - time.monotonic() - cls.WAIT_RESPONSE_BUDGET_SECONDS,
            )
        balance = None
        if balance_timeout > 0:
            try:
                balance = await cls._run_provider_call(cls._read_balance, user_id, wait_timeout=balance_timeout)
            except (asyncio.TimeoutError, ServiceException):
                logger.info("Open API paid balance read exceeded its remaining response budget", exc_info=True)
        return {
            "wait_result": "paid",
            "close_result": close_result,
            "order_status": "paid",
            "order_no": order.get("order_no"),
            "paid_at": order.get("paid_at"),
            "balance": balance,
        }
