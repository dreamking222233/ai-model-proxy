"""Agent cash balance and withdrawal service."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.agent import Agent
from app.models.payment import (
    AgentCashBalance,
    AgentCashLedger,
    AgentCashWithdrawal,
    PaymentRechargeOrder,
)
from app.models.user import SysUser
from app.services.payment_service import PaymentService


class AgentCashService:
    """Operations for agent RMB cash balance."""

    MONEY_SCALE = Decimal("0.01")

    @staticmethod
    def _parse_date(value: str | None, field_name: str) -> datetime | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d")
        except ValueError as exc:
            raise ServiceException(400, f"{field_name} 格式应为 YYYY-MM-DD", "INVALID_DATE_RANGE") from exc

    @staticmethod
    def _normalize_money(value, code: str = "INVALID_AGENT_CASH_AMOUNT", allow_negative: bool = False) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(AgentCashService.MONEY_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "金额格式不正确", code) from exc
        if not allow_negative and amount <= Decimal("0"):
            raise ServiceException(400, "金额必须大于 0", code)
        if allow_negative and amount == Decimal("0"):
            raise ServiceException(400, "金额不能为 0", code)
        return amount

    @staticmethod
    def _serialize_cash_balance(balance: AgentCashBalance | None) -> dict:
        if not balance:
            return {
                "balance": 0.0,
                "total_income": 0.0,
                "total_withdrawn": 0.0,
                "total_adjusted": 0.0,
            }
        return {
            "balance": float(balance.balance or 0),
            "total_income": float(balance.total_income or 0),
            "total_withdrawn": float(balance.total_withdrawn or 0),
            "total_adjusted": float(balance.total_adjusted or 0),
        }

    @staticmethod
    def _recharge_type(order: PaymentRechargeOrder) -> str:
        return PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None))

    @staticmethod
    def _recharge_type_text(recharge_type: str | None) -> str:
        return PaymentService._recharge_type_text(recharge_type)

    @staticmethod
    def _serialize_order(order: PaymentRechargeOrder, user: SysUser | None = None, agent: Agent | None = None) -> dict:
        customer_type = "agent" if order.agent_id else "platform"
        return {
            "id": order.id,
            "order_no": order.order_no,
            "user_id": order.user_id,
            "username": user.username if user else None,
            "agent_id": order.agent_id,
            "agent_name": agent.agent_name if agent else None,
            "site_scope": order.site_scope,
            "source_host": order.source_host,
            "payment_channel": order.payment_channel,
            "payment_channel_text": {"alipay": "支付宝", "wechat": "微信"}.get(order.payment_channel, order.payment_channel or "-"),
            "recharge_type": AgentCashService._recharge_type(order),
            "recharge_type_text": AgentCashService._recharge_type_text(getattr(order, "recharge_type", None)),
            "customer_type": customer_type,
            "customer_type_text": "代理客户" if customer_type == "agent" else "直属用户",
            "amount_cny": float(order.amount_cny or 0),
            "credited_usd": float(order.credited_usd or 0),
            "credited_image_credits": float(order.credited_image_credits or 0),
            "agent_income_cny": float(order.agent_income_cny or 0),
            "status": order.status,
            "trade_status": order.trade_status,
            "subject": order.subject,
            "alipay_trade_no": order.alipay_trade_no,
            "wechat_transaction_id": order.wechat_transaction_id,
            "channel_trade_no": order.alipay_trade_no if order.payment_channel == "alipay" else order.wechat_transaction_id,
            "paid_at": PaymentService._serialize_dt(order.paid_at, assume_utc=True),
            "created_at": PaymentService._serialize_dt(order.created_at, assume_utc=False),
        }

    @staticmethod
    def _serialize_withdrawal(row: AgentCashWithdrawal, agent: Agent | None = None) -> dict:
        return {
            "id": row.id,
            "agent_id": row.agent_id,
            "agent_name": agent.agent_name if agent else None,
            "amount": float(row.amount or 0),
            "status": row.status,
            "transfer_method": row.transfer_method,
            "operator_user_id": row.operator_user_id,
            "remark": row.remark,
            "completed_at": PaymentService._serialize_dt(row.completed_at, assume_utc=True),
            "created_at": PaymentService._serialize_dt(row.created_at, assume_utc=False),
        }

    @staticmethod
    def _get_agent_or_raise(db: Session, agent_id: int) -> Agent:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")
        return agent

    @staticmethod
    def get_or_create_cash_balance_for_update(db: Session, agent_id: int) -> AgentCashBalance:
        balance = (
            db.query(AgentCashBalance)
            .filter(AgentCashBalance.agent_id == agent_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = AgentCashBalance(
                agent_id=agent_id,
                balance=0,
                total_income=0,
                total_withdrawn=0,
                total_adjusted=0,
            )
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
    def list_admin_summary(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[dict], int]:
        query = db.query(Agent)
        if keyword:
            like = f"%{str(keyword).strip()}%"
            query = query.filter(or_(
                Agent.agent_code.like(like),
                Agent.agent_name.like(like),
                Agent.frontend_domain.like(like),
                Agent.api_domain.like(like),
            ))
        total = query.count()
        agents = (
            query.order_by(Agent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        if not agents:
            return [], total

        agent_ids = [int(item.id) for item in agents]
        balance_rows = db.query(AgentCashBalance).filter(AgentCashBalance.agent_id.in_(agent_ids)).all()
        balance_map = {int(row.agent_id): row for row in balance_rows}

        order_rows = (
            db.query(
                PaymentRechargeOrder.agent_id,
                func.coalesce(func.sum(PaymentRechargeOrder.amount_cny), 0).label("total_amount_cny"),
                func.coalesce(func.sum(PaymentRechargeOrder.credited_usd), 0).label("total_credited_usd"),
                func.coalesce(func.sum(PaymentRechargeOrder.credited_image_credits), 0).label("total_credited_image_credits"),
                func.coalesce(func.sum(PaymentRechargeOrder.agent_income_cny), 0).label("total_agent_income_cny"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.amount_cny), else_=0)), 0).label("balance_amount_cny"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.credited_usd), else_=0)), 0).label("balance_credited_usd"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.agent_income_cny), else_=0)), 0).label("balance_agent_income_cny"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.amount_cny), else_=0)), 0).label("image_credit_amount_cny"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.credited_image_credits), else_=0)), 0).label("image_credit_credited_amount"),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.agent_income_cny), else_=0)), 0).label("image_credit_agent_income_cny"),
                func.count(PaymentRechargeOrder.id).label("paid_order_count"),
            )
            .filter(
                PaymentRechargeOrder.agent_id.in_(agent_ids),
                PaymentRechargeOrder.status == "paid",
            )
            .group_by(PaymentRechargeOrder.agent_id)
            .all()
        )
        order_map = {
            int(agent_id): {
                "total_amount_cny": float(total_amount_cny or 0),
                "total_credited_usd": float(total_credited_usd or 0),
                "total_credited_image_credits": float(total_credited_image_credits or 0),
                "total_agent_income_cny": float(total_agent_income_cny or 0),
                "balance_amount_cny": float(balance_amount_cny or 0),
                "balance_credited_usd": float(balance_credited_usd or 0),
                "balance_agent_income_cny": float(balance_agent_income_cny or 0),
                "image_credit_amount_cny": float(image_credit_amount_cny or 0),
                "image_credit_credited_amount": float(image_credit_credited_amount or 0),
                "image_credit_agent_income_cny": float(image_credit_agent_income_cny or 0),
                "paid_order_count": int(paid_order_count or 0),
            }
            for (
                agent_id,
                total_amount_cny,
                total_credited_usd,
                total_credited_image_credits,
                total_agent_income_cny,
                balance_amount_cny,
                balance_credited_usd,
                balance_agent_income_cny,
                image_credit_amount_cny,
                image_credit_credited_amount,
                image_credit_agent_income_cny,
                paid_order_count,
            ) in order_rows
        }

        items = []
        for agent in agents:
            agent_id = int(agent.id)
            cash = AgentCashService._serialize_cash_balance(balance_map.get(agent_id))
            stats = order_map.get(agent_id, {
                "total_amount_cny": 0.0,
                "total_credited_usd": 0.0,
                "total_credited_image_credits": 0.0,
                "total_agent_income_cny": 0.0,
                "balance_amount_cny": 0.0,
                "balance_credited_usd": 0.0,
                "balance_agent_income_cny": 0.0,
                "image_credit_amount_cny": 0.0,
                "image_credit_credited_amount": 0.0,
                "image_credit_agent_income_cny": 0.0,
                "paid_order_count": 0,
            })
            items.append({
                "agent_id": agent_id,
                "agent_code": agent.agent_code,
                "agent_name": agent.agent_name,
                "frontend_domain": agent.frontend_domain,
                "api_domain": agent.api_domain,
                **cash,
                **stats,
            })
        return items, total

    @staticmethod
    def list_recharge_orders(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        agent_id: int | None = None,
        user_id: int | None = None,
        status: str | None = None,
        payment_channel: str | None = None,
        recharge_type: str | None = None,
        site_scope: str | None = None,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        time_field: str | None = "created_at",
        agent_keyword: str | None = None,
        source_host: str | None = None,
    ) -> tuple[list[dict], int]:
        query = db.query(PaymentRechargeOrder)
        if agent_id is not None:
            query = query.filter(PaymentRechargeOrder.agent_id == agent_id)
        if user_id is not None:
            query = query.filter(PaymentRechargeOrder.user_id == user_id)
        if status:
            query = query.filter(PaymentRechargeOrder.status == status)
        if payment_channel:
            query = query.filter(PaymentRechargeOrder.payment_channel == payment_channel)
        if recharge_type:
            normalized_type = PaymentService._normalize_recharge_type(recharge_type)
            query = query.filter(PaymentRechargeOrder.recharge_type == normalized_type)
        if site_scope == "platform":
            query = query.filter(PaymentRechargeOrder.agent_id.is_(None))
        elif site_scope == "agent":
            query = query.filter(PaymentRechargeOrder.agent_id.is_not(None))

        if source_host:
            query = query.filter(PaymentRechargeOrder.source_host.like(f"%{str(source_host).strip()}%"))

        if agent_keyword:
            like = f"%{str(agent_keyword).strip()}%"
            matched_agent_ids = [
                int(item.id)
                for item in db.query(Agent.id)
                .filter(
                    or_(
                        Agent.agent_name.like(like),
                        Agent.agent_code.like(like),
                        Agent.frontend_domain.like(like),
                        Agent.api_domain.like(like),
                    )
                )
                .all()
            ]
            if not matched_agent_ids:
                return [], 0
            query = query.filter(PaymentRechargeOrder.agent_id.in_(matched_agent_ids))

        date_field = PaymentRechargeOrder.paid_at if str(time_field or "created_at").strip() == "paid_at" else PaymentRechargeOrder.created_at
        start_dt = AgentCashService._parse_date(start_date, "开始日期")
        end_dt = AgentCashService._parse_date(end_date, "结束日期")
        if start_dt:
            query = query.filter(date_field >= start_dt)
        if end_dt:
            query = query.filter(date_field < (end_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)))

        if keyword:
            keyword_text = str(keyword).strip()
            like = f"%{keyword_text}%"
            matched_user_ids = [
                int(item.id)
                for item in db.query(SysUser.id)
                .filter(SysUser.username.like(like))
                .all()
            ]
            matched_agent_ids = [
                int(item.id)
                for item in db.query(Agent.id)
                .filter(
                    or_(
                        Agent.agent_name.like(like),
                        Agent.agent_code.like(like),
                        Agent.frontend_domain.like(like),
                        Agent.api_domain.like(like),
                    )
                )
                .all()
            ]
            filters = [
                PaymentRechargeOrder.order_no.like(like),
                PaymentRechargeOrder.alipay_trade_no.like(like),
                PaymentRechargeOrder.wechat_transaction_id.like(like),
                PaymentRechargeOrder.source_host.like(like),
            ]
            if matched_user_ids:
                filters.append(PaymentRechargeOrder.user_id.in_(matched_user_ids))
            if matched_agent_ids:
                filters.append(PaymentRechargeOrder.agent_id.in_(matched_agent_ids))
            query = query.filter(or_(*filters))

        total = query.count()
        rows = (
            query.order_by(PaymentRechargeOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        if not rows:
            return [], total

        user_ids = sorted({int(row.user_id) for row in rows if row.user_id})
        agent_ids = sorted({int(row.agent_id) for row in rows if row.agent_id})
        user_map = {int(user.id): user for user in db.query(SysUser).filter(SysUser.id.in_(user_ids)).all()} if user_ids else {}
        agent_map = {int(agent.id): agent for agent in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()} if agent_ids else {}
        items = [
            AgentCashService._serialize_order(
                row,
                user=user_map.get(int(row.user_id)),
                agent=agent_map.get(int(row.agent_id)) if row.agent_id else None,
            )
            for row in rows
        ]
        return items, total

    @staticmethod
    def list_withdrawals(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        agent_id: int | None = None,
    ) -> tuple[list[dict], int]:
        query = db.query(AgentCashWithdrawal)
        if agent_id is not None:
            query = query.filter(AgentCashWithdrawal.agent_id == agent_id)
        total = query.count()
        rows = (
            query.order_by(AgentCashWithdrawal.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        if not rows:
            return [], total

        agent_ids = sorted({int(row.agent_id) for row in rows if row.agent_id})
        agent_map = {int(agent.id): agent for agent in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()} if agent_ids else {}
        items = [AgentCashService._serialize_withdrawal(row, agent_map.get(int(row.agent_id))) for row in rows]
        return items, total

    @staticmethod
    def adjust_agent_cash_balance(
        db: Session,
        agent_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        AgentCashService._get_agent_or_raise(db, agent_id)
        amount_decimal = AgentCashService._normalize_money(amount, allow_negative=True)
        balance = AgentCashService.get_or_create_cash_balance_for_update(db, agent_id)
        balance_before = Decimal(str(balance.balance or 0))
        balance_after = balance_before + amount_decimal
        if balance_after < Decimal("0"):
            raise ServiceException(400, "代理现金余额不足，无法扣减", "AGENT_CASH_INSUFFICIENT")

        balance.balance = balance_after
        balance.total_adjusted = Decimal(str(balance.total_adjusted or 0)) + amount_decimal
        db.add(AgentCashLedger(
            agent_id=agent_id,
            order_id=None,
            withdrawal_id=None,
            action_type="manual_adjust",
            change_amount=amount_decimal,
            balance_before=balance_before,
            balance_after=balance_after,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(balance)
        return {
            "agent_id": agent_id,
            **AgentCashService._serialize_cash_balance(balance),
            "adjusted_amount": float(amount_decimal),
        }

    @staticmethod
    def withdraw_agent_cash(
        db: Session,
        agent_id: int,
        amount,
        transfer_method: str = "offline_other",
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        AgentCashService._get_agent_or_raise(db, agent_id)
        amount_decimal = AgentCashService._normalize_money(amount)
        balance = AgentCashService.get_or_create_cash_balance_for_update(db, agent_id)
        balance_before = Decimal(str(balance.balance or 0))
        if balance_before < amount_decimal:
            raise ServiceException(400, "代理现金余额不足，无法提现", "AGENT_CASH_INSUFFICIENT")

        withdrawal = AgentCashWithdrawal(
            agent_id=agent_id,
            amount=amount_decimal,
            status="completed",
            transfer_method=str(transfer_method or "offline_other"),
            operator_user_id=operator_user_id,
            remark=remark,
            completed_at=datetime.utcnow(),
        )
        db.add(withdrawal)
        db.flush()

        balance.balance = balance_before - amount_decimal
        balance.total_withdrawn = Decimal(str(balance.total_withdrawn or 0)) + amount_decimal

        db.add(AgentCashLedger(
            agent_id=agent_id,
            order_id=None,
            withdrawal_id=withdrawal.id,
            action_type="withdraw",
            change_amount=-amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(balance)
        return {
            "agent_id": agent_id,
            "withdrawal_id": withdrawal.id,
            "amount": float(amount_decimal),
            **AgentCashService._serialize_cash_balance(balance),
        }

    @staticmethod
    def get_agent_summary(db: Session, agent_id: int) -> dict:
        AgentCashService._get_agent_or_raise(db, agent_id)
        balance = db.query(AgentCashBalance).filter(AgentCashBalance.agent_id == agent_id).first()
        paid_rows = (
            db.query(
                func.coalesce(func.sum(PaymentRechargeOrder.amount_cny), 0),
                func.coalesce(func.sum(PaymentRechargeOrder.credited_usd), 0),
                func.coalesce(func.sum(PaymentRechargeOrder.credited_image_credits), 0),
                func.coalesce(func.sum(PaymentRechargeOrder.agent_income_cny), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.amount_cny), else_=0)), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.credited_usd), else_=0)), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "balance", PaymentRechargeOrder.agent_income_cny), else_=0)), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.amount_cny), else_=0)), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.credited_image_credits), else_=0)), 0),
                func.coalesce(func.sum(case((PaymentRechargeOrder.recharge_type == "image_credit", PaymentRechargeOrder.agent_income_cny), else_=0)), 0),
                func.count(PaymentRechargeOrder.id),
            )
            .filter(
                PaymentRechargeOrder.agent_id == agent_id,
                PaymentRechargeOrder.status == "paid",
            )
            .first()
        )
        (
            total_amount_cny,
            total_credited_usd,
            total_credited_image_credits,
            total_agent_income_cny,
            balance_amount_cny,
            balance_credited_usd,
            balance_agent_income_cny,
            image_credit_amount_cny,
            image_credit_credited_amount,
            image_credit_agent_income_cny,
            paid_order_count,
        ) = paid_rows or (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return {
            "agent_id": agent_id,
            **AgentCashService._serialize_cash_balance(balance),
            "total_amount_cny": float(total_amount_cny or 0),
            "total_credited_usd": float(total_credited_usd or 0),
            "total_credited_image_credits": float(total_credited_image_credits or 0),
            "total_agent_income_cny": float(total_agent_income_cny or 0),
            "balance_amount_cny": float(balance_amount_cny or 0),
            "balance_credited_usd": float(balance_credited_usd or 0),
            "balance_agent_income_cny": float(balance_agent_income_cny or 0),
            "image_credit_amount_cny": float(image_credit_amount_cny or 0),
            "image_credit_credited_amount": float(image_credit_credited_amount or 0),
            "image_credit_agent_income_cny": float(image_credit_agent_income_cny or 0),
            "paid_order_count": int(paid_order_count or 0),
        }
