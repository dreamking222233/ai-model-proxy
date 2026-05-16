"""Alipay recharge order service."""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ServiceException
from app.models.log import ConsumptionRecord, UserBalance
from app.models.payment import (
    AgentCashBalance,
    AgentCashLedger,
    PaymentRechargeOrder,
)
from app.models.user import SysUser
from app.services.agent_service import AgentService, AgentSiteContext

logger = logging.getLogger(__name__)


class PaymentService:
    """Online recharge flow backed by Alipay page pay."""

    CNY_SCALE = Decimal("0.01")
    USD_SCALE = Decimal("0.000001")
    ORDER_EXPIRE_MINUTES = 30
    PAY_CHANNEL = "alipay"
    ACCEPTED_TRADE_STATUSES = {"TRADE_SUCCESS", "TRADE_FINISHED"}

    @staticmethod
    def _quantize(value, scale: Decimal, code: str, allow_zero: bool = False) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(scale, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "金额格式不正确", code) from exc
        if allow_zero:
            if amount < Decimal("0"):
                raise ServiceException(400, "金额不能小于 0", code)
        elif amount <= Decimal("0"):
            raise ServiceException(400, "金额必须大于 0", code)
        return amount

    @staticmethod
    def _normalize_cny(value, code: str = "INVALID_RECHARGE_AMOUNT") -> Decimal:
        return PaymentService._quantize(value, PaymentService.CNY_SCALE, code)

    @staticmethod
    def _normalize_usd(value, code: str = "INVALID_USD_AMOUNT", allow_zero: bool = False) -> Decimal:
        return PaymentService._quantize(value, PaymentService.USD_SCALE, code, allow_zero=allow_zero)

    @staticmethod
    def _try_normalize_cny(value) -> Decimal | None:
        if value is None:
            return None
        try:
            amount = Decimal(str(value)).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None
        return amount

    @staticmethod
    def _settings_decimal(value, code: str) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(500, "支付配置无效", code) from exc
        if amount <= Decimal("0"):
            raise ServiceException(500, "支付配置无效", code)
        return amount

    @staticmethod
    def _is_local_host(host: str | None) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"} or normalized.endswith(".localhost") or normalized.endswith(".local")

    @staticmethod
    def _build_origin_from_host(host: str | None) -> str:
        normalized = AgentService.normalize_host(host)
        if not normalized:
            raise ServiceException(500, "无法生成支付回跳地址", "PAYMENT_RETURN_HOST_MISSING")
        scheme = "http" if PaymentService._is_local_host(normalized) else "https"
        return f"{scheme}://{normalized}"

    @staticmethod
    def _build_origin_from_site_context(site_context: AgentSiteContext | None) -> str:
        if not site_context:
            return ""
        for raw_url in (getattr(site_context, "origin_url", ""), getattr(site_context, "referer_url", "")):
            value = str(raw_url or "").strip()
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return ""

    @staticmethod
    def _get_platform_frontend_host() -> str:
        for item in settings.PLATFORM_FRONTEND_HOSTS:
            normalized = AgentService.normalize_host(item)
            if normalized and not AgentService.is_platform_api_host(normalized):
                return normalized
        raise ServiceException(500, "未配置平台前台域名", "PAYMENT_PLATFORM_HOST_MISSING")

    @staticmethod
    def _append_query(url: str, params: dict[str, str]) -> str:
        parsed = urlparse(url)
        current = dict(parse_qsl(parsed.query, keep_blank_values=True))
        current.update({k: v for k, v in params.items() if v is not None})
        return urlunparse(parsed._replace(query=urlencode(current)))

    @staticmethod
    def _build_pem_key(raw_key: str) -> bytes:
        text = str(raw_key or "").strip()
        if not text:
            raise ServiceException(500, "缺少支付宝公钥配置", "ALIPAY_PUBLIC_KEY_MISSING")
        if "BEGIN PUBLIC KEY" in text:
            return text.encode("utf-8")
        wrapped = "-----BEGIN PUBLIC KEY-----\n" + text + "\n-----END PUBLIC KEY-----\n"
        return wrapped.encode("utf-8")

    @staticmethod
    def _build_private_pem_key(raw_key: str) -> bytes:
        text = str(raw_key or "").strip()
        if not text:
            raise ServiceException(500, "缺少支付宝应用私钥配置", "ALIPAY_PRIVATE_KEY_MISSING")

        if "BEGIN " not in text:
            text = "-----BEGIN PRIVATE KEY-----\n" + text + "\n-----END PRIVATE KEY-----\n"

        try:
            private_key = load_pem_private_key(text.encode("utf-8"), password=None)
        except Exception as exc:
            raise ServiceException(500, "支付宝应用私钥格式无效", "ALIPAY_PRIVATE_KEY_INVALID") from exc

        # Old alipay-sdk-python expects PKCS1 RSA PRIVATE KEY for rsa.PrivateKey.load_pkcs1.
        return private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )

    @staticmethod
    def _get_notify_url() -> str:
        configured = str(settings.ALIPAY_NOTIFY_URL or "").strip()
        if configured:
            return configured
        base = str(settings.PAYMENT_PUBLIC_BASE_URL or "").strip().rstrip("/")
        if not base:
            raise ServiceException(500, "缺少支付宝通知地址配置", "ALIPAY_NOTIFY_URL_MISSING")
        return f"{base}/api/public/payment/alipay/notify"

    @staticmethod
    def _validate_payment_config() -> None:
        if not bool(settings.ALIPAY_ENABLED):
            raise ServiceException(400, "在线充值暂未开启", "PAYMENT_DISABLED")
        if not str(settings.ALIPAY_APP_ID or "").strip():
            raise ServiceException(500, "缺少支付宝 AppId 配置", "ALIPAY_APP_ID_MISSING")
        if not str(settings.ALIPAY_APP_PRIVATE_KEY or "").strip():
            raise ServiceException(500, "缺少支付宝应用私钥配置", "ALIPAY_PRIVATE_KEY_MISSING")
        if not str(settings.ALIPAY_PUBLIC_KEY or "").strip():
            raise ServiceException(500, "缺少支付宝公钥配置", "ALIPAY_PUBLIC_KEY_MISSING")
        PaymentService._get_notify_url()

    @staticmethod
    def assert_recharge_enabled_for_site(site_context: AgentSiteContext | None = None) -> None:
        if not bool(settings.ALIPAY_ENABLED):
            raise ServiceException(400, "在线充值暂未开启", "PAYMENT_DISABLED")
        if site_context and not AgentService.is_online_recharge_enabled(site_context):
            raise ServiceException(403, "当前站点未开启在线充值", "AGENT_ONLINE_RECHARGE_DISABLED")

    @staticmethod
    def _build_alipay_client():
        try:
            from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
            from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        config = AlipayClientConfig()
        config.server_url = settings.ALIPAY_SERVER_URL
        config.app_id = settings.ALIPAY_APP_ID
        config.app_private_key = PaymentService._build_private_pem_key(settings.ALIPAY_APP_PRIVATE_KEY).decode("utf-8")
        config.alipay_public_key = load_pem_public_key(
            PaymentService._build_pem_key(settings.ALIPAY_PUBLIC_KEY)
        ).public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return DefaultAlipayClient(alipay_client_config=config)

    @staticmethod
    def _generate_order_no() -> str:
        return "ALP" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()

    @staticmethod
    def _build_subject() -> str:
        return "AI 平台在线充值"

    @staticmethod
    def _build_body() -> str:
        return "用户在线充值美元余额"

    @staticmethod
    def build_order_return_url(order: PaymentRechargeOrder, site_context: AgentSiteContext | None = None) -> str:
        explicit_origin = PaymentService._build_origin_from_site_context(site_context)
        if explicit_origin:
            base = f"{explicit_origin.rstrip('/')}{str(settings.ALIPAY_RETURN_PATH or '/user/recharge')}"
            return PaymentService._append_query(base, {"order_no": order.order_no})

        source_host = AgentService.normalize_host(getattr(site_context, "host", None) or order.source_host)
        if not source_host and order.site_scope == "agent":
            raise ServiceException(500, "代理站点缺少前台域名，无法创建回跳地址", "PAYMENT_RETURN_HOST_MISSING")
        if not source_host:
            source_host = PaymentService._get_platform_frontend_host()
        origin = PaymentService._build_origin_from_host(source_host)
        base = f"{origin.rstrip('/')}{str(settings.ALIPAY_RETURN_PATH or '/user/recharge')}"
        return PaymentService._append_query(base, {"order_no": order.order_no})

    @staticmethod
    def _calculate_amounts(amount_cny: Decimal, agent_id: int | None) -> tuple[Decimal, Decimal, Decimal]:
        user_rate = PaymentService._settings_decimal(
            settings.RECHARGE_USER_CNY_TO_USD_RATE,
            "RECHARGE_USER_RATE_INVALID",
        )
        agent_rate = PaymentService._settings_decimal(
            settings.RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE,
            "RECHARGE_AGENT_RATE_INVALID",
        )
        credited_usd = (amount_cny * user_rate).quantize(PaymentService.USD_SCALE, rounding=ROUND_HALF_UP)
        if not agent_id:
            return credited_usd, agent_rate, Decimal("0.00")

        agent_cost_cny = (credited_usd / agent_rate).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        agent_income_cny = (amount_cny - agent_cost_cny).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        if agent_income_cny < Decimal("0"):
            raise ServiceException(500, "代理结算比例配置错误，导致代理分润为负数", "RECHARGE_AGENT_INCOME_INVALID")
        return credited_usd, agent_rate, agent_income_cny

    @staticmethod
    def create_recharge_order(
        db: Session,
        user: SysUser,
        amount_cny,
        site_context: AgentSiteContext | None = None,
    ) -> dict:
        PaymentService._validate_payment_config()
        PaymentService.assert_recharge_enabled_for_site(site_context)
        amount_decimal = PaymentService._normalize_cny(amount_cny)
        credited_usd, agent_rate, agent_income_cny = PaymentService._calculate_amounts(amount_decimal, user.agent_id)
        order = PaymentRechargeOrder(
            order_no=PaymentService._generate_order_no(),
            payment_channel=PaymentService.PAY_CHANNEL,
            user_id=user.id,
            agent_id=user.agent_id,
            site_scope="agent" if user.agent_id else "platform",
            source_host=AgentService.normalize_host(getattr(site_context, "host", None) or getattr(site_context, "request_host", None)),
            amount_cny=amount_decimal,
            credited_usd=credited_usd,
            agent_settlement_rate=agent_rate,
            agent_income_cny=agent_income_cny,
            status="pending",
            subject=PaymentService._build_subject(),
            body=PaymentService._build_body(),
            expired_at=datetime.utcnow() + timedelta(minutes=PaymentService.ORDER_EXPIRE_MINUTES),
        )
        order.return_url_snapshot = PaymentService.build_order_return_url(order, site_context)
        db.add(order)
        db.flush()
        pay_url = PaymentService.build_alipay_page_pay_url(order, order.return_url_snapshot)
        db.commit()
        db.refresh(order)
        return {
            "order": PaymentService.serialize_order(order),
            "pay_url": pay_url,
        }

    @staticmethod
    def _apply_request_urls(request, notify_url: str, return_url: str) -> None:
        if hasattr(request, "notify_url"):
            request.notify_url = notify_url
        if hasattr(request, "return_url"):
            request.return_url = return_url
        setter = getattr(request, "set_notify_url", None)
        if callable(setter):
            setter(notify_url)
        setter = getattr(request, "set_return_url", None)
        if callable(setter):
            setter(return_url)

    @staticmethod
    def build_alipay_page_pay_url(order: PaymentRechargeOrder, return_url: str) -> str:
        PaymentService._validate_payment_config()
        try:
            from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
            from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        client = PaymentService._build_alipay_client()
        model = AlipayTradePagePayModel()
        model.out_trade_no = order.order_no
        model.total_amount = str(Decimal(str(order.amount_cny or 0)).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP))
        model.subject = order.subject
        model.body = order.body
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        model.timeout_express = f"{PaymentService.ORDER_EXPIRE_MINUTES}m"
        request = AlipayTradePagePayRequest(biz_model=model)
        PaymentService._apply_request_urls(request, PaymentService._get_notify_url(), return_url)
        response = client.page_execute(request, http_method="GET")
        if not response:
            raise ServiceException(500, "支付宝下单失败，请稍后重试", "ALIPAY_PAGE_PAY_FAILED")
        return response

    @staticmethod
    def _serialize_query_response(response) -> dict:
        return {
            "trade_status": getattr(response, "trade_status", None),
            "alipay_trade_no": getattr(response, "trade_no", None),
            "buyer_logon_id": getattr(response, "buyer_logon_id", None),
            "buyer_user_id": getattr(response, "buyer_user_id", None),
            "total_amount": getattr(response, "total_amount", None),
        }

    @staticmethod
    def query_alipay_order(order_no: str) -> dict:
        PaymentService._validate_payment_config()
        try:
            from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
            from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
            from alipay.aop.api.response.AlipayTradeQueryResponse import AlipayTradeQueryResponse
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        client = PaymentService._build_alipay_client()
        model = AlipayTradeQueryModel()
        model.out_trade_no = order_no
        request = AlipayTradeQueryRequest(biz_model=model)
        response_content = client.execute(request)
        if not response_content:
            raise ServiceException(500, "支付宝查单失败", "ALIPAY_QUERY_FAILED")
        response = AlipayTradeQueryResponse()
        response.parse_response_content(response_content)
        if not response.is_success():
            code = str(getattr(response, "sub_code", None) or getattr(response, "code", None) or "")
            if code == "ACQ.TRADE_NOT_EXIST":
                return {"trade_status": "NOT_FOUND"}
            raise ServiceException(500, "支付宝查单失败", "ALIPAY_QUERY_FAILED")
        return PaymentService._serialize_query_response(response)

    @staticmethod
    def _load_order_for_user(db: Session, order_no: str, user_id: int) -> PaymentRechargeOrder:
        order = (
            db.query(PaymentRechargeOrder)
            .filter(
                PaymentRechargeOrder.order_no == order_no,
                PaymentRechargeOrder.user_id == user_id,
            )
            .first()
        )
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
        return order

    @staticmethod
    def list_user_orders(db: Session, user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        query = db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.user_id == user_id)
        total = query.count()
        rows = (
            query.order_by(PaymentRechargeOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [PaymentService.serialize_order(row) for row in rows], total

    @staticmethod
    def get_user_order(db: Session, user_id: int, order_no: str) -> dict:
        return PaymentService.serialize_order(PaymentService._load_order_for_user(db, order_no, user_id))

    @staticmethod
    def sync_order_status_from_alipay(db: Session, user_id: int, order_no: str) -> dict:
        order = PaymentService._load_order_for_user(db, order_no, user_id)
        if order.status == "paid":
            return PaymentService.serialize_order(order)

        upstream = PaymentService.query_alipay_order(order.order_no)
        trade_status = str(upstream.get("trade_status") or "")
        if trade_status in PaymentService.ACCEPTED_TRADE_STATUSES:
            return PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
        if trade_status == "TRADE_CLOSED":
            locked = (
                db.query(PaymentRechargeOrder)
                .filter(PaymentRechargeOrder.order_no == order.order_no)
                .with_for_update()
                .first()
            )
            if locked and locked.status == "pending":
                locked.status = "closed"
                locked.trade_status = trade_status
                locked.closed_at = datetime.utcnow()
                db.commit()
                db.refresh(locked)
                return PaymentService.serialize_order(locked)
        return PaymentService.serialize_order(order)

    @staticmethod
    def _verify_alipay_signature(params: dict[str, str]) -> None:
        sign = str(params.get("sign") or "").strip()
        if not sign:
            raise ServiceException(400, "缺少支付宝签名", "ALIPAY_SIGN_MISSING")
        try:
            from alipay.aop.api.util.SignatureUtils import get_sign_content, verify_with_rsa
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        public_key = str(settings.ALIPAY_PUBLIC_KEY or "").strip()
        candidates = [
            (
                "sdk_keep_sign_type",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key != "sign" and value is not None
                },
            ),
            (
                "doc_drop_sign_type",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key not in {"sign", "sign_type"} and value is not None
                },
            ),
            (
                "legacy_drop_empty",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key not in {"sign", "sign_type"} and value is not None and str(value) != ""
                },
            ),
        ]

        seen_sign_contents: set[str] = set()
        errors: list[str] = []
        for strategy, candidate in candidates:
            sign_content = get_sign_content(candidate)
            if sign_content in seen_sign_contents:
                continue
            seen_sign_contents.add(sign_content)
            try:
                verified = bool(verify_with_rsa(public_key, sign_content.encode("utf-8"), sign))
            except Exception as exc:  # pragma: no cover - depends on upstream callback data
                errors.append(f"{strategy}:{exc}")
                continue
            if verified:
                if strategy != "sdk_keep_sign_type":
                    logger.warning("Alipay notify verified with fallback strategy: %s", strategy)
                return
            errors.append(f"{strategy}:verify_false")

        logger.error("Alipay signature verification failed. keys=%s errors=%s", sorted(params.keys()), errors)
        raise ServiceException(400, "支付宝签名校验失败", "ALIPAY_SIGN_INVALID")

    @staticmethod
    def _get_order_for_update(db: Session, order_no: str) -> PaymentRechargeOrder:
        order = (
            db.query(PaymentRechargeOrder)
            .filter(PaymentRechargeOrder.order_no == order_no)
            .with_for_update()
            .first()
        )
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
        return order

    @staticmethod
    def _get_or_create_agent_cash_balance_for_update(db: Session, agent_id: int) -> AgentCashBalance:
        balance = (
            db.query(AgentCashBalance)
            .filter(AgentCashBalance.agent_id == agent_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = AgentCashBalance(agent_id=agent_id, balance=0, total_income=0, total_withdrawn=0, total_adjusted=0)
            db.add(balance)
            db.flush()
            balance = (
                db.query(AgentCashBalance)
                .filter(AgentCashBalance.agent_id == agent_id)
                .with_for_update()
                .first()
            )
        return balance

    @staticmethod
    def _credit_user_balance(db: Session, order: PaymentRechargeOrder) -> None:
        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == order.user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "用户余额记录不存在", "BALANCE_NOT_FOUND")

        credited_usd = PaymentService._normalize_usd(order.credited_usd)
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + credited_usd
        balance.total_recharged = Decimal(str(balance.total_recharged or 0)) + credited_usd

        db.add(ConsumptionRecord(
            user_id=order.user_id,
            agent_id=order.agent_id,
            request_id=order.order_no,
            model_name="支付宝充值",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=-credited_usd,
            balance_before=balance_before,
            balance_after=balance.balance,
            billing_mode="balance",
        ))

    @staticmethod
    def _credit_agent_cash_balance(db: Session, order: PaymentRechargeOrder) -> None:
        if not order.agent_id:
            return
        income = PaymentService._try_normalize_cny(order.agent_income_cny)
        if income is None:
            raise ServiceException(500, "代理现金分润金额格式无效", "AGENT_CASH_INCOME_INVALID")
        if income <= Decimal("0"):
            return
        balance = PaymentService._get_or_create_agent_cash_balance_for_update(db, int(order.agent_id))
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + income
        balance.total_income = Decimal(str(balance.total_income or 0)) + income
        db.add(AgentCashLedger(
            agent_id=int(order.agent_id),
            order_id=order.id,
            withdrawal_id=None,
            action_type="recharge_commission",
            change_amount=income,
            balance_before=balance_before,
            balance_after=balance.balance,
            operator_user_id=None,
            remark=f"用户在线充值分润，订单 {order.order_no}",
        ))

    @staticmethod
    def _apply_paid_order(db: Session, order_no: str, payload: dict, source: str = "notify") -> dict:
        locked = PaymentService._get_order_for_update(db, order_no)
        if locked.status == "paid":
            return PaymentService.serialize_order(locked)
        if locked.status != "pending":
            raise ServiceException(400, "订单状态不允许再次入账", "RECHARGE_ORDER_STATUS_INVALID")

        app_id = str(payload.get("app_id") or settings.ALIPAY_APP_ID or "").strip()
        if app_id and app_id != str(settings.ALIPAY_APP_ID or "").strip():
            raise ServiceException(400, "支付宝应用编号不匹配", "ALIPAY_APP_ID_MISMATCH")

        trade_status = str(payload.get("trade_status") or "").strip()
        if trade_status not in PaymentService.ACCEPTED_TRADE_STATUSES:
            raise ServiceException(400, "支付宝交易状态不支持入账", "ALIPAY_TRADE_STATUS_INVALID")

        total_amount = payload.get("total_amount")
        if source == "notify":
            if total_amount is not None:
                notify_amount = PaymentService._normalize_cny(total_amount)
                local_amount = PaymentService._normalize_cny(locked.amount_cny)
                if notify_amount != local_amount:
                    raise ServiceException(400, "支付宝回调金额与本地订单不一致", "ALIPAY_AMOUNT_MISMATCH")
        elif total_amount is not None:
            queried_amount = PaymentService._try_normalize_cny(total_amount)
            if queried_amount is not None and queried_amount > Decimal("0"):
                local_amount = PaymentService._normalize_cny(locked.amount_cny)
                if queried_amount != local_amount:
                    raise ServiceException(400, "支付宝回调金额与本地订单不一致", "ALIPAY_AMOUNT_MISMATCH")

        alipay_trade_no = str(payload.get("alipay_trade_no") or payload.get("trade_no") or "").strip() or None
        if alipay_trade_no:
            exists = (
                db.query(PaymentRechargeOrder)
                .filter(
                    PaymentRechargeOrder.alipay_trade_no == alipay_trade_no,
                    PaymentRechargeOrder.order_no != locked.order_no,
                )
                .first()
            )
            if exists:
                raise ServiceException(400, "支付宝交易号已被其他订单占用", "ALIPAY_TRADE_NO_CONFLICT")

        PaymentService._credit_user_balance(db, locked)
        PaymentService._credit_agent_cash_balance(db, locked)

        locked.status = "paid"
        locked.trade_status = trade_status
        locked.alipay_trade_no = alipay_trade_no
        locked.buyer_logon_id = str(payload.get("buyer_logon_id") or locked.buyer_logon_id or "")
        locked.buyer_user_id = str(payload.get("buyer_user_id") or locked.buyer_user_id or "")
        locked.paid_at = datetime.utcnow()
        if source == "notify":
            locked.notify_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        else:
            locked.return_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        db.commit()
        db.refresh(locked)
        return PaymentService.serialize_order(locked)

    @staticmethod
    def handle_alipay_notify(db: Session, form_data: dict[str, str]) -> bool:
        PaymentService._validate_payment_config()
        params = {str(key): str(value) for key, value in form_data.items()}
        PaymentService._verify_alipay_signature(params)
        order_no = str(params.get("out_trade_no") or "").strip()
        if not order_no:
            raise ServiceException(400, "缺少订单号", "RECHARGE_ORDER_NO_MISSING")

        trade_status = str(params.get("trade_status") or "").strip()
        if trade_status in PaymentService.ACCEPTED_TRADE_STATUSES:
            PaymentService._apply_paid_order(db, order_no, {
                "app_id": params.get("app_id"),
                "trade_status": trade_status,
                "total_amount": params.get("total_amount"),
                "alipay_trade_no": params.get("trade_no"),
                "buyer_logon_id": params.get("buyer_logon_id"),
                "buyer_user_id": params.get("buyer_user_id"),
                "notify_id": params.get("notify_id"),
                "raw": params,
            }, source="notify")
            return True

        if trade_status == "TRADE_CLOSED":
            order = PaymentService._get_order_for_update(db, order_no)
            if order.status == "pending":
                order.status = "closed"
                order.trade_status = trade_status
                order.closed_at = datetime.utcnow()
                order.notify_raw = json.dumps(params, ensure_ascii=False, sort_keys=True)
                db.commit()
            return True
        return True

    @staticmethod
    def handle_alipay_return(db: Session, query_params: dict[str, str]) -> str:
        order_no = str(query_params.get("out_trade_no") or query_params.get("order_no") or "").strip()
        if not order_no:
            raise ServiceException(400, "缺少订单号", "RECHARGE_ORDER_NO_MISSING")
        order = db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.order_no == order_no).first()
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")

        order.return_raw = json.dumps({str(key): str(value) for key, value in query_params.items()}, ensure_ascii=False, sort_keys=True)
        db.commit()
        return PaymentService._append_query(
            order.return_url_snapshot or PaymentService.build_order_return_url(order),
            {"trade_status": str(query_params.get("trade_status") or ""), "order_no": order.order_no},
        )

    @staticmethod
    def serialize_order(order: PaymentRechargeOrder) -> dict:
        return {
            "id": order.id,
            "order_no": order.order_no,
            "payment_channel": order.payment_channel,
            "user_id": order.user_id,
            "agent_id": order.agent_id,
            "site_scope": order.site_scope,
            "source_host": order.source_host,
            "amount_cny": float(order.amount_cny or 0),
            "credited_usd": float(order.credited_usd or 0),
            "agent_income_cny": float(order.agent_income_cny or 0),
            "status": order.status,
            "trade_status": order.trade_status,
            "subject": order.subject,
            "return_url_snapshot": order.return_url_snapshot,
            "alipay_trade_no": order.alipay_trade_no,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "expired_at": order.expired_at.isoformat() if order.expired_at else None,
            "closed_at": order.closed_at.isoformat() if order.closed_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        }
