"""Agent subscription sale records for online user purchases."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.agent import Agent, AgentSubscriptionSaleRecord
from app.models.payment import PaymentRechargeOrder
from app.models.user import SysUser
from app.services.payment_service import PaymentService


class AgentSubscriptionSaleService:
    """Offline-settled rebate records for agent users buying subscriptions online."""

    MONEY_SCALE = Decimal("0.01")

    @staticmethod
    def _normalize_money(value, code: str = "INVALID_SUBSCRIPTION_SALE_AMOUNT") -> Decimal:
        try:
            amount = Decimal(str(value or 0)).quantize(AgentSubscriptionSaleService.MONEY_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(500, "套餐销售金额格式不正确", code) from exc
        if amount < Decimal("0"):
            raise ServiceException(500, "套餐销售金额不能小于 0", code)
        return amount

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
    def _date_bounds(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
        start_dt = AgentSubscriptionSaleService._parse_date(start_date, "开始日期")
        end_dt = AgentSubscriptionSaleService._parse_date(end_date, "结束日期")
        upper_dt = end_dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1) if end_dt else None
        return start_dt, upper_dt

    @staticmethod
    def _serialize(
        row: AgentSubscriptionSaleRecord,
        user: SysUser | None = None,
        agent: Agent | None = None,
    ) -> dict:
        return {
            "id": row.id,
            "order_id": row.order_id,
            "order_no": row.order_no,
            "agent_id": row.agent_id,
            "agent_name": agent.agent_name if agent else None,
            "user_id": row.user_id,
            "username": user.username if user else None,
            "email": user.email if user else None,
            "subscription_id": row.subscription_id,
            "plan_id": row.plan_id,
            "plan_code_snapshot": row.plan_code_snapshot,
            "plan_name_snapshot": row.plan_name_snapshot,
            "plan_kind_snapshot": row.plan_kind_snapshot,
            "duration_days_snapshot": row.duration_days_snapshot,
            "sale_price_cny": float(row.sale_price_cny or 0),
            "agent_cost_price_cny": float(row.agent_cost_price_cny or 0),
            "agent_rebate_cny": float(row.agent_rebate_cny or 0),
            "payment_channel": row.payment_channel,
            "payment_channel_text": PaymentService._payment_channel_text(row.payment_channel),
            "payment_status": row.payment_status,
            "rebate_status": row.rebate_status,
            "settled_at": PaymentService._serialize_dt(row.settled_at, assume_utc=True),
            "settled_by": row.settled_by,
            "settlement_remark": row.settlement_remark,
            "created_at": PaymentService._serialize_dt(row.created_at, assume_utc=False),
            "updated_at": PaymentService._serialize_dt(row.updated_at, assume_utc=False),
        }

    @staticmethod
    def create_from_paid_order(db: Session, order: PaymentRechargeOrder) -> AgentSubscriptionSaleRecord | None:
        if not order.agent_id:
            return None
        if PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None)) != "subscription":
            return None

        existing = (
            db.query(AgentSubscriptionSaleRecord)
            .filter(AgentSubscriptionSaleRecord.order_no == order.order_no)
            .first()
        )
        if existing:
            return existing

        sale_price = AgentSubscriptionSaleService._normalize_money(order.subscription_sale_price_cny)
        cost_price = AgentSubscriptionSaleService._normalize_money(order.subscription_agent_cost_cny)
        rebate = AgentSubscriptionSaleService._normalize_money(order.subscription_agent_rebate_cny)
        if cost_price <= Decimal("0"):
            raise ServiceException(500, "套餐订单缺少代理拿货价", "SUBSCRIPTION_AGENT_COST_MISSING")
        if sale_price < cost_price:
            raise ServiceException(500, "套餐订单售价小于代理拿货价", "SUBSCRIPTION_REBATE_INVALID")

        record = AgentSubscriptionSaleRecord(
            order_id=order.id,
            order_no=order.order_no,
            agent_id=int(order.agent_id),
            user_id=int(order.user_id),
            subscription_id=order.subscription_id,
            plan_id=order.subscription_plan_id,
            plan_code_snapshot=order.plan_code_snapshot,
            plan_name_snapshot=order.plan_name_snapshot or "套餐",
            plan_kind_snapshot=order.plan_kind_snapshot,
            duration_days_snapshot=order.duration_days_snapshot,
            sale_price_cny=sale_price,
            agent_cost_price_cny=cost_price,
            agent_rebate_cny=rebate,
            payment_channel=order.payment_channel,
            payment_status=order.status,
            rebate_status="pending",
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def _apply_filters(
        query,
        db: Session,
        agent_id: int | None = None,
        user_id: int | None = None,
        rebate_status: str | None = None,
        payment_channel: str | None = None,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        if agent_id is not None:
            query = query.filter(AgentSubscriptionSaleRecord.agent_id == agent_id)
        if user_id is not None:
            query = query.filter(AgentSubscriptionSaleRecord.user_id == user_id)
        if rebate_status:
            query = query.filter(AgentSubscriptionSaleRecord.rebate_status == rebate_status)
        if payment_channel:
            query = query.filter(AgentSubscriptionSaleRecord.payment_channel == payment_channel)
        start_dt, end_dt = AgentSubscriptionSaleService._date_bounds(start_date, end_date)
        if start_dt:
            query = query.filter(AgentSubscriptionSaleRecord.created_at >= start_dt)
        if end_dt:
            query = query.filter(AgentSubscriptionSaleRecord.created_at < end_dt)

        if keyword:
            keyword_text = str(keyword).strip()
            like = f"%{keyword_text}%"
            user_ids = [
                int(item.id)
                for item in db.query(SysUser.id)
                .filter(or_(SysUser.username.like(like), SysUser.email.like(like)))
                .all()
            ]
            agent_ids = [
                int(item.id)
                for item in db.query(Agent.id)
                .filter(or_(Agent.agent_name.like(like), Agent.agent_code.like(like)))
                .all()
            ]
            filters = [
                AgentSubscriptionSaleRecord.order_no.like(like),
                AgentSubscriptionSaleRecord.plan_name_snapshot.like(like),
                AgentSubscriptionSaleRecord.plan_code_snapshot.like(like),
            ]
            if user_ids:
                filters.append(AgentSubscriptionSaleRecord.user_id.in_(user_ids))
            if agent_ids:
                filters.append(AgentSubscriptionSaleRecord.agent_id.in_(agent_ids))
            query = query.filter(or_(*filters))
        return query

    @staticmethod
    def list_sales(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        agent_id: int | None = None,
        user_id: int | None = None,
        rebate_status: str | None = None,
        payment_channel: str | None = None,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[dict], int]:
        query = AgentSubscriptionSaleService._apply_filters(
            db.query(AgentSubscriptionSaleRecord),
            db,
            agent_id=agent_id,
            user_id=user_id,
            rebate_status=rebate_status,
            payment_channel=payment_channel,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
        )
        total = query.count()
        rows = (
            query.order_by(AgentSubscriptionSaleRecord.id.desc())
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
        return [
            AgentSubscriptionSaleService._serialize(
                row,
                user=user_map.get(int(row.user_id)),
                agent=agent_map.get(int(row.agent_id)),
            )
            for row in rows
        ], total

    @staticmethod
    def get_summary(
        db: Session,
        agent_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        query = AgentSubscriptionSaleService._apply_filters(
            db.query(AgentSubscriptionSaleRecord),
            db,
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
        )
        row = (
            query.with_entities(
                func.count(AgentSubscriptionSaleRecord.id),
                func.coalesce(func.sum(AgentSubscriptionSaleRecord.sale_price_cny), 0),
                func.coalesce(func.sum(AgentSubscriptionSaleRecord.agent_cost_price_cny), 0),
                func.coalesce(func.sum(AgentSubscriptionSaleRecord.agent_rebate_cny), 0),
                func.coalesce(func.sum(case((AgentSubscriptionSaleRecord.rebate_status == "pending", AgentSubscriptionSaleRecord.agent_rebate_cny), else_=0)), 0),
                func.coalesce(func.sum(case((AgentSubscriptionSaleRecord.rebate_status == "settled", AgentSubscriptionSaleRecord.agent_rebate_cny), else_=0)), 0),
                func.coalesce(func.sum(case((AgentSubscriptionSaleRecord.rebate_status == "pending", 1), else_=0)), 0),
                func.coalesce(func.sum(case((AgentSubscriptionSaleRecord.rebate_status == "settled", 1), else_=0)), 0),
            )
            .first()
        )
        (
            total_count,
            total_sale_price_cny,
            total_agent_cost_price_cny,
            total_agent_rebate_cny,
            pending_rebate_cny,
            settled_rebate_cny,
            pending_count,
            settled_count,
        ) = row or (0, 0, 0, 0, 0, 0, 0, 0)
        return {
            "agent_id": agent_id,
            "total_count": int(total_count or 0),
            "total_sale_price_cny": float(total_sale_price_cny or 0),
            "total_agent_cost_price_cny": float(total_agent_cost_price_cny or 0),
            "total_agent_rebate_cny": float(total_agent_rebate_cny or 0),
            "pending_rebate_cny": float(pending_rebate_cny or 0),
            "settled_rebate_cny": float(settled_rebate_cny or 0),
            "pending_count": int(pending_count or 0),
            "settled_count": int(settled_count or 0),
        }

    @staticmethod
    def settle_sale(db: Session, sale_id: int, operator_user_id: int, remark: str | None = None) -> dict:
        record = (
            db.query(AgentSubscriptionSaleRecord)
            .filter(AgentSubscriptionSaleRecord.id == sale_id)
            .with_for_update()
            .first()
        )
        if not record:
            raise ServiceException(404, "代理套餐销售记录不存在", "SUBSCRIPTION_SALE_NOT_FOUND")
        if record.rebate_status == "settled":
            return AgentSubscriptionSaleService._serialize(record)
        if record.rebate_status != "pending":
            raise ServiceException(400, "当前销售记录状态不允许核销", "SUBSCRIPTION_SALE_STATUS_INVALID")
        record.rebate_status = "settled"
        record.settled_at = datetime.utcnow()
        record.settled_by = operator_user_id
        record.settlement_remark = remark
        db.commit()
        db.refresh(record)
        return AgentSubscriptionSaleService._serialize(record)

    @staticmethod
    def batch_settle_sales(db: Session, sale_ids: list[int], operator_user_id: int, remark: str | None = None) -> dict:
        unique_ids = sorted({int(item) for item in sale_ids if item})
        if not unique_ids:
            raise ServiceException(400, "请选择要核销的销售记录", "SUBSCRIPTION_SALE_IDS_REQUIRED")
        records = (
            db.query(AgentSubscriptionSaleRecord)
            .filter(AgentSubscriptionSaleRecord.id.in_(unique_ids))
            .with_for_update()
            .all()
        )
        if len(records) != len(unique_ids):
            raise ServiceException(404, "部分代理套餐销售记录不存在", "SUBSCRIPTION_SALE_NOT_FOUND")
        now = datetime.utcnow()
        settled_count = 0
        settled_amount = Decimal("0.00")
        for record in records:
            if record.rebate_status == "settled":
                continue
            if record.rebate_status != "pending":
                raise ServiceException(400, "存在不允许核销的销售记录", "SUBSCRIPTION_SALE_STATUS_INVALID")
            record.rebate_status = "settled"
            record.settled_at = now
            record.settled_by = operator_user_id
            record.settlement_remark = remark
            settled_count += 1
            settled_amount += AgentSubscriptionSaleService._normalize_money(record.agent_rebate_cny)
        db.commit()
        return {
            "settled_count": settled_count,
            "settled_amount": float(settled_amount),
        }
