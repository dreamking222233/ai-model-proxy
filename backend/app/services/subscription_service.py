"""Subscription management service."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ServiceException
from app.models.log import (
    ConsumptionRecord,
    SubscriptionPlan,
    SubscriptionUsageCycle,
    UserSubscription,
)
from app.models.user import SysUser


class SubscriptionService:
    """User subscription management operations."""

    PLAN_KIND_UNLIMITED = "unlimited"
    PLAN_KIND_DAILY_QUOTA = "daily_quota"
    QUOTA_METRIC_TOKENS = "total_tokens"
    QUOTA_METRIC_COST = "cost_usd"
    DEFAULT_TIMEZONE = "Asia/Shanghai"
    DEFAULT_RESET_PERIOD = "day"

    BUILTIN_PLANS = [
        {
            "plan_code": "daily-unlimited",
            "plan_name": "日度无限包",
            "plan_kind": PLAN_KIND_UNLIMITED,
            "duration_mode": "day",
            "duration_days": 1,
            "quota_metric": None,
            "quota_value": Decimal("0"),
            "sort_order": 10,
            "description": "1 天无限额度套餐",
        },
        {
            "plan_code": "weekly-unlimited",
            "plan_name": "周度无限包",
            "plan_kind": PLAN_KIND_UNLIMITED,
            "duration_mode": "custom",
            "duration_days": 7,
            "quota_metric": None,
            "quota_value": Decimal("0"),
            "sort_order": 20,
            "description": "7 天无限额度套餐",
        },
        {
            "plan_code": "monthly-unlimited",
            "plan_name": "月度无限包",
            "plan_kind": PLAN_KIND_UNLIMITED,
            "duration_mode": "month",
            "duration_days": 30,
            "quota_metric": None,
            "quota_value": Decimal("0"),
            "sort_order": 30,
            "description": "30 天无限额度套餐",
        },
        {
            "plan_code": "daily-10m-token",
            "plan_name": "日度畅享包",
            "plan_kind": PLAN_KIND_DAILY_QUOTA,
            "duration_mode": "day",
            "duration_days": 1,
            "quota_metric": QUOTA_METRIC_TOKENS,
            "quota_value": Decimal("10000000"),
            "sort_order": 40,
            "description": "1 天有效，每天 1000 万 Token",
        },
        {
            "plan_code": "weekly-10m-token",
            "plan_name": "周度畅享包",
            "plan_kind": PLAN_KIND_DAILY_QUOTA,
            "duration_mode": "custom",
            "duration_days": 7,
            "quota_metric": QUOTA_METRIC_TOKENS,
            "quota_value": Decimal("10000000"),
            "sort_order": 50,
            "description": "7 天有效，每天 1000 万 Token",
        },
        {
            "plan_code": "monthly-10m-token",
            "plan_name": "月度畅享包",
            "plan_kind": PLAN_KIND_DAILY_QUOTA,
            "duration_mode": "month",
            "duration_days": 30,
            "quota_metric": QUOTA_METRIC_TOKENS,
            "quota_value": Decimal("10000000"),
            "sort_order": 60,
            "description": "30 天有效，每天 1000 万 Token",
        },
    ]

    @staticmethod
    def _normalize_decimal(value, default: str = "0") -> Decimal:
        if value is None or value == "":
            return Decimal(default)
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ServiceException(400, "Invalid decimal value", "INVALID_DECIMAL") from exc

    @staticmethod
    def _empty_usage_summary() -> dict:
        return {
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    @staticmethod
    def _active_status_filter():
        return or_(
            UserSubscription.status == "active",
            UserSubscription.status.is_(None),
            UserSubscription.status == "",
        )

    @staticmethod
    def _normalized_subscription_status(
        subscription: UserSubscription,
        now: Optional[datetime] = None,
    ) -> str:
        usage_now = now or SubscriptionService.get_current_time()
        raw_status = (subscription.status or "").strip().lower()
        if raw_status == "cancelled":
            return "cancelled"
        if subscription.end_time and subscription.end_time < usage_now:
            return "expired"
        return "active"

    @staticmethod
    def _is_effectively_active(
        subscription: UserSubscription,
        now: Optional[datetime] = None,
    ) -> bool:
        usage_now = now or SubscriptionService.get_current_time()
        return (
            SubscriptionService._normalized_subscription_status(subscription, usage_now) == "active"
            and subscription.start_time <= usage_now <= subscription.end_time
        )

    @staticmethod
    def _default_subscription_summary() -> dict:
        return {
            "subscription_type": "balance",
            "plan_name": None,
            "plan_code": None,
            "plan_kind": None,
            "start_time": None,
            "end_time": None,
            "quota_metric": None,
            "quota_value": 0.0,
            "current_cycle": None,
        }

    @staticmethod
    def _resolve_zoneinfo(tz_name: Optional[str]) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name or SubscriptionService.DEFAULT_TIMEZONE)
        except Exception:
            return ZoneInfo(SubscriptionService.DEFAULT_TIMEZONE)

    @staticmethod
    def get_current_time(tz_name: Optional[str] = None) -> datetime:
        zone = SubscriptionService._resolve_zoneinfo(tz_name or SubscriptionService.DEFAULT_TIMEZONE)
        return datetime.now(zone).replace(tzinfo=None)

    @staticmethod
    def _get_cycle_window(
        now_local: datetime,
        tz_name: Optional[str],
    ) -> tuple[date, datetime, datetime]:
        storage_zone = SubscriptionService._resolve_zoneinfo(SubscriptionService.DEFAULT_TIMEZONE)
        zone = SubscriptionService._resolve_zoneinfo(tz_name)
        aware_now = now_local.replace(tzinfo=storage_zone)
        target_now = aware_now.astimezone(zone)
        target_start = target_now.replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = target_start + timedelta(days=1)
        start_local = target_start.astimezone(storage_zone).replace(tzinfo=None)
        end_local = target_end.astimezone(storage_zone).replace(tzinfo=None)
        return target_now.date(), start_local, end_local

    @staticmethod
    def _validate_plan_payload(data: dict, is_update: bool = False) -> dict:
        payload = dict(data)
        plan_kind = str(payload.get("plan_kind") or "").strip() or None
        if not is_update or plan_kind is not None:
            if plan_kind not in {SubscriptionService.PLAN_KIND_UNLIMITED, SubscriptionService.PLAN_KIND_DAILY_QUOTA}:
                raise ServiceException(400, "Invalid plan kind", "INVALID_PLAN_KIND")

        duration_days = payload.get("duration_days")
        if duration_days is not None and int(duration_days) <= 0:
            raise ServiceException(400, "Duration must be positive", "INVALID_DURATION")

        quota_metric = payload.get("quota_metric")
        quota_value = payload.get("quota_value")
        effective_plan_kind = plan_kind

        if effective_plan_kind == SubscriptionService.PLAN_KIND_UNLIMITED:
            payload["quota_metric"] = None
            payload["quota_value"] = Decimal("0")
        elif effective_plan_kind == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            if quota_metric not in {SubscriptionService.QUOTA_METRIC_TOKENS, SubscriptionService.QUOTA_METRIC_COST}:
                raise ServiceException(400, "Invalid quota metric", "INVALID_QUOTA_METRIC")
            normalized_quota = SubscriptionService._normalize_decimal(quota_value)
            if normalized_quota <= 0:
                raise ServiceException(400, "Quota value must be positive", "INVALID_QUOTA_VALUE")
            payload["quota_value"] = normalized_quota

        if "status" in payload and payload["status"] not in {"active", "inactive"}:
            raise ServiceException(400, "Invalid plan status", "INVALID_PLAN_STATUS")

        if "reset_period" not in payload or not payload.get("reset_period"):
            payload["reset_period"] = SubscriptionService.DEFAULT_RESET_PERIOD
        if "reset_timezone" not in payload or not payload.get("reset_timezone"):
            payload["reset_timezone"] = SubscriptionService.DEFAULT_TIMEZONE

        return payload

    @staticmethod
    def ensure_default_plans(db: Session) -> None:
        existing_count = db.query(func.count(SubscriptionPlan.id)).scalar() or 0
        if existing_count > 0:
            return

        for plan_data in SubscriptionService.BUILTIN_PLANS:
            db.add(
                SubscriptionPlan(
                    plan_code=plan_data["plan_code"],
                    plan_name=plan_data["plan_name"],
                    plan_kind=plan_data["plan_kind"],
                    duration_mode=plan_data["duration_mode"],
                    duration_days=plan_data["duration_days"],
                    quota_metric=plan_data["quota_metric"],
                    quota_value=plan_data["quota_value"],
                    reset_period=SubscriptionService.DEFAULT_RESET_PERIOD,
                    reset_timezone=SubscriptionService.DEFAULT_TIMEZONE,
                    sort_order=plan_data["sort_order"],
                    status="active",
                    description=plan_data["description"],
                )
            )
        db.commit()

    @staticmethod
    def _serialize_plan(plan: SubscriptionPlan) -> dict:
        return {
            "id": plan.id,
            "plan_code": plan.plan_code,
            "plan_name": plan.plan_name,
            "plan_kind": plan.plan_kind,
            "duration_mode": plan.duration_mode,
            "duration_days": plan.duration_days,
            "quota_metric": plan.quota_metric,
            "quota_value": float(plan.quota_value or 0),
            "reset_period": plan.reset_period,
            "reset_timezone": plan.reset_timezone,
            "sort_order": plan.sort_order,
            "status": plan.status,
            "description": plan.description,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }

    @staticmethod
    def list_plans(
        db: Session,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        SubscriptionService.ensure_default_plans(db)
        query = db.query(SubscriptionPlan)
        if status:
            query = query.filter(SubscriptionPlan.status == status)
        total = query.count()
        plans = (
            query.order_by(SubscriptionPlan.sort_order.asc(), SubscriptionPlan.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [SubscriptionService._serialize_plan(plan) for plan in plans], total

    @staticmethod
    def create_plan(db: Session, data: dict) -> dict:
        payload = SubscriptionService._validate_plan_payload(data)
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == payload["plan_code"]).first()
        if existing:
            raise ServiceException(400, "Plan code already exists", "DUPLICATE_PLAN_CODE")

        plan = SubscriptionPlan(
            plan_code=payload["plan_code"],
            plan_name=payload["plan_name"],
            plan_kind=payload["plan_kind"],
            duration_mode=payload.get("duration_mode") or "custom",
            duration_days=int(payload["duration_days"]),
            quota_metric=payload.get("quota_metric"),
            quota_value=payload.get("quota_value") or Decimal("0"),
            reset_period=payload.get("reset_period") or SubscriptionService.DEFAULT_RESET_PERIOD,
            reset_timezone=payload.get("reset_timezone") or SubscriptionService.DEFAULT_TIMEZONE,
            sort_order=int(payload.get("sort_order") or 0),
            status=payload.get("status") or "active",
            description=payload.get("description"),
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return SubscriptionService._serialize_plan(plan)

    @staticmethod
    def update_plan(db: Session, plan_id: int, data: dict) -> dict:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise ServiceException(404, "Plan not found", "PLAN_NOT_FOUND")

        payload = SubscriptionService._validate_plan_payload(data, is_update=True)
        if "plan_code" in payload and payload["plan_code"] != plan.plan_code:
            duplicate = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == payload["plan_code"]).first()
            if duplicate:
                raise ServiceException(400, "Plan code already exists", "DUPLICATE_PLAN_CODE")

        for field in (
            "plan_code",
            "plan_name",
            "plan_kind",
            "duration_mode",
            "duration_days",
            "quota_metric",
            "quota_value",
            "reset_period",
            "reset_timezone",
            "sort_order",
            "status",
            "description",
        ):
            if field in payload and payload[field] is not None:
                setattr(plan, field, payload[field])

        db.commit()
        db.refresh(plan)
        return SubscriptionService._serialize_plan(plan)

    @staticmethod
    def _serialize_cycle(cycle: Optional[SubscriptionUsageCycle], quota_limit: Decimal | None = None) -> Optional[dict]:
        if cycle is None:
            return None
        limit_value = SubscriptionService._normalize_decimal(quota_limit if quota_limit is not None else cycle.quota_limit)
        used_value = SubscriptionService._normalize_decimal(cycle.used_amount)
        remaining_value = max(Decimal("0"), limit_value - used_value)
        return {
            "id": cycle.id,
            "cycle_date": cycle.cycle_date.isoformat() if cycle.cycle_date else None,
            "cycle_start_at": cycle.cycle_start_at.isoformat() if cycle.cycle_start_at else None,
            "cycle_end_at": cycle.cycle_end_at.isoformat() if cycle.cycle_end_at else None,
            "quota_metric": cycle.quota_metric,
            "quota_limit": float(limit_value),
            "used_amount": float(used_value),
            "remaining_amount": float(remaining_value),
            "request_count": int(cycle.request_count or 0),
            "last_request_id": cycle.last_request_id,
        }

    @staticmethod
    def _serialize_subscription(
        subscription: UserSubscription,
        user: Optional[SysUser] = None,
        usage_summary: Optional[dict] = None,
        current_cycle: Optional[object] = None,
    ) -> dict:
        result = {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "plan_id": subscription.plan_id,
            "plan_code": subscription.plan_code_snapshot,
            "plan_name": subscription.plan_name,
            "plan_type": subscription.plan_type,
            "plan_kind": subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED,
            "duration_days": int(subscription.duration_days_snapshot or 0),
            "quota_metric": subscription.quota_metric,
            "quota_value": float(subscription.quota_value or 0),
            "reset_period": subscription.reset_period,
            "reset_timezone": subscription.reset_timezone,
            "activation_mode": subscription.activation_mode,
            "start_time": subscription.start_time.isoformat() if subscription.start_time else None,
            "end_time": subscription.end_time.isoformat() if subscription.end_time else None,
            "status": SubscriptionService._normalized_subscription_status(subscription),
            "created_by": subscription.created_by,
            "activated_at": subscription.activated_at.isoformat() if subscription.activated_at else None,
            "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
            "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
            "usage_summary": usage_summary or SubscriptionService._empty_usage_summary(),
            "current_cycle": current_cycle if isinstance(current_cycle, dict) else SubscriptionService._serialize_cycle(current_cycle, subscription.quota_value),
        }
        if user is not None:
            result["username"] = user.username
            result["email"] = user.email
        return result

    @staticmethod
    def _subscription_usage_filter(subscription: UserSubscription):
        return or_(
            ConsumptionRecord.subscription_id == subscription.id,
            and_(
                ConsumptionRecord.subscription_id.is_(None),
                ConsumptionRecord.billing_mode.is_(None),
                ConsumptionRecord.user_id == subscription.user_id,
                ConsumptionRecord.model_name.isnot(None),
                ConsumptionRecord.created_at >= subscription.start_time,
                ConsumptionRecord.created_at <= subscription.end_time,
            ),
        )

    @staticmethod
    def _merge_usage_rows(summary: dict, row) -> None:
        summary["request_count"] += int(row.request_count or 0)
        summary["input_tokens"] += int(row.input_tokens or 0)
        summary["output_tokens"] += int(row.output_tokens or 0)
        summary["total_tokens"] += int(row.total_tokens or 0)
        summary["total_cost"] += float(row.total_cost or 0)

    @staticmethod
    def _build_usage_summary_map(
        db: Session,
        subscriptions: list[UserSubscription],
    ) -> dict[int, dict]:
        if not subscriptions:
            return {}

        summary_map = {subscription.id: SubscriptionService._empty_usage_summary() for subscription in subscriptions}
        subscription_ids = [subscription.id for subscription in subscriptions]

        linked_rows = (
            db.query(
                ConsumptionRecord.subscription_id.label("subscription_id"),
                func.count(ConsumptionRecord.id).label("request_count"),
                func.coalesce(func.sum(ConsumptionRecord.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.total_cost), 0).label("total_cost"),
            )
            .filter(
                ConsumptionRecord.subscription_id.in_(subscription_ids),
                ConsumptionRecord.model_name.isnot(None),
            )
            .group_by(ConsumptionRecord.subscription_id)
            .all()
        )
        for row in linked_rows:
            SubscriptionService._merge_usage_rows(summary_map[row.subscription_id], row)

        legacy_rows = (
            db.query(
                UserSubscription.id.label("subscription_id"),
                func.count(ConsumptionRecord.id).label("request_count"),
                func.coalesce(func.sum(ConsumptionRecord.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.total_cost), 0).label("total_cost"),
            )
            .join(
                ConsumptionRecord,
                and_(
                    ConsumptionRecord.user_id == UserSubscription.user_id,
                    ConsumptionRecord.subscription_id.is_(None),
                    ConsumptionRecord.billing_mode.is_(None),
                    ConsumptionRecord.model_name.isnot(None),
                    ConsumptionRecord.created_at >= UserSubscription.start_time,
                    ConsumptionRecord.created_at <= UserSubscription.end_time,
                ),
            )
            .filter(UserSubscription.id.in_(subscription_ids))
            .group_by(UserSubscription.id)
            .all()
        )
        for row in legacy_rows:
            SubscriptionService._merge_usage_rows(summary_map[row.subscription_id], row)

        for summary in summary_map.values():
            summary["total_cost"] = round(summary["total_cost"], 6)

        return summary_map

    @staticmethod
    def _serialize_consumption_record(record: ConsumptionRecord) -> dict:
        return {
            "id": record.id,
            "user_id": record.user_id,
            "request_id": record.request_id,
            "model_name": record.model_name,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "total_tokens": record.total_tokens,
            "raw_input_tokens": record.raw_input_tokens or 0,
            "raw_output_tokens": record.raw_output_tokens or 0,
            "raw_total_tokens": record.raw_total_tokens or 0,
            "logical_input_tokens": record.logical_input_tokens or 0,
            "upstream_input_tokens": record.upstream_input_tokens or 0,
            "upstream_cache_read_input_tokens": record.upstream_cache_read_input_tokens or 0,
            "upstream_cache_creation_input_tokens": record.upstream_cache_creation_input_tokens or 0,
            "upstream_prompt_cache_status": record.upstream_prompt_cache_status or "BYPASS",
            "input_cost": float(record.input_cost),
            "output_cost": float(record.output_cost),
            "total_cost": float(record.total_cost),
            "balance_before": float(record.balance_before),
            "balance_after": float(record.balance_after),
            "billing_mode": record.billing_mode,
            "subscription_id": record.subscription_id,
            "subscription_cycle_id": record.subscription_cycle_id,
            "quota_metric": record.quota_metric,
            "quota_consumed_amount": float(record.quota_consumed_amount or 0),
            "quota_limit_snapshot": float(record.quota_limit_snapshot or 0),
            "quota_used_after": float(record.quota_used_after or 0),
            "quota_cycle_date": record.quota_cycle_date.isoformat() if record.quota_cycle_date else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    @staticmethod
    def _expire_due_subscriptions(db: Session, now: datetime) -> int:
        expired_subs = (
            db.query(UserSubscription)
            .filter(
                SubscriptionService._active_status_filter(),
                UserSubscription.end_time < now,
            )
            .all()
        )
        for sub in expired_subs:
            sub.status = "expired"
        return len(expired_subs)

    @staticmethod
    def resolve_active_subscription(
        db: Session,
        user_id: int,
        now: Optional[datetime] = None,
    ) -> Optional[UserSubscription]:
        usage_now = now or SubscriptionService.get_current_time()
        SubscriptionService._expire_due_subscriptions(db, usage_now)
        return (
            db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user_id,
                SubscriptionService._active_status_filter(),
                UserSubscription.start_time <= usage_now,
                UserSubscription.end_time >= usage_now,
            )
            .order_by(UserSubscription.end_time.desc(), UserSubscription.id.desc())
            .first()
        )

    @staticmethod
    def refresh_user_subscription_state(
        db: Session,
        user_id: int,
        now: Optional[datetime] = None,
    ) -> Optional[UserSubscription]:
        usage_now = now or SubscriptionService.get_current_time()
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        active_subscription = SubscriptionService.resolve_active_subscription(db, user_id, usage_now)
        if not active_subscription:
            user.subscription_type = "balance"
            user.subscription_expires_at = None
            return None

        # ``sys_user.subscription_type`` is only a coarse cache flag and must stay
        # compatible with legacy schemas that only support ``balance/unlimited``.
        # The precise package kind continues to come from ``user_subscription``.
        user.subscription_type = "unlimited"
        user.subscription_expires_at = active_subscription.end_time
        return active_subscription

    @staticmethod
    def _get_or_create_cycle(
        db: Session,
        subscription: UserSubscription,
        now: Optional[datetime] = None,
        lock: bool = False,
    ) -> SubscriptionUsageCycle:
        usage_now = now or SubscriptionService.get_current_time()
        cycle_date, cycle_start_at, cycle_end_at = SubscriptionService._get_cycle_window(
            usage_now,
            subscription.reset_timezone,
        )
        query = db.query(SubscriptionUsageCycle).filter(
            SubscriptionUsageCycle.subscription_id == subscription.id,
            SubscriptionUsageCycle.cycle_date == cycle_date,
        )
        if lock:
            query = query.with_for_update()
        cycle = query.first()
        if cycle:
            return cycle

        savepoint = db.begin_nested()
        try:
            cycle = SubscriptionUsageCycle(
                subscription_id=subscription.id,
                user_id=subscription.user_id,
                cycle_date=cycle_date,
                cycle_start_at=cycle_start_at,
                cycle_end_at=cycle_end_at,
                quota_metric=subscription.quota_metric or SubscriptionService.QUOTA_METRIC_TOKENS,
                quota_limit=subscription.quota_value or Decimal("0"),
                used_amount=Decimal("0"),
                request_count=0,
                last_request_id=None,
            )
            db.add(cycle)
            db.flush()
            savepoint.commit()
            return cycle
        except IntegrityError:
            savepoint.rollback()

        cycle = query.first()
        if cycle:
            return cycle
        raise ServiceException(500, "Failed to load subscription usage cycle", "SUBSCRIPTION_CYCLE_LOAD_FAILED")

    @staticmethod
    def _get_cycle_for_summary(
        db: Session,
        subscription: UserSubscription,
        now: Optional[datetime] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        cycle_date, cycle_start_at, cycle_end_at = SubscriptionService._get_cycle_window(
            usage_now,
            subscription.reset_timezone,
        )
        cycle = (
            db.query(SubscriptionUsageCycle)
            .filter(
                SubscriptionUsageCycle.subscription_id == subscription.id,
                SubscriptionUsageCycle.cycle_date == cycle_date,
            )
            .first()
        )
        if cycle:
            return SubscriptionService._serialize_cycle(cycle, subscription.quota_value)
        quota_limit = SubscriptionService._normalize_decimal(subscription.quota_value)
        return {
            "id": None,
            "cycle_date": cycle_date.isoformat(),
            "cycle_start_at": cycle_start_at.isoformat(),
            "cycle_end_at": cycle_end_at.isoformat(),
            "quota_metric": subscription.quota_metric,
            "quota_limit": float(quota_limit),
            "used_amount": 0.0,
            "remaining_amount": float(quota_limit),
            "request_count": 0,
            "last_request_id": None,
        }

    @staticmethod
    def get_current_subscription_summary(
        db: Session,
        user_id: int,
        now: Optional[datetime] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        active_subscription = SubscriptionService.resolve_active_subscription(db, user_id, usage_now)
        if not active_subscription:
            return SubscriptionService._default_subscription_summary()

        current_cycle = None
        if (active_subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED) == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            current_cycle = SubscriptionService._get_cycle_for_summary(db, active_subscription, usage_now)

        return {
            "subscription_type": "quota"
            if (active_subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED) == SubscriptionService.PLAN_KIND_DAILY_QUOTA
            else "unlimited",
            "plan_name": active_subscription.plan_name,
            "plan_code": active_subscription.plan_code_snapshot,
            "plan_kind": active_subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED,
            "start_time": active_subscription.start_time.isoformat() if active_subscription.start_time else None,
            "end_time": active_subscription.end_time.isoformat() if active_subscription.end_time else None,
            "quota_metric": active_subscription.quota_metric,
            "quota_value": float(active_subscription.quota_value or 0),
            "current_cycle": current_cycle,
        }

    @staticmethod
    def check_quota_before_request(
        db: Session,
        user: SysUser,
        now: Optional[datetime] = None,
        quota_precheck: Optional[dict] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        active_subscription = SubscriptionService.resolve_active_subscription(db, user.id, usage_now)
        if not active_subscription:
            raise ServiceException(403, "套餐已过期，请续费或充值余额", "SUBSCRIPTION_EXPIRED")

        plan_kind = active_subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED
        if plan_kind != SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            return {"subscription": active_subscription, "cycle": None}

        quota_metric = active_subscription.quota_metric or SubscriptionService.QUOTA_METRIC_TOKENS
        estimated_consumed_amount = None
        if quota_precheck:
            metric_key = (
                "estimated_total_cost"
                if quota_metric == SubscriptionService.QUOTA_METRIC_COST
                else "estimated_total_tokens"
            )
            raw_estimate = quota_precheck.get(metric_key)
            if raw_estimate is not None:
                estimated_consumed_amount = SubscriptionService._normalize_decimal(raw_estimate)

        cycle = SubscriptionService._get_or_create_cycle(
            db,
            active_subscription,
            usage_now,
            lock=estimated_consumed_amount is not None,
        )
        quota_limit = SubscriptionService._normalize_decimal(active_subscription.quota_value)
        used_amount = SubscriptionService._normalize_decimal(cycle.used_amount)
        if used_amount >= quota_limit:
            raise ServiceException(
                403,
                "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
                "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
            )

        if estimated_consumed_amount is not None:
            remaining_amount = quota_limit - used_amount
            if estimated_consumed_amount > remaining_amount:
                raise ServiceException(
                    403,
                    "本次请求预计会超出当日套餐剩余额度，请缩短上下文或降低输出上限后重试",
                    "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
                )
        return {"subscription": active_subscription, "cycle": cycle}

    @staticmethod
    def consume_quota_after_request(
        db: Session,
        subscription: UserSubscription,
        request_id: str,
        raw_total_tokens: int,
        total_cost: float,
        now: Optional[datetime] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        cycle = SubscriptionService._get_or_create_cycle(db, subscription, usage_now, lock=True)

        quota_metric = subscription.quota_metric or SubscriptionService.QUOTA_METRIC_TOKENS
        if quota_metric == SubscriptionService.QUOTA_METRIC_COST:
            consumed_amount = SubscriptionService._normalize_decimal(total_cost)
        else:
            consumed_amount = SubscriptionService._normalize_decimal(raw_total_tokens)

        quota_limit = SubscriptionService._normalize_decimal(subscription.quota_value)
        next_used_amount = SubscriptionService._normalize_decimal(cycle.used_amount) + consumed_amount
        if next_used_amount > quota_limit:
            raise ServiceException(
                403,
                "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
                "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
            )

        cycle.used_amount = next_used_amount
        cycle.request_count = int(cycle.request_count or 0) + 1
        cycle.last_request_id = request_id
        db.flush()

        return {
            "subscription_cycle_id": cycle.id,
            "quota_metric": quota_metric,
            "quota_consumed_amount": consumed_amount,
            "quota_limit_snapshot": SubscriptionService._normalize_decimal(subscription.quota_value),
            "quota_used_after": SubscriptionService._normalize_decimal(cycle.used_amount),
            "quota_cycle_date": cycle.cycle_date,
        }

    @staticmethod
    def _build_subscription_record(
        user_id: int,
        operator_id: int,
        plan_name: str,
        plan_type: str,
        plan_kind: str,
        duration_days: int,
        start_time: datetime,
        end_time: datetime,
        activation_mode: str = "append",
        plan_id: Optional[int] = None,
        plan_code: Optional[str] = None,
        quota_metric: Optional[str] = None,
        quota_value: Decimal | int | float | None = None,
        reset_period: str = DEFAULT_RESET_PERIOD,
        reset_timezone: str = DEFAULT_TIMEZONE,
    ) -> UserSubscription:
        current_time = SubscriptionService.get_current_time()
        return UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            plan_code_snapshot=plan_code,
            plan_name=plan_name,
            plan_type=plan_type,
            plan_kind_snapshot=plan_kind,
            duration_days_snapshot=duration_days,
            quota_metric=quota_metric,
            quota_value=SubscriptionService._normalize_decimal(quota_value),
            reset_period=reset_period,
            reset_timezone=reset_timezone,
            activation_mode=activation_mode,
            start_time=start_time,
            end_time=end_time,
            status="active",
            created_by=operator_id,
            activated_at=start_time if start_time <= current_time else None,
        )

    @staticmethod
    def activate_subscription(
        db: Session,
        user_id: int,
        plan_name: str,
        plan_type: str,
        duration_days: int,
        operator_id: int,
    ) -> dict:
        if duration_days <= 0:
            raise ServiceException(400, "Duration must be positive", "INVALID_DURATION")

        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        start_time = SubscriptionService.get_current_time()
        current_active = SubscriptionService.resolve_active_subscription(db, user_id, start_time)
        if current_active and current_active.end_time > start_time:
            start_time = current_active.end_time
        end_time = start_time + timedelta(days=duration_days)

        subscription = SubscriptionService._build_subscription_record(
            user_id=user_id,
            operator_id=operator_id,
            plan_name=plan_name,
            plan_type=plan_type,
            plan_kind=SubscriptionService.PLAN_KIND_UNLIMITED,
            duration_days=duration_days,
            start_time=start_time,
            end_time=end_time,
            activation_mode="append",
            quota_metric=None,
            quota_value=Decimal("0"),
        )
        db.add(subscription)
        SubscriptionService.refresh_user_subscription_state(db, user_id, SubscriptionService.get_current_time())
        db.commit()
        db.refresh(subscription)
        return SubscriptionService._serialize_subscription(subscription)

    @staticmethod
    def activate_plan_subscription(
        db: Session,
        user_id: int,
        plan_id: int,
        operator_id: int,
        activation_mode: str = "append",
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise ServiceException(404, "Plan not found", "PLAN_NOT_FOUND")
        if plan.status != "active":
            raise ServiceException(400, "Plan is inactive", "PLAN_INACTIVE")
        if activation_mode not in {"append", "override"}:
            raise ServiceException(400, "Invalid activation mode", "INVALID_ACTIVATION_MODE")

        now = SubscriptionService.get_current_time()
        current_active = SubscriptionService.resolve_active_subscription(db, user_id, now)
        start_time = now
        if activation_mode == "append" and current_active and current_active.end_time > now:
            start_time = current_active.end_time
        elif activation_mode == "override" and current_active:
            current_active.status = "cancelled"

        end_time = start_time + timedelta(days=int(plan.duration_days))
        subscription = SubscriptionService._build_subscription_record(
            user_id=user_id,
            operator_id=operator_id,
            plan_id=plan.id,
            plan_code=plan.plan_code,
            plan_name=plan.plan_name,
            plan_type=plan.duration_mode,
            plan_kind=plan.plan_kind,
            duration_days=int(plan.duration_days),
            start_time=start_time,
            end_time=end_time,
            activation_mode=activation_mode,
            quota_metric=plan.quota_metric,
            quota_value=plan.quota_value,
            reset_period=plan.reset_period,
            reset_timezone=plan.reset_timezone,
        )
        db.add(subscription)
        db.flush()
        SubscriptionService.refresh_user_subscription_state(db, user_id, now)
        db.commit()
        db.refresh(subscription)
        return SubscriptionService._serialize_subscription(subscription)

    @staticmethod
    def cancel_subscription(db: Session, user_id: int) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        now = SubscriptionService.get_current_time()
        active_subs = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user_id,
                SubscriptionService._active_status_filter(),
                UserSubscription.end_time >= now,
            )
            .all()
        )
        for sub in active_subs:
            sub.status = "cancelled"

        SubscriptionService.refresh_user_subscription_state(db, user_id, now)
        db.commit()

        return {
            "user_id": user.id,
            "subscription_type": user.subscription_type,
            "message": "Subscription cancelled, switched to balance mode",
        }

    @staticmethod
    def get_user_subscriptions(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = db.query(UserSubscription).filter(UserSubscription.user_id == user_id)
        total = query.count()
        subscriptions = (
            query.order_by(UserSubscription.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        usage_summary_map = SubscriptionService._build_usage_summary_map(db, subscriptions)
        usage_now = SubscriptionService.get_current_time()
        result = []
        for subscription in subscriptions:
            current_cycle = None
            if (subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED) == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
                if SubscriptionService._is_effectively_active(subscription, usage_now):
                    current_cycle = SubscriptionService._get_cycle_for_summary(db, subscription, usage_now)
            result.append(
                SubscriptionService._serialize_subscription(
                    subscription,
                    usage_summary=usage_summary_map.get(subscription.id),
                    current_cycle=current_cycle,
                )
            )
        return result, total

    @staticmethod
    def list_all_subscriptions(
        db: Session,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = db.query(UserSubscription, SysUser).join(SysUser, UserSubscription.user_id == SysUser.id)
        if status:
            if status == "active":
                query = query.filter(SubscriptionService._active_status_filter())
            else:
                query = query.filter(UserSubscription.status == status)
        total = query.count()
        rows = (
            query.order_by(UserSubscription.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        subscriptions = [sub for sub, _ in rows]
        usage_summary_map = SubscriptionService._build_usage_summary_map(db, subscriptions)
        usage_now = SubscriptionService.get_current_time()
        result = []
        for subscription, user in rows:
            current_cycle = None
            if (subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED) == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
                if SubscriptionService._is_effectively_active(subscription, usage_now):
                    current_cycle = SubscriptionService._get_cycle_for_summary(db, subscription, usage_now)
            result.append(
                SubscriptionService._serialize_subscription(
                    subscription,
                    user=user,
                    usage_summary=usage_summary_map.get(subscription.id),
                    current_cycle=current_cycle,
                )
            )
        return result, total

    @staticmethod
    def get_subscription_usage_detail(
        db: Session,
        subscription_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        row = (
            db.query(UserSubscription, SysUser)
            .join(SysUser, UserSubscription.user_id == SysUser.id)
            .filter(UserSubscription.id == subscription_id)
            .first()
        )
        if not row:
            raise ServiceException(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")

        subscription, user = row
        usage_summary = SubscriptionService._build_usage_summary_map(db, [subscription]).get(
            subscription.id,
            SubscriptionService._empty_usage_summary(),
        )
        current_cycle = None
        if (subscription.plan_kind_snapshot or SubscriptionService.PLAN_KIND_UNLIMITED) == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            usage_now = SubscriptionService.get_current_time()
            if SubscriptionService._is_effectively_active(subscription, usage_now):
                current_cycle = SubscriptionService._get_cycle_for_summary(db, subscription, usage_now)

        query = db.query(ConsumptionRecord).filter(
            SubscriptionService._subscription_usage_filter(subscription),
            ConsumptionRecord.model_name.isnot(None),
        )
        total = query.count()
        records = (
            query.order_by(ConsumptionRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "subscription": SubscriptionService._serialize_subscription(
                subscription,
                user=user,
                usage_summary=usage_summary,
                current_cycle=current_cycle,
            ),
            "summary": usage_summary,
            "records": [SubscriptionService._serialize_consumption_record(record) for record in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def check_and_expire_subscriptions(db: Session) -> int:
        now = SubscriptionService.get_current_time()
        expired_subs = (
            db.query(UserSubscription)
            .filter(
                SubscriptionService._active_status_filter(),
                UserSubscription.end_time < now,
            )
            .all()
        )
        expired_user_ids = {sub.user_id for sub in expired_subs}
        expired_count = SubscriptionService._expire_due_subscriptions(db, now)
        user_ids = {
            row[0]
            for row in db.query(UserSubscription.user_id).filter(SubscriptionService._active_status_filter()).distinct().all()
        }
        user_ids.update(expired_user_ids)
        for user_id in user_ids:
            SubscriptionService.refresh_user_subscription_state(db, user_id, now)
        db.commit()
        return expired_count
