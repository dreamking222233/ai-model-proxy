"""Balance management service."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, exists, literal, or_
from sqlalchemy.orm import Session

from app.models.log import UserBalance, ConsumptionRecord, RequestLog
from app.models.payment import PaymentRechargeOrder
from app.core.exceptions import ServiceException


class BalanceService:
    """User balance queries and admin recharge operations."""

    ASSET_TYPES = {"all", "balance"}
    DIRECTIONS = {"all", "increase", "decrease"}

    @staticmethod
    def _normalize_remark(remark: str | None) -> str | None:
        text = str(remark or "").strip()
        return text[:255] if text else None

    @staticmethod
    def get_balance(db: Session, user_id: int) -> dict:
        """
        Get the balance record for a user.

        Returns:
            dict with ``user_id``, ``balance``, ``total_recharged``, ``total_consumed``.

        Raises:
            ServiceException: if balance record not found.
        """
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
        }

    @staticmethod
    def recharge(db: Session, user_id: int, amount: Decimal, operator_id: int, reason: str | None = None) -> dict:
        """
        Add funds to a user's balance.

        Uses ``SELECT ... FOR UPDATE`` to prevent race conditions.

        Args:
            user_id: target user.
            amount: positive Decimal amount to add.
            operator_id: admin user performing the recharge.

        Returns:
            dict with updated balance info.

        Raises:
            ServiceException: if balance record not found or amount invalid.
        """
        if amount <= 0:
            raise ServiceException(400, "Recharge amount must be positive", "INVALID_AMOUNT")

        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        balance_before = float(balance.balance)
        balance.balance += amount
        balance.total_recharged += amount

        # Write a consumption record for the recharge (positive amount)
        record = ConsumptionRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=-amount,  # negative cost = recharge
            balance_before=Decimal(str(balance_before)),
            balance_after=balance.balance,
            operator_id=operator_id,
            remark=BalanceService._normalize_remark(reason),
        )
        db.add(record)
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "recharged_amount": float(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def deduct(db: Session, user_id: int, amount: Decimal, operator_id: int, reason: str = None) -> dict:
        """
        Deduct funds from a user's balance (admin operation).

        Args:
            user_id: target user.
            amount: positive Decimal amount to deduct.
            operator_id: admin user performing the deduction.
            reason: optional reason for deduction.

        Returns:
            dict with updated balance info.

        Raises:
            ServiceException: if balance record not found, amount invalid, or insufficient balance.
        """
        if amount <= 0:
            raise ServiceException(400, "Deduct amount must be positive", "INVALID_AMOUNT")

        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        if balance.balance < amount:
            raise ServiceException(400, "Insufficient balance", "INSUFFICIENT_BALANCE")

        balance_before = float(balance.balance)
        balance.balance -= amount
        balance.total_consumed += amount

        record = ConsumptionRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=amount,  # positive cost = deduction
            balance_before=Decimal(str(balance_before)),
            balance_after=balance.balance,
            operator_id=operator_id,
            remark=BalanceService._normalize_remark(reason),
        )
        db.add(record)
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "deducted_amount": float(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def _payment_channel_text(payment_channel: str | None) -> str:
        channel = str(payment_channel or "").strip().lower()
        return {"alipay": "支付宝", "wechat": "微信支付"}.get(channel, channel or "-")

    @staticmethod
    def _asset_type_text(asset_type: str | None) -> str:
        return {"balance": "余额"}.get(asset_type or "", asset_type or "-")

    @staticmethod
    def _normalize_recharge_type(recharge_type: str | None) -> str:
        normalized = str(recharge_type or "balance").strip().lower()
        return normalized if normalized in {"balance", "image_credit"} else ""

    @staticmethod
    def _row_value(row, key: str):
        mapping = getattr(row, "_mapping", None)
        if mapping is not None and key in mapping:
            return mapping[key]
        return getattr(row, key)

    @staticmethod
    def _serialize_asset_source_record(row, order_map: dict[str, PaymentRechargeOrder]) -> dict:
        asset_type = str(BalanceService._row_value(row, "asset_type") or "")
        record_id = BalanceService._row_value(row, "id")
        signed_amount = Decimal(str(BalanceService._row_value(row, "signed_amount") or 0))
        direction = "increase" if signed_amount > 0 else "decrease"
        request_id = str(BalanceService._row_value(row, "request_id") or "").strip() or None
        model_name = str(BalanceService._row_value(row, "model_name") or "").strip() or None
        agent_id = BalanceService._row_value(row, "agent_id")
        operator_id = BalanceService._row_value(row, "operator_id")
        action_type = str(BalanceService._row_value(row, "action_type") or "").strip() or None
        billing_mode = str(BalanceService._row_value(row, "billing_mode") or "").strip() or None
        remark = BalanceService._normalize_remark(BalanceService._row_value(row, "remark"))
        created_at = BalanceService._row_value(row, "created_at")

        order = order_map.get(request_id or "")
        if (
            order
            and direction == "increase"
            and str(getattr(order, "status", "") or "").strip().lower() == "paid"
            and BalanceService._normalize_recharge_type(getattr(order, "recharge_type", None)) == asset_type
        ):
            source = "线上充值"
            remark = BalanceService._payment_channel_text(getattr(order, "payment_channel", None))
            action_type = "recharge"
        elif agent_id:
            source = "代理端"
        elif operator_id:
            source = "管理端"
        elif direction == "increase":
            source = "历史充值"
            action_type = action_type or "recharge"
            remark = remark or model_name
        else:
            source = "系统扣减"
            action_type = action_type or "deduct"

        return {
            "id": int(record_id),
            "record_key": f"{asset_type}-{record_id}",
            "asset_type": asset_type,
            "asset_type_text": BalanceService._asset_type_text(asset_type),
            "direction": direction,
            "amount": float(abs(signed_amount)),
            "source": source,
            "remark": remark,
            "request_id": request_id,
            "model_name": model_name,
            "action_type": action_type,
            "billing_mode": billing_mode,
            "balance_before": float(Decimal(str(BalanceService._row_value(row, "balance_before") or 0))),
            "balance_after": float(Decimal(str(BalanceService._row_value(row, "balance_after") or 0))),
            "created_at": created_at.isoformat() if created_at else None,
        }

    @staticmethod
    def get_asset_source_records(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        asset_type: str = "all",
        direction: str = "all",
    ) -> tuple[list[dict], int]:
        normalized_asset_type = str(asset_type or "all").strip().lower()
        normalized_direction = str(direction or "all").strip().lower()
        if normalized_asset_type not in BalanceService.ASSET_TYPES:
            raise ServiceException(400, "不支持的资产类型", "ASSET_TYPE_INVALID")
        if normalized_direction not in BalanceService.DIRECTIONS:
            raise ServiceException(400, "不支持的变动方向", "ASSET_DIRECTION_INVALID")

        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 20), 1), 100)
        blank_request = or_(ConsumptionRecord.request_id.is_(None), ConsumptionRecord.request_id == "")
        blank_model = or_(ConsumptionRecord.model_name.is_(None), ConsumptionRecord.model_name == "")
        manual_balance_change = and_(blank_request, blank_model)
        paid_balance_recharge = exists().where(and_(
            PaymentRechargeOrder.user_id == ConsumptionRecord.user_id,
            PaymentRechargeOrder.order_no == ConsumptionRecord.request_id,
            PaymentRechargeOrder.status == "paid",
            PaymentRechargeOrder.recharge_type == "balance",
        ))

        balance_query = db.query(
            ConsumptionRecord.id.label("id"),
            literal("balance").label("asset_type"),
            (-ConsumptionRecord.total_cost).label("signed_amount"),
            ConsumptionRecord.balance_before.label("balance_before"),
            ConsumptionRecord.balance_after.label("balance_after"),
            ConsumptionRecord.request_id.label("request_id"),
            ConsumptionRecord.model_name.label("model_name"),
            ConsumptionRecord.agent_id.label("agent_id"),
            ConsumptionRecord.operator_id.label("operator_id"),
            literal(None).label("action_type"),
            ConsumptionRecord.billing_mode.label("billing_mode"),
            ConsumptionRecord.remark.label("remark"),
            ConsumptionRecord.created_at.label("created_at"),
        ).filter(
            ConsumptionRecord.user_id == user_id,
            ConsumptionRecord.total_cost != Decimal("0"),
            or_(manual_balance_change, paid_balance_recharge),
        )
        if normalized_direction == "increase":
            balance_query = balance_query.filter(ConsumptionRecord.total_cost < Decimal("0"))
        elif normalized_direction == "decrease":
            balance_query = balance_query.filter(ConsumptionRecord.total_cost > Decimal("0"))

        total = balance_query.count()
        rows = (
            balance_query
            .order_by(ConsumptionRecord.created_at.desc(), ConsumptionRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        order_nos = sorted({
            str(BalanceService._row_value(row, "request_id") or "").strip()
            for row in rows
            if str(BalanceService._row_value(row, "request_id") or "").strip()
        })
        order_map: dict[str, PaymentRechargeOrder] = {}
        if order_nos:
            orders = (
                db.query(PaymentRechargeOrder)
                .filter(
                    PaymentRechargeOrder.user_id == user_id,
                    PaymentRechargeOrder.status == "paid",
                    PaymentRechargeOrder.order_no.in_(order_nos),
                )
                .all()
            )
            order_map = {str(order.order_no): order for order in orders}

        return [BalanceService._serialize_asset_source_record(row, order_map) for row in rows], int(total)

    @staticmethod
    def get_consumption_records(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List consumption records for a user with pagination.

        Returns:
            Tuple of (list of record dicts, total count).
        """
        query = db.query(ConsumptionRecord).filter(ConsumptionRecord.user_id == user_id)

        total = query.count()
        records = (
            query.order_by(ConsumptionRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        request_ids = sorted({
            str(record.request_id).strip()
            for record in records
            if str(record.request_id or "").strip()
            and not str(record.model_name or "").strip()
        })
        request_model_map: dict[str, str] = {}
        if request_ids:
            log_rows = (
                db.query(RequestLog.request_id, RequestLog.requested_model)
                .filter(RequestLog.request_id.in_(request_ids))
                .all()
            )
            request_model_map = {
                str(request_id): str(requested_model or "").strip()
                for request_id, requested_model in log_rows
                if str(request_id or "").strip() and str(requested_model or "").strip()
            }

        result = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "request_id": r.request_id,
                "model_name": (
                    r.model_name
                    or request_model_map.get(str(r.request_id or "").strip())
                ),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "billable_input_tokens": r.billable_input_tokens or r.input_tokens or 0,
                "raw_input_tokens": r.raw_input_tokens or 0,
                "raw_output_tokens": r.raw_output_tokens or 0,
                "raw_total_tokens": r.raw_total_tokens or 0,
                "logical_input_tokens": r.logical_input_tokens or 0,
                "upstream_input_tokens": r.upstream_input_tokens or 0,
                "upstream_cache_read_input_tokens": r.upstream_cache_read_input_tokens or 0,
                "billable_cache_read_input_tokens": r.billable_cache_read_input_tokens or r.upstream_cache_read_input_tokens or 0,
                "upstream_cache_creation_input_tokens": r.upstream_cache_creation_input_tokens or 0,
                "upstream_prompt_cache_status": r.upstream_prompt_cache_status or "BYPASS",
                "input_cost": float(r.input_cost),
                "cache_read_cost": float(r.cache_read_cost or 0),
                "output_cost": float(r.output_cost),
                "total_cost": float(r.total_cost),
                "input_price_per_million_snapshot": float(r.input_price_per_million_snapshot or 0),
                "output_price_per_million_snapshot": float(r.output_price_per_million_snapshot or 0),
                "price_multiplier_snapshot": float(r.price_multiplier_snapshot or 1),
                "fast_price_multiplier_snapshot": float(r.fast_price_multiplier_snapshot or 1),
                "context_tokens_snapshot": int(r.context_tokens_snapshot or 0),
                "context_token_threshold_snapshot": int(r.context_token_threshold_snapshot or 262144),
                "context_price_multiplier_snapshot": float(r.context_price_multiplier_snapshot or 1),
                "effective_price_multiplier_snapshot": float(
                    (r.price_multiplier_snapshot or 1)
                    * (r.fast_price_multiplier_snapshot or 1)
                    * (r.context_price_multiplier_snapshot or 1)
                ),
                "service_tier": r.service_tier,
                "token_multiplier_snapshot": float(r.token_multiplier_snapshot or 1),
                "balance_before": float(r.balance_before),
                "balance_after": float(r.balance_after),
                "subscription_id": r.subscription_id,
                "subscription_cycle_id": r.subscription_cycle_id,
                "quota_metric": r.quota_metric,
                "quota_consumed_amount": float(r.quota_consumed_amount or 0),
                "quota_limit_snapshot": float(r.quota_limit_snapshot or 0),
                "quota_used_after": float(r.quota_used_after or 0),
                "quota_cycle_date": r.quota_cycle_date.isoformat() if r.quota_cycle_date else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
        return result, total
