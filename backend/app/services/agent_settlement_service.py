"""Agent daily credit limit and settlement ledger service."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.agent import (
    Agent,
    AgentBalance,
    AgentDailyLimit,
    AgentDailyLimitUsage,
    AgentImageBalance,
    AgentSettlementBatch,
    AgentSettlementBatchItem,
    AgentSettlementRecord,
    AgentSubscriptionInventory,
)
from app.models.log import SubscriptionPlan
from app.models.user import SysUser


class AgentSettlementService:
    """Operations for agent settlement-mode allocation and admin settlement."""

    RESOURCE_BALANCE = "balance"
    RESOURCE_IMAGE_CREDIT = "image_credit"
    RESOURCE_SUBSCRIPTION = "subscription"
    DEFAULT_TIMEZONE = "Asia/Shanghai"
    ACTIVE_STATUSES = {"pending", "partial"}

    @staticmethod
    def _normalize_decimal(value, code: str = "INVALID_DECIMAL") -> Decimal:
        try:
            amount = Decimal(str(value or 0)).quantize(Decimal("0.000001"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "数值格式不正确", code) from exc
        return amount

    @staticmethod
    def _positive_decimal(value, code: str = "INVALID_AMOUNT") -> Decimal:
        amount = AgentSettlementService._normalize_decimal(value, code)
        if amount <= Decimal("0"):
            raise ServiceException(400, "数量必须大于 0", code)
        return amount

    @staticmethod
    def _integer_decimal(value, code: str = "INVALID_INTEGER_AMOUNT") -> Decimal:
        amount = AgentSettlementService._normalize_decimal(value, code)
        if amount != amount.to_integral_value():
            raise ServiceException(400, "套餐数量必须是整数", code)
        return amount

    @staticmethod
    def _positive_resource_amount(resource_type: str, value, code: str = "INVALID_AMOUNT") -> Decimal:
        amount = AgentSettlementService._positive_decimal(value, code)
        if resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION:
            amount = AgentSettlementService._integer_decimal(amount, code)
        return amount

    @staticmethod
    def _plan_id_key(plan_id: Optional[int]) -> int:
        return int(plan_id or 0)

    @staticmethod
    def _validate_resource(resource_type: str, plan_id: Optional[int] = None) -> None:
        if resource_type not in {
            AgentSettlementService.RESOURCE_BALANCE,
            AgentSettlementService.RESOURCE_IMAGE_CREDIT,
            AgentSettlementService.RESOURCE_SUBSCRIPTION,
        }:
            raise ServiceException(400, "资源类型不合法", "INVALID_AGENT_SETTLEMENT_RESOURCE")
        if resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION and not plan_id:
            raise ServiceException(400, "套餐额度必须指定套餐模板", "AGENT_SETTLEMENT_PLAN_REQUIRED")
        if resource_type != AgentSettlementService.RESOURCE_SUBSCRIPTION and plan_id:
            raise ServiceException(400, "余额或图片积分额度不能指定套餐模板", "AGENT_SETTLEMENT_PLAN_NOT_ALLOWED")

    @staticmethod
    def get_today_date():
        return datetime.now(ZoneInfo(AgentSettlementService.DEFAULT_TIMEZONE)).date()

    @staticmethod
    def _parse_date(value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ServiceException(400, "日期格式不正确，应为 YYYY-MM-DD", "INVALID_DATE_FORMAT") from exc

    @staticmethod
    def _serialize_limit(limit: AgentDailyLimit, used_amount: Decimal | int | float = 0, plan: Optional[SubscriptionPlan] = None) -> dict:
        used = AgentSettlementService._normalize_decimal(used_amount)
        daily = AgentSettlementService._normalize_decimal(limit.daily_limit)
        remaining = daily - used if limit.status == "active" else Decimal("0")
        if remaining < Decimal("0"):
            remaining = Decimal("0")
        return {
            "id": limit.id,
            "agent_id": limit.agent_id,
            "resource_type": limit.resource_type,
            "plan_id": limit.plan_id,
            "plan_name": plan.plan_name if plan else None,
            "plan_code": plan.plan_code if plan else None,
            "daily_limit": float(daily),
            "used_amount": float(used),
            "remaining_amount": float(remaining),
            "status": limit.status,
            "created_at": limit.created_at.isoformat() if limit.created_at else None,
            "updated_at": limit.updated_at.isoformat() if limit.updated_at else None,
        }

    @staticmethod
    def _serialize_record(record: AgentSettlementRecord, agent: Optional[Agent] = None, user: Optional[SysUser] = None) -> dict:
        quantity = AgentSettlementService._normalize_decimal(record.quantity)
        settled = AgentSettlementService._normalize_decimal(record.settled_quantity)
        remaining = quantity - settled
        if remaining < Decimal("0"):
            remaining = Decimal("0")
        return {
            "id": record.id,
            "agent_id": record.agent_id,
            "agent_name": agent.agent_name if agent else None,
            "agent_code": agent.agent_code if agent else None,
            "target_user_id": record.target_user_id,
            "username": user.username if user else None,
            "business_date": record.business_date.isoformat() if record.business_date else None,
            "resource_type": record.resource_type,
            "plan_id": record.plan_id,
            "plan_code": record.plan_code_snapshot,
            "plan_name": record.plan_name_snapshot,
            "plan_kind": record.plan_kind_snapshot,
            "duration_days": record.duration_days_snapshot,
            "quota_metric": record.quota_metric_snapshot,
            "quota_value": float(record.quota_value_snapshot or 0),
            "quantity": float(quantity),
            "settled_quantity": float(settled),
            "remaining_quantity": float(remaining),
            "status": record.status,
            "source_action": record.source_action,
            "related_subscription_id": record.related_subscription_id,
            "operator_user_id": record.operator_user_id,
            "remark": record.remark,
            "settled_at": record.settled_at.isoformat() if record.settled_at else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    @staticmethod
    def list_limits(db: Session, agent_id: int) -> list[dict]:
        today = AgentSettlementService.get_today_date()
        rows = (
            db.query(AgentDailyLimit, SubscriptionPlan)
            .outerjoin(SubscriptionPlan, SubscriptionPlan.id == AgentDailyLimit.plan_id)
            .filter(AgentDailyLimit.agent_id == agent_id)
            .order_by(AgentDailyLimit.resource_type.asc(), AgentDailyLimit.plan_id_key.asc())
            .all()
        )
        result = []
        for limit, plan in rows:
            usage = db.query(AgentDailyLimitUsage).filter(
                AgentDailyLimitUsage.agent_id == agent_id,
                AgentDailyLimitUsage.usage_date == today,
                AgentDailyLimitUsage.resource_type == limit.resource_type,
                AgentDailyLimitUsage.plan_id_key == limit.plan_id_key,
            ).first()
            result.append(AgentSettlementService._serialize_limit(limit, usage.used_amount if usage else 0, plan))
        return result

    @staticmethod
    def _validate_limit_payload(
        db: Session,
        agent_id: int,
        resource_type: str,
        daily_limit,
        plan_id: Optional[int] = None,
        status: str = "active",
    ) -> tuple[Decimal, Optional[SubscriptionPlan]]:
        AgentSettlementService._validate_resource(resource_type, plan_id)
        if status not in {"active", "disabled"}:
            raise ServiceException(400, "额度状态不合法", "INVALID_AGENT_DAILY_LIMIT_STATUS")
        amount = AgentSettlementService._normalize_decimal(daily_limit, "INVALID_AGENT_DAILY_LIMIT")
        if amount < Decimal("0"):
            raise ServiceException(400, "每日额度不能小于 0", "INVALID_AGENT_DAILY_LIMIT")
        if resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION:
            amount = AgentSettlementService._integer_decimal(amount, "INVALID_AGENT_DAILY_LIMIT")
        if not db.query(Agent).filter(Agent.id == agent_id).first():
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")
        plan = None
        if resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
            if not plan:
                raise ServiceException(404, "套餐模板不存在", "PLAN_NOT_FOUND")
        return amount, plan

    @staticmethod
    def _upsert_limit_entity(
        db: Session,
        agent_id: int,
        resource_type: str,
        amount: Decimal,
        plan_id: Optional[int] = None,
        status: str = "active",
    ) -> AgentDailyLimit:
        plan_key = AgentSettlementService._plan_id_key(plan_id)
        limit = (
            db.query(AgentDailyLimit)
            .filter(
                AgentDailyLimit.agent_id == agent_id,
                AgentDailyLimit.resource_type == resource_type,
                AgentDailyLimit.plan_id_key == plan_key,
            )
            .with_for_update()
            .first()
        )
        if not limit:
            limit = AgentDailyLimit(
                agent_id=agent_id,
                resource_type=resource_type,
                plan_id=plan_id,
                plan_id_key=plan_key,
                daily_limit=amount,
                status=status,
            )
            db.add(limit)
        else:
            limit.daily_limit = amount
            limit.status = status
            limit.plan_id = plan_id
        db.flush()
        return limit

    @staticmethod
    def upsert_limit(
        db: Session,
        agent_id: int,
        resource_type: str,
        daily_limit,
        plan_id: Optional[int] = None,
        status: str = "active",
    ) -> dict:
        amount, plan = AgentSettlementService._validate_limit_payload(db, agent_id, resource_type, daily_limit, plan_id, status)
        limit = AgentSettlementService._upsert_limit_entity(db, agent_id, resource_type, amount, plan_id, status)
        db.commit()
        db.refresh(limit)
        return AgentSettlementService._serialize_limit(limit, plan=plan)

    @staticmethod
    def batch_upsert_limits(db: Session, agent_id: int, items: list[dict]) -> list[dict]:
        prepared = []
        for item in items:
            status = item.get("status") or "active"
            amount, plan = AgentSettlementService._validate_limit_payload(
                db,
                agent_id=agent_id,
                resource_type=item.get("resource_type"),
                daily_limit=item.get("daily_limit"),
                plan_id=item.get("plan_id"),
                status=status,
            )
            prepared.append((item, amount, plan, status))
        for item, amount, _plan, status in prepared:
            AgentSettlementService._upsert_limit_entity(
                db,
                agent_id=agent_id,
                resource_type=item.get("resource_type"),
                amount=amount,
                plan_id=item.get("plan_id"),
                status=status,
            )
        db.commit()
        result = []
        for item, _amount, plan, _status in prepared:
            plan_key = AgentSettlementService._plan_id_key(item.get("plan_id"))
            limit = db.query(AgentDailyLimit).filter(
                AgentDailyLimit.agent_id == agent_id,
                AgentDailyLimit.resource_type == item.get("resource_type"),
                AgentDailyLimit.plan_id_key == plan_key,
            ).first()
            result.append(AgentSettlementService._serialize_limit(limit, plan=plan))
        return result

    @staticmethod
    def check_and_consume_daily_limit(
        db: Session,
        agent_id: int,
        resource_type: str,
        amount,
        plan_id: Optional[int] = None,
    ) -> AgentDailyLimitUsage:
        AgentSettlementService._validate_resource(resource_type, plan_id)
        amount_decimal = AgentSettlementService._positive_resource_amount(resource_type, amount, "INVALID_AGENT_CREDIT_LIMIT_AMOUNT")
        plan_key = AgentSettlementService._plan_id_key(plan_id)
        today = AgentSettlementService.get_today_date()
        limit = (
            db.query(AgentDailyLimit)
            .filter(
                AgentDailyLimit.agent_id == agent_id,
                AgentDailyLimit.resource_type == resource_type,
                AgentDailyLimit.plan_id_key == plan_key,
                AgentDailyLimit.status == "active",
            )
            .with_for_update()
            .first()
        )
        if not limit or AgentSettlementService._normalize_decimal(limit.daily_limit) <= Decimal("0"):
            raise ServiceException(400, "当前代理未配置今日授信额度，请联系管理员配置", "AGENT_DAILY_LIMIT_NOT_CONFIGURED")

        usage = (
            db.query(AgentDailyLimitUsage)
            .filter(
                AgentDailyLimitUsage.agent_id == agent_id,
                AgentDailyLimitUsage.usage_date == today,
                AgentDailyLimitUsage.resource_type == resource_type,
                AgentDailyLimitUsage.plan_id_key == plan_key,
            )
            .with_for_update()
            .first()
        )
        if not usage:
            usage = AgentDailyLimitUsage(
                agent_id=agent_id,
                usage_date=today,
                resource_type=resource_type,
                plan_id=plan_id,
                plan_id_key=plan_key,
                used_amount=Decimal("0"),
            )
            db.add(usage)
            db.flush()

        used = AgentSettlementService._normalize_decimal(usage.used_amount)
        daily_limit = AgentSettlementService._normalize_decimal(limit.daily_limit)
        if used + amount_decimal > daily_limit:
            raise ServiceException(400, "当前代理今日授信额度不足，请联系管理员调整额度或次日再试", "AGENT_DAILY_LIMIT_INSUFFICIENT")
        usage.used_amount = used + amount_decimal
        db.flush()
        return usage

    @staticmethod
    def create_settlement_record(
        db: Session,
        agent_id: int,
        target_user_id: int,
        resource_type: str,
        quantity,
        source_action: str,
        operator_user_id: Optional[int] = None,
        plan: Optional[SubscriptionPlan] = None,
        related_subscription_id: Optional[int] = None,
        related_balance_record_id: Optional[int] = None,
        related_image_record_id: Optional[int] = None,
        remark: Optional[str] = None,
    ) -> AgentSettlementRecord:
        quantity_decimal = AgentSettlementService._positive_resource_amount(resource_type, quantity, "INVALID_AGENT_SETTLEMENT_QUANTITY")
        record = AgentSettlementRecord(
            agent_id=agent_id,
            target_user_id=target_user_id,
            business_date=AgentSettlementService.get_today_date(),
            resource_type=resource_type,
            plan_id=plan.id if plan else None,
            plan_code_snapshot=plan.plan_code if plan else None,
            plan_name_snapshot=plan.plan_name if plan else None,
            plan_kind_snapshot=plan.plan_kind if plan else None,
            duration_days_snapshot=plan.duration_days if plan else None,
            quota_metric_snapshot=plan.quota_metric if plan else None,
            quota_value_snapshot=plan.quota_value if plan else None,
            quantity=quantity_decimal,
            settled_quantity=Decimal("0"),
            status="pending",
            source_action=source_action,
            related_subscription_id=related_subscription_id,
            related_balance_record_id=related_balance_record_id,
            related_image_record_id=related_image_record_id,
            operator_user_id=operator_user_id,
            remark=remark,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def has_unsettled_credit_records(db: Session, agent_id: int, resource_type: str) -> bool:
        return db.query(AgentSettlementRecord.id).filter(
            AgentSettlementRecord.agent_id == agent_id,
            AgentSettlementRecord.resource_type == resource_type,
            AgentSettlementRecord.status.in_(AgentSettlementService.ACTIVE_STATUSES),
            AgentSettlementRecord.quantity > AgentSettlementRecord.settled_quantity,
        ).first() is not None

    @staticmethod
    def get_agent_today_quota_summary(db: Session, agent_id: int) -> dict:
        today_limits = AgentSettlementService.list_limits(db, agent_id)
        pending_rows = (
            db.query(
                AgentSettlementRecord.resource_type,
                AgentSettlementRecord.plan_id,
                func.coalesce(func.sum(AgentSettlementRecord.quantity - AgentSettlementRecord.settled_quantity), 0).label("pending_quantity"),
            )
            .filter(
                AgentSettlementRecord.agent_id == agent_id,
                AgentSettlementRecord.status.in_(AgentSettlementService.ACTIVE_STATUSES),
            )
            .group_by(AgentSettlementRecord.resource_type, AgentSettlementRecord.plan_id)
            .all()
        )
        pending_total = sum(float(row.pending_quantity or 0) for row in pending_rows)
        return {
            "business_date": AgentSettlementService.get_today_date().isoformat(),
            "daily_limits": today_limits,
            "pending_settlement_total": pending_total,
            "pending_settlement_items": [
                {
                    "resource_type": row.resource_type,
                    "plan_id": row.plan_id,
                    "pending_quantity": float(row.pending_quantity or 0),
                }
                for row in pending_rows
            ],
        }

    @staticmethod
    def list_admin_settlement_records(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        agent_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        query = (
            db.query(AgentSettlementRecord, Agent, SysUser)
            .join(Agent, Agent.id == AgentSettlementRecord.agent_id)
            .outerjoin(SysUser, SysUser.id == AgentSettlementRecord.target_user_id)
        )
        if agent_id:
            query = query.filter(AgentSettlementRecord.agent_id == agent_id)
        if resource_type:
            query = query.filter(AgentSettlementRecord.resource_type == resource_type)
        if status:
            query = query.filter(AgentSettlementRecord.status == status)
        start = AgentSettlementService._parse_date(start_date)
        end = AgentSettlementService._parse_date(end_date)
        if start:
            query = query.filter(AgentSettlementRecord.business_date >= start)
        if end:
            query = query.filter(AgentSettlementRecord.business_date <= end)

        total = query.count()
        rows = (
            query.order_by(AgentSettlementRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [AgentSettlementService._serialize_record(record, agent, user) for record, agent, user in rows], total

    @staticmethod
    def list_admin_settlement_summary(
        db: Session,
        agent_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        query = (
            db.query(
                AgentSettlementRecord.agent_id,
                Agent.agent_name,
                Agent.agent_code,
                AgentSettlementRecord.resource_type,
                AgentSettlementRecord.plan_id,
                AgentSettlementRecord.plan_name_snapshot,
                func.coalesce(func.sum(AgentSettlementRecord.quantity), 0).label("total_quantity"),
                func.coalesce(func.sum(AgentSettlementRecord.settled_quantity), 0).label("settled_quantity"),
                func.count(AgentSettlementRecord.id).label("record_count"),
            )
            .join(Agent, Agent.id == AgentSettlementRecord.agent_id)
        )
        if agent_id:
            query = query.filter(AgentSettlementRecord.agent_id == agent_id)
        if resource_type:
            query = query.filter(AgentSettlementRecord.resource_type == resource_type)
        if status:
            query = query.filter(AgentSettlementRecord.status == status)
        start = AgentSettlementService._parse_date(start_date)
        end = AgentSettlementService._parse_date(end_date)
        if start:
            query = query.filter(AgentSettlementRecord.business_date >= start)
        if end:
            query = query.filter(AgentSettlementRecord.business_date <= end)

        rows = (
            query.group_by(
                AgentSettlementRecord.agent_id,
                Agent.agent_name,
                Agent.agent_code,
                AgentSettlementRecord.resource_type,
                AgentSettlementRecord.plan_id,
                AgentSettlementRecord.plan_name_snapshot,
            )
            .order_by(AgentSettlementRecord.agent_id.desc())
            .all()
        )
        result = []
        for row in rows:
            total = AgentSettlementService._normalize_decimal(row.total_quantity)
            settled = AgentSettlementService._normalize_decimal(row.settled_quantity)
            pending = total - settled
            balance = db.query(AgentBalance).filter(AgentBalance.agent_id == row.agent_id).first()
            image_balance = db.query(AgentImageBalance).filter(AgentImageBalance.agent_id == row.agent_id).first()
            inventory_query = db.query(
                func.coalesce(func.sum(AgentSubscriptionInventory.remaining_count), 0).label("remaining_count"),
                func.coalesce(func.sum(AgentSubscriptionInventory.total_used), 0).label("used_count"),
            ).filter(AgentSubscriptionInventory.agent_id == row.agent_id)
            if row.resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION and row.plan_id:
                inventory_query = inventory_query.filter(AgentSubscriptionInventory.plan_id == row.plan_id)
            inventory = inventory_query.one()
            result.append({
                "agent_id": row.agent_id,
                "agent_name": row.agent_name,
                "agent_code": row.agent_code,
                "resource_type": row.resource_type,
                "plan_id": row.plan_id,
                "plan_name": row.plan_name_snapshot,
                "total_quantity": float(total),
                "settled_quantity": float(settled),
                "pending_quantity": float(max(Decimal("0"), pending)),
                "record_count": int(row.record_count or 0),
                "asset_balance": float(balance.balance) if balance else 0.0,
                "asset_balance_allocated": float(balance.total_allocated) if balance else 0.0,
                "asset_image_credit_balance": float(image_balance.balance) if image_balance else 0.0,
                "asset_image_credit_allocated": float(image_balance.total_allocated) if image_balance else 0.0,
                "asset_subscription_remaining": int(inventory.remaining_count or 0),
                "asset_subscription_used": int(inventory.used_count or 0),
            })
        return result

    @staticmethod
    def settle_records(
        db: Session,
        agent_id: int,
        resource_type: str,
        quantity,
        operator_user_id: int,
        plan_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        remark: Optional[str] = None,
    ) -> dict:
        quantity_decimal = AgentSettlementService._positive_resource_amount(resource_type, quantity, "INVALID_SETTLEMENT_QUANTITY")
        start = AgentSettlementService._parse_date(start_date)
        end = AgentSettlementService._parse_date(end_date)
        query = db.query(AgentSettlementRecord).filter(
            AgentSettlementRecord.agent_id == agent_id,
            AgentSettlementRecord.resource_type == resource_type,
            AgentSettlementRecord.status.in_(AgentSettlementService.ACTIVE_STATUSES),
            AgentSettlementRecord.quantity > AgentSettlementRecord.settled_quantity,
        )
        if plan_id:
            query = query.filter(AgentSettlementRecord.plan_id == plan_id)
        elif resource_type == AgentSettlementService.RESOURCE_SUBSCRIPTION:
            raise ServiceException(400, "结算套餐销售必须选择套餐模板", "SETTLEMENT_PLAN_REQUIRED")
        if start:
            query = query.filter(AgentSettlementRecord.business_date >= start)
        if end:
            query = query.filter(AgentSettlementRecord.business_date <= end)

        records = query.order_by(AgentSettlementRecord.created_at.asc(), AgentSettlementRecord.id.asc()).with_for_update().all()
        available = sum(
            AgentSettlementService._normalize_decimal(record.quantity) - AgentSettlementService._normalize_decimal(record.settled_quantity)
            for record in records
        )
        if available < quantity_decimal:
            raise ServiceException(400, "结算数量超过当前未结算数量", "SETTLEMENT_QUANTITY_EXCEEDS_PENDING")

        batch = AgentSettlementBatch(
            agent_id=agent_id,
            resource_type=resource_type,
            plan_id=plan_id,
            business_start_date=start,
            business_end_date=end,
            settled_quantity=quantity_decimal,
            operator_user_id=operator_user_id,
            remark=remark,
        )
        db.add(batch)
        db.flush()

        remaining_to_settle = quantity_decimal
        now = datetime.now(ZoneInfo(AgentSettlementService.DEFAULT_TIMEZONE)).replace(tzinfo=None)
        touched = []
        for record in records:
            if remaining_to_settle <= Decimal("0"):
                break
            record_remaining = AgentSettlementService._normalize_decimal(record.quantity) - AgentSettlementService._normalize_decimal(record.settled_quantity)
            consume = min(record_remaining, remaining_to_settle)
            record.settled_quantity = AgentSettlementService._normalize_decimal(record.settled_quantity) + consume
            record.status = "settled" if record.settled_quantity >= record.quantity else "partial"
            record.settled_at = now
            db.add(AgentSettlementBatchItem(
                batch_id=batch.id,
                settlement_record_id=record.id,
                settled_quantity=consume,
            ))
            touched.append(record.id)
            remaining_to_settle -= consume

        db.commit()
        return {
            "batch_id": batch.id,
            "agent_id": agent_id,
            "resource_type": resource_type,
            "plan_id": plan_id,
            "settled_quantity": float(quantity_decimal),
            "record_ids": touched,
        }
