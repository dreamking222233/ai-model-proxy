"""Agent cash balance and withdrawal service."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, or_
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


class AgentCashService:
    """Operations for agent RMB cash balance."""

    MONEY_SCALE = Decimal("0.01")

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
    def _serialize_order(order: PaymentRechargeOrder, user: SysUser | None = None, agent: Agent | None = None) -> dict:
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
            "amount_cny": float(order.amount_cny or 0),
            "credited_usd": float(order.credited_usd or 0),
            "agent_income_cny": float(order.agent_income_cny or 0),
            "status": order.status,
            "trade_status": order.trade_status,
            "subject": order.subject,
            "alipay_trade_no": order.alipay_trade_no,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
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
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
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
                func.coalesce(func.sum(PaymentRechargeOrder.agent_income_cny), 0).label("total_agent_income_cny"),
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
                "total_agent_income_cny": float(total_agent_income_cny or 0),
                "paid_order_count": int(paid_order_count or 0),
            }
            for agent_id, total_amount_cny, total_credited_usd, total_agent_income_cny, paid_order_count in order_rows
        }

        items = []
        for agent in agents:
            agent_id = int(agent.id)
            cash = AgentCashService._serialize_cash_balance(balance_map.get(agent_id))
            stats = order_map.get(agent_id, {
                "total_amount_cny": 0.0,
                "total_credited_usd": 0.0,
                "total_agent_income_cny": 0.0,
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
    ) -> tuple[list[dict], int]:
        query = db.query(PaymentRechargeOrder)
        if agent_id is not None:
            query = query.filter(PaymentRechargeOrder.agent_id == agent_id)
        if user_id is not None:
            query = query.filter(PaymentRechargeOrder.user_id == user_id)
        if status:
            query = query.filter(PaymentRechargeOrder.status == status)

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
                func.coalesce(func.sum(PaymentRechargeOrder.agent_income_cny), 0),
                func.count(PaymentRechargeOrder.id),
            )
            .filter(
                PaymentRechargeOrder.agent_id == agent_id,
                PaymentRechargeOrder.status == "paid",
            )
            .first()
        )
        total_amount_cny, total_credited_usd, total_agent_income_cny, paid_order_count = paid_rows or (0, 0, 0, 0)
        return {
            "agent_id": agent_id,
            **AgentCashService._serialize_cash_balance(balance),
            "total_amount_cny": float(total_amount_cny or 0),
            "total_credited_usd": float(total_credited_usd or 0),
            "total_agent_income_cny": float(total_agent_income_cny or 0),
            "paid_order_count": int(paid_order_count or 0),
        }
