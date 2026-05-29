"""Subscription management service."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

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
    QUOTA_RULE_CUTOVER_AT = datetime(2026, 5, 10, 0, 0, 0)
    UNLIMITED_DAILY_TOKEN_LIMIT = Decimal("300000000")
    UNLIMITED_MONTHLY_DAILY_COST_LIMIT = Decimal("100")
    LEGACY_UNLIMITED_MONTHLY_DAILY_COST_LIMIT = Decimal("120")
    ENJOY_DAILY_COST_LIMIT = Decimal("50")
    LEGACY_ENJOY_DAILY_COST_LIMIT = Decimal("60")
    MIN_TEXT_REQUEST_USD_THRESHOLD = Decimal("0.1")
    UNLIMITED_DAILY_LIMIT_ERROR_CODE = "SUBSCRIPTION_UNLIMITED_DAILY_TOKEN_EXCEEDED"
    RETRYABLE_DB_ERROR_CODES = {1205, 1213}
    ENJOY_PLAN_CODES = frozenset({"daily-10m-token", "weekly-10m-token", "monthly-10m-token"})
    MONTHLY_UNLIMITED_PLAN_CODES = frozenset({"monthly-unlimited"})
    COST_LIMITED_UNLIMITED_PLAN_CODES = frozenset({"daily-unlimited", "weekly-unlimited", "monthly-unlimited"})

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
            "description": "1 天无限额度套餐，每日 100 美元额度",
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
            "description": "7 天无限额度套餐，每日 100 美元额度",
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
            "description": "30 天无限额度套餐，每日 100 美元额度",
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
            raise ServiceException(400, "数值格式不正确", "INVALID_DECIMAL") from exc

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
            "resolved_quota_metric": None,
            "resolved_quota_value": 0.0,
            "unlimited_daily_token_limit": None,
            "current_cycle": None,
        }

    @staticmethod
    def _get_plan_kind(subscription: UserSubscription) -> str:
        return getattr(subscription, "plan_kind_snapshot", None) or SubscriptionService.PLAN_KIND_UNLIMITED

    @staticmethod
    def _normalized_text(value: object) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _get_record_plan_code(record: object) -> str:
        return SubscriptionService._normalized_text(
            getattr(record, "plan_code_snapshot", None) or getattr(record, "plan_code", None)
        )

    @staticmethod
    def _get_record_plan_name(record: object) -> str:
        return str(getattr(record, "plan_name", None) or "").strip()

    @staticmethod
    def _get_record_duration_mode(record: object) -> str:
        return SubscriptionService._normalized_text(
            getattr(record, "duration_mode", None) or getattr(record, "plan_type", None)
        )

    @staticmethod
    def _is_record_created_before_quota_cutover(record: object) -> bool:
        created_at = getattr(record, "created_at", None)
        return isinstance(created_at, datetime) and created_at < SubscriptionService.QUOTA_RULE_CUTOVER_AT

    @staticmethod
    def _get_record_plan_kind(record: object) -> str:
        return SubscriptionService._normalized_text(
            getattr(record, "plan_kind_snapshot", None) or getattr(record, "plan_kind", None)
        )

    @staticmethod
    def _is_monthly_unlimited_record(record: object) -> bool:
        if SubscriptionService._get_record_plan_kind(record) != SubscriptionService.PLAN_KIND_UNLIMITED:
            return False

        plan_code = SubscriptionService._get_record_plan_code(record)
        if plan_code in SubscriptionService.COST_LIMITED_UNLIMITED_PLAN_CODES:
            return True

        duration_mode = SubscriptionService._get_record_duration_mode(record)
        plan_name = SubscriptionService._get_record_plan_name(record)
        if duration_mode in {"month", "monthly", "day", "daily", "week", "weekly"} and "无限" in plan_name:
            return True

        return False

    @staticmethod
    def _is_enjoy_daily_quota_record(record: object) -> bool:
        if SubscriptionService._get_record_plan_kind(record) != SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            return False

        plan_code = SubscriptionService._get_record_plan_code(record)
        if plan_code in SubscriptionService.ENJOY_PLAN_CODES:
            return True

        plan_name = SubscriptionService._get_record_plan_name(record)
        return "畅享" in plan_name

    @staticmethod
    def _build_quota_strategy(
        *,
        quota_metric: str,
        quota_limit: Decimal,
        hard_limit: bool,
        use_official_cost: bool,
    ) -> dict:
        return {
            "quota_metric": quota_metric,
            "quota_limit": SubscriptionService._normalize_decimal(quota_limit),
            "hard_limit": hard_limit,
            "use_official_cost": use_official_cost,
        }

    @staticmethod
    def _resolve_subscription_quota_strategy(subscription: UserSubscription) -> dict:
        if SubscriptionService._is_monthly_unlimited_record(subscription):
            limit = (
                SubscriptionService.LEGACY_UNLIMITED_MONTHLY_DAILY_COST_LIMIT
                if SubscriptionService._is_record_created_before_quota_cutover(subscription)
                else SubscriptionService.UNLIMITED_MONTHLY_DAILY_COST_LIMIT
            )
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_limit=limit,
                hard_limit=True,
                use_official_cost=True,
            )

        if SubscriptionService._is_enjoy_daily_quota_record(subscription):
            limit = (
                SubscriptionService.LEGACY_ENJOY_DAILY_COST_LIMIT
                if SubscriptionService._is_record_created_before_quota_cutover(subscription)
                else SubscriptionService.ENJOY_DAILY_COST_LIMIT
            )
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_limit=limit,
                hard_limit=False,
                use_official_cost=True,
            )

        if SubscriptionService._is_unlimited_subscription(subscription):
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_TOKENS,
                quota_limit=SubscriptionService.UNLIMITED_DAILY_TOKEN_LIMIT,
                hard_limit=True,
                use_official_cost=False,
            )

        return SubscriptionService._build_quota_strategy(
            quota_metric=getattr(subscription, "quota_metric", None) or SubscriptionService.QUOTA_METRIC_TOKENS,
            quota_limit=getattr(subscription, "quota_value", None) or Decimal("0"),
            hard_limit=False,
            use_official_cost=False,
        )

    @staticmethod
    def _resolve_plan_quota_strategy(plan: SubscriptionPlan) -> dict:
        if SubscriptionService._is_monthly_unlimited_record(plan):
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_limit=SubscriptionService.UNLIMITED_MONTHLY_DAILY_COST_LIMIT,
                hard_limit=True,
                use_official_cost=True,
            )

        if SubscriptionService._is_enjoy_daily_quota_record(plan):
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_limit=SubscriptionService.ENJOY_DAILY_COST_LIMIT,
                hard_limit=False,
                use_official_cost=True,
            )

        if SubscriptionService._get_record_plan_kind(plan) == SubscriptionService.PLAN_KIND_UNLIMITED:
            return SubscriptionService._build_quota_strategy(
                quota_metric=SubscriptionService.QUOTA_METRIC_TOKENS,
                quota_limit=SubscriptionService.UNLIMITED_DAILY_TOKEN_LIMIT,
                hard_limit=True,
                use_official_cost=False,
            )

        return SubscriptionService._build_quota_strategy(
            quota_metric=getattr(plan, "quota_metric", None) or SubscriptionService.QUOTA_METRIC_TOKENS,
            quota_limit=getattr(plan, "quota_value", None) or Decimal("0"),
            hard_limit=False,
            use_official_cost=False,
        )

    @staticmethod
    def _is_unlimited_subscription(subscription: UserSubscription) -> bool:
        return SubscriptionService._get_plan_kind(subscription) == SubscriptionService.PLAN_KIND_UNLIMITED

    @staticmethod
    def _requires_daily_cycle(subscription: UserSubscription) -> bool:
        return SubscriptionService._get_plan_kind(subscription) in {
            SubscriptionService.PLAN_KIND_UNLIMITED,
            SubscriptionService.PLAN_KIND_DAILY_QUOTA,
        }

    @staticmethod
    def _get_effective_quota_metric(subscription: UserSubscription) -> str:
        return SubscriptionService._resolve_subscription_quota_strategy(subscription)["quota_metric"]

    @staticmethod
    def _get_effective_quota_limit(subscription: UserSubscription) -> Decimal:
        return SubscriptionService._resolve_subscription_quota_strategy(subscription)["quota_limit"]

    @staticmethod
    def _uses_official_cost_for_quota(subscription: UserSubscription) -> bool:
        return bool(SubscriptionService._resolve_subscription_quota_strategy(subscription)["use_official_cost"])

    @staticmethod
    def _get_quota_consumed_amount(
        subscription: UserSubscription,
        *,
        raw_total_tokens: int,
        total_cost: float,
        quota_cost: Optional[float] = None,
    ) -> Decimal:
        quota_metric = SubscriptionService._get_effective_quota_metric(subscription)
        if quota_metric == SubscriptionService.QUOTA_METRIC_COST:
            return SubscriptionService._normalize_decimal(
                quota_cost
                if SubscriptionService._uses_official_cost_for_quota(subscription) and quota_cost is not None
                else total_cost
            )
        return SubscriptionService._normalize_decimal(raw_total_tokens)

    @staticmethod
    def _get_estimated_quota_consumption(
        subscription: UserSubscription,
        quota_precheck: Optional[dict],
    ) -> Decimal:
        if not quota_precheck:
            return Decimal("0")

        quota_metric = SubscriptionService._get_effective_quota_metric(subscription)
        if quota_metric == SubscriptionService.QUOTA_METRIC_COST:
            keys = (
                ("estimated_quota_cost", "estimated_total_cost")
                if SubscriptionService._uses_official_cost_for_quota(subscription)
                else ("estimated_total_cost", "estimated_quota_cost")
            )
        else:
            keys = ("estimated_total_tokens",)

        for key in keys:
            estimated_value = quota_precheck.get(key)
            if estimated_value is None:
                continue
            estimated_amount = SubscriptionService._normalize_decimal(estimated_value)
            return estimated_amount if estimated_amount > 0 else Decimal("0")

        return Decimal("0")

    @staticmethod
    def is_retryable_concurrency_error(exc: Exception) -> bool:
        """Return whether one DB exception is safe to retry in a fresh transaction."""
        if not isinstance(exc, OperationalError):
            return False

        error_code = None
        orig = getattr(exc, "orig", None)
        if orig is not None:
            args = getattr(orig, "args", ())
            if args:
                error_code = args[0]

        if error_code in SubscriptionService.RETRYABLE_DB_ERROR_CODES:
            return True

        message = str(orig or exc).lower()
        return "lock wait timeout" in message or "deadlock found" in message

    @staticmethod
    def _get_unlimited_daily_token_limit(subscription: UserSubscription) -> Optional[float]:
        if not SubscriptionService._is_unlimited_subscription(subscription):
            return None
        if SubscriptionService._get_effective_quota_metric(subscription) != SubscriptionService.QUOTA_METRIC_TOKENS:
            return None
        return float(SubscriptionService._get_effective_quota_limit(subscription))

    @staticmethod
    def _format_quota_limit_text(quota_metric: str, quota_limit: Decimal) -> str:
        limit_value = SubscriptionService._normalize_decimal(quota_limit)
        if quota_metric == SubscriptionService.QUOTA_METRIC_COST:
            return f"${limit_value.quantize(Decimal('0.01'))}"
        return f"{int(limit_value):,} Token"

    @staticmethod
    def _build_quota_exceeded_error(subscription: UserSubscription, estimated: bool = False) -> ServiceException:
        strategy = SubscriptionService._resolve_subscription_quota_strategy(subscription)
        if strategy["hard_limit"]:
            limit_text = SubscriptionService._format_quota_limit_text(
                strategy["quota_metric"],
                strategy["quota_limit"],
            )
            if estimated:
                message = f"本次请求预计会超出实际使用额度，每日最多可使用 {limit_text}，请缩短上下文或降低输出上限后重试"
            else:
                message = f"已超出实际使用额度，每日最多可使用 {limit_text}，请明天再试"
            return ServiceException(
                403,
                message,
                SubscriptionService.UNLIMITED_DAILY_LIMIT_ERROR_CODE,
            )
        if estimated:
            return ServiceException(
                403,
                "本次请求预计会超出当日套餐剩余额度，请缩短上下文或降低输出上限后重试",
                "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
            )
        return ServiceException(
            403,
            "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

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
                raise ServiceException(400, "套餐类型不合法", "INVALID_PLAN_KIND")

        duration_days = payload.get("duration_days")
        if duration_days is not None and int(duration_days) <= 0:
            raise ServiceException(400, "套餐时长必须大于 0", "INVALID_DURATION")

        quota_metric = payload.get("quota_metric")
        quota_value = payload.get("quota_value")
        effective_plan_kind = plan_kind

        if effective_plan_kind == SubscriptionService.PLAN_KIND_UNLIMITED:
            payload["quota_metric"] = None
            payload["quota_value"] = Decimal("0")
        elif effective_plan_kind == SubscriptionService.PLAN_KIND_DAILY_QUOTA:
            if quota_metric not in {SubscriptionService.QUOTA_METRIC_TOKENS, SubscriptionService.QUOTA_METRIC_COST}:
                raise ServiceException(400, "套餐额度口径不合法", "INVALID_QUOTA_METRIC")
            normalized_quota = SubscriptionService._normalize_decimal(quota_value)
            if normalized_quota <= 0:
                raise ServiceException(400, "套餐额度必须大于 0", "INVALID_QUOTA_VALUE")
            payload["quota_value"] = normalized_quota

        if "status" in payload and payload["status"] not in {"active", "inactive"}:
            raise ServiceException(400, "套餐状态不合法", "INVALID_PLAN_STATUS")

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
        resolved_strategy = SubscriptionService._resolve_plan_quota_strategy(plan)
        resolved_quota_metric = resolved_strategy["quota_metric"]
        resolved_quota_value = resolved_strategy["quota_limit"]
        return {
            "id": plan.id,
            "plan_code": plan.plan_code,
            "plan_name": plan.plan_name,
            "plan_kind": plan.plan_kind,
            "duration_mode": plan.duration_mode,
            "duration_days": plan.duration_days,
            "quota_metric": plan.quota_metric,
            "quota_value": float(plan.quota_value or 0),
            "resolved_quota_metric": resolved_quota_metric,
            "resolved_quota_value": float(resolved_quota_value),
            "unlimited_daily_token_limit": float(resolved_quota_value)
            if plan.plan_kind == SubscriptionService.PLAN_KIND_UNLIMITED
            and resolved_quota_metric == SubscriptionService.QUOTA_METRIC_TOKENS
            else None,
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
            raise ServiceException(400, "套餐编码已存在", "DUPLICATE_PLAN_CODE")

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
            raise ServiceException(404, "套餐模板不存在", "PLAN_NOT_FOUND")

        payload = SubscriptionService._validate_plan_payload(data, is_update=True)
        if "plan_code" in payload and payload["plan_code"] != plan.plan_code:
            duplicate = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == payload["plan_code"]).first()
            if duplicate:
                raise ServiceException(400, "套餐编码已存在", "DUPLICATE_PLAN_CODE")

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
        remaining_value = limit_value - used_value
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
        effective_quota_metric = (
            SubscriptionService._get_effective_quota_metric(subscription)
            if SubscriptionService._requires_daily_cycle(subscription)
            else subscription.quota_metric
        )
        effective_quota_value = (
            SubscriptionService._get_effective_quota_limit(subscription)
            if SubscriptionService._requires_daily_cycle(subscription)
            else SubscriptionService._normalize_decimal(subscription.quota_value)
        )
        result = {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "plan_id": subscription.plan_id,
            "plan_code": subscription.plan_code_snapshot,
            "plan_name": subscription.plan_name,
            "plan_type": subscription.plan_type,
            "plan_kind": SubscriptionService._get_plan_kind(subscription),
            "duration_days": int(subscription.duration_days_snapshot or 0),
            "quota_metric": effective_quota_metric,
            "quota_value": float(effective_quota_value),
            "resolved_quota_metric": effective_quota_metric,
            "resolved_quota_value": float(effective_quota_value),
            "unlimited_daily_token_limit": SubscriptionService._get_unlimited_daily_token_limit(subscription),
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
            "current_cycle": current_cycle if isinstance(current_cycle, dict) else SubscriptionService._serialize_cycle(
                current_cycle,
                effective_quota_value,
            ),
        }
        if user is not None:
            result["username"] = user.username
            result["email"] = user.email
        return result

    @staticmethod
    def _subscription_usage_filter(subscription: UserSubscription):
        return or_(
            and_(
                ConsumptionRecord.subscription_id == subscription.id,
                or_(
                    ConsumptionRecord.billing_mode == "subscription",
                    ConsumptionRecord.billing_mode.is_(None),
                ),
            ),
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
                or_(
                    ConsumptionRecord.billing_mode == "subscription",
                    ConsumptionRecord.billing_mode.is_(None),
                ),
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
            "billable_input_tokens": record.billable_input_tokens or record.input_tokens or 0,
            "raw_input_tokens": record.raw_input_tokens or 0,
            "raw_output_tokens": record.raw_output_tokens or 0,
            "raw_total_tokens": record.raw_total_tokens or 0,
            "logical_input_tokens": record.logical_input_tokens or 0,
            "upstream_input_tokens": record.upstream_input_tokens or 0,
            "upstream_cache_read_input_tokens": record.upstream_cache_read_input_tokens or 0,
            "billable_cache_read_input_tokens": record.billable_cache_read_input_tokens or record.upstream_cache_read_input_tokens or 0,
            "upstream_cache_creation_input_tokens": record.upstream_cache_creation_input_tokens or 0,
            "upstream_prompt_cache_status": record.upstream_prompt_cache_status or "BYPASS",
            "input_cost": float(record.input_cost),
            "cache_read_cost": float(record.cache_read_cost or 0),
            "output_cost": float(record.output_cost),
            "total_cost": float(record.total_cost),
            "input_price_per_million_snapshot": float(record.input_price_per_million_snapshot or 0),
            "output_price_per_million_snapshot": float(record.output_price_per_million_snapshot or 0),
            "price_multiplier_snapshot": float(record.price_multiplier_snapshot or 1),
            "fast_price_multiplier_snapshot": float(record.fast_price_multiplier_snapshot or 1),
            "context_tokens_snapshot": int(record.context_tokens_snapshot or 0),
            "context_token_threshold_snapshot": int(record.context_token_threshold_snapshot or 262144),
            "context_price_multiplier_snapshot": float(record.context_price_multiplier_snapshot or 1),
            "effective_price_multiplier_snapshot": float(
                (record.price_multiplier_snapshot or 1)
                * (record.fast_price_multiplier_snapshot or 1)
                * (record.context_price_multiplier_snapshot or 1)
            ),
            "token_multiplier_snapshot": float(record.token_multiplier_snapshot or 1),
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
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")

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
        quota_metric = SubscriptionService._get_effective_quota_metric(subscription)
        quota_limit = SubscriptionService._get_effective_quota_limit(subscription)
        query = db.query(SubscriptionUsageCycle).filter(
            SubscriptionUsageCycle.subscription_id == subscription.id,
            SubscriptionUsageCycle.cycle_date == cycle_date,
        )
        if lock:
            query = query.with_for_update()
        cycle = query.first()
        if cycle:
            cycle_used_amount = SubscriptionService._normalize_decimal(cycle.used_amount)
            should_rebuild_snapshot = cycle.quota_metric != quota_metric or (
                quota_metric == SubscriptionService.QUOTA_METRIC_COST
                and SubscriptionService._uses_official_cost_for_quota(subscription)
                and cycle_used_amount > quota_limit
            )
            if should_rebuild_snapshot:
                usage_snapshot = SubscriptionService._rebuild_cycle_usage_snapshot(
                    db,
                    subscription,
                    cycle_start_at,
                    cycle_end_at,
                    quota_metric,
                )
                cycle.quota_metric = quota_metric
                cycle.quota_limit = quota_limit
                cycle.used_amount = usage_snapshot["used_amount"]
                cycle.request_count = usage_snapshot["request_count"]
                cycle.last_request_id = usage_snapshot["last_request_id"]
                return cycle
            if SubscriptionService._normalize_decimal(cycle.quota_limit) != quota_limit:
                cycle.quota_limit = quota_limit
            return cycle

        savepoint = db.begin_nested()
        try:
            cycle = SubscriptionUsageCycle(
                subscription_id=subscription.id,
                user_id=subscription.user_id,
                cycle_date=cycle_date,
                cycle_start_at=cycle_start_at,
                cycle_end_at=cycle_end_at,
                quota_metric=quota_metric,
                quota_limit=quota_limit,
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
        raise ServiceException(500, "加载套餐使用周期失败", "SUBSCRIPTION_CYCLE_LOAD_FAILED")

    @staticmethod
    def _rebuild_cycle_usage_snapshot(
        db: Session,
        subscription: UserSubscription,
        cycle_start_at: datetime,
        cycle_end_at: datetime,
        quota_metric: str,
    ) -> dict:
        aggregate = (
            db.query(
                func.count(ConsumptionRecord.id).label("request_count"),
                func.coalesce(func.sum(ConsumptionRecord.total_cost), 0).label("total_cost"),
                func.coalesce(func.sum(ConsumptionRecord.raw_total_tokens), 0).label("raw_total_tokens"),
                func.coalesce(func.sum(ConsumptionRecord.total_tokens), 0).label("total_tokens"),
            )
            .filter(
                SubscriptionService._subscription_usage_filter(subscription),
                ConsumptionRecord.model_name.isnot(None),
                ConsumptionRecord.created_at >= cycle_start_at,
                ConsumptionRecord.created_at < cycle_end_at,
            )
            .first()
        )

        latest_record = (
            db.query(ConsumptionRecord)
            .filter(
                SubscriptionService._subscription_usage_filter(subscription),
                ConsumptionRecord.model_name.isnot(None),
                ConsumptionRecord.created_at >= cycle_start_at,
                ConsumptionRecord.created_at < cycle_end_at,
            )
            .order_by(ConsumptionRecord.id.desc())
            .first()
        )

        if quota_metric == SubscriptionService.QUOTA_METRIC_COST:
            used_amount = SubscriptionService._normalize_decimal(getattr(aggregate, "total_cost", 0))
        else:
            raw_total_tokens = SubscriptionService._normalize_decimal(
                getattr(aggregate, "raw_total_tokens", 0)
            )
            total_tokens = SubscriptionService._normalize_decimal(getattr(aggregate, "total_tokens", 0))
            used_amount = raw_total_tokens if raw_total_tokens > 0 else total_tokens

        return {
            "used_amount": used_amount,
            "request_count": int(getattr(aggregate, "request_count", 0) or 0),
            "last_request_id": getattr(latest_record, "request_id", None),
        }

    @staticmethod
    def _load_cycle_by_id(
        db: Session,
        cycle_id: int,
    ) -> Optional[SubscriptionUsageCycle]:
        return (
            db.query(SubscriptionUsageCycle)
            .filter(SubscriptionUsageCycle.id == cycle_id)
            .first()
        )

    @staticmethod
    def _apply_cycle_consumption_update(
        db: Session,
        *,
        cycle_id: int,
        consumed_amount: Decimal,
        request_id: str,
        quota_metric: str,
        quota_limit: Decimal,
    ) -> bool:
        result = db.execute(
            update(SubscriptionUsageCycle)
            .where(SubscriptionUsageCycle.id == cycle_id)
            .where((func.coalesce(SubscriptionUsageCycle.used_amount, 0) + consumed_amount) <= quota_limit)
            .values(
                quota_metric=quota_metric,
                quota_limit=quota_limit,
                used_amount=func.coalesce(SubscriptionUsageCycle.used_amount, 0) + consumed_amount,
                request_count=func.coalesce(SubscriptionUsageCycle.request_count, 0) + 1,
                last_request_id=request_id,
            )
        )
        return bool(result.rowcount)

    @staticmethod
    def _get_cycle_for_summary(
        db: Session,
        subscription: UserSubscription,
        now: Optional[datetime] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        if SubscriptionService._is_effectively_active(subscription, usage_now):
            cycle = SubscriptionService._get_or_create_cycle(db, subscription, usage_now)
            return SubscriptionService._serialize_cycle(
                cycle,
                SubscriptionService._get_effective_quota_limit(subscription),
            )

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
            return SubscriptionService._serialize_cycle(
                cycle,
                SubscriptionService._get_effective_quota_limit(subscription),
            )
        quota_limit = SubscriptionService._get_effective_quota_limit(subscription)
        return {
            "id": None,
            "cycle_date": cycle_date.isoformat(),
            "cycle_start_at": cycle_start_at.isoformat(),
            "cycle_end_at": cycle_end_at.isoformat(),
            "quota_metric": SubscriptionService._get_effective_quota_metric(subscription),
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
        if SubscriptionService._requires_daily_cycle(active_subscription):
            current_cycle = SubscriptionService._get_cycle_for_summary(db, active_subscription, usage_now)
        plan_kind = SubscriptionService._get_plan_kind(active_subscription)

        return {
            "subscription_type": "quota"
            if plan_kind == SubscriptionService.PLAN_KIND_DAILY_QUOTA
            else "unlimited",
            "plan_name": active_subscription.plan_name,
            "plan_code": active_subscription.plan_code_snapshot,
            "plan_kind": plan_kind,
            "start_time": active_subscription.start_time.isoformat() if active_subscription.start_time else None,
            "end_time": active_subscription.end_time.isoformat() if active_subscription.end_time else None,
            "quota_metric": SubscriptionService._get_effective_quota_metric(active_subscription)
            if SubscriptionService._requires_daily_cycle(active_subscription)
            else active_subscription.quota_metric,
            "quota_value": float(SubscriptionService._get_effective_quota_limit(active_subscription))
            if SubscriptionService._requires_daily_cycle(active_subscription)
            else float(active_subscription.quota_value or 0),
            "resolved_quota_metric": SubscriptionService._get_effective_quota_metric(active_subscription)
            if SubscriptionService._requires_daily_cycle(active_subscription)
            else active_subscription.quota_metric,
            "resolved_quota_value": float(SubscriptionService._get_effective_quota_limit(active_subscription))
            if SubscriptionService._requires_daily_cycle(active_subscription)
            else float(active_subscription.quota_value or 0),
            "unlimited_daily_token_limit": SubscriptionService._get_unlimited_daily_token_limit(active_subscription),
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

        if not SubscriptionService._requires_daily_cycle(active_subscription):
            return {"subscription": active_subscription, "cycle": None}

        cycle = SubscriptionService._get_or_create_cycle(db, active_subscription, usage_now)
        quota_limit = SubscriptionService._get_effective_quota_limit(active_subscription)
        used_amount = SubscriptionService._normalize_decimal(cycle.used_amount)
        remaining_amount = quota_limit - used_amount
        if remaining_amount <= 0:
            raise SubscriptionService._build_quota_exceeded_error(active_subscription)
        estimated_amount = SubscriptionService._get_estimated_quota_consumption(
            active_subscription,
            quota_precheck,
        )
        if estimated_amount > 0 and remaining_amount < estimated_amount:
            raise SubscriptionService._build_quota_exceeded_error(active_subscription, estimated=True)

        return {"subscription": active_subscription, "cycle": cycle}

    @staticmethod
    def consume_quota_after_request(
        db: Session,
        subscription: UserSubscription,
        request_id: str,
        raw_total_tokens: int,
        total_cost: float,
        quota_cost: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> dict:
        usage_now = now or SubscriptionService.get_current_time()
        quota_metric = SubscriptionService._get_effective_quota_metric(subscription)
        consumed_amount = SubscriptionService._get_quota_consumed_amount(
            subscription,
            raw_total_tokens=raw_total_tokens,
            total_cost=total_cost,
            quota_cost=quota_cost,
        )

        quota_limit = SubscriptionService._get_effective_quota_limit(subscription)
        cycle: Optional[SubscriptionUsageCycle] = None
        for _attempt in range(2):
            cycle = SubscriptionService._get_or_create_cycle(db, subscription, usage_now)
            updated = SubscriptionService._apply_cycle_consumption_update(
                db,
                cycle_id=cycle.id,
                consumed_amount=consumed_amount,
                request_id=request_id,
                quota_metric=quota_metric,
                quota_limit=quota_limit,
            )
            if updated:
                db.flush()
                refreshed_cycle = SubscriptionService._load_cycle_by_id(db, cycle.id)
                if not refreshed_cycle:
                    break
                return {
                    "subscription_cycle_id": refreshed_cycle.id,
                    "quota_metric": quota_metric,
                    "quota_consumed_amount": consumed_amount,
                    "quota_limit_snapshot": quota_limit,
                    "quota_used_after": SubscriptionService._normalize_decimal(refreshed_cycle.used_amount),
                    "quota_cycle_date": refreshed_cycle.cycle_date,
                }

        raise ServiceException(500, "套餐额度记账失败，请稍后重试", "SUBSCRIPTION_QUOTA_UPDATE_FAILED")

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
        agent_id: Optional[int] = None,
    ) -> UserSubscription:
        current_time = SubscriptionService.get_current_time()
        return UserSubscription(
            user_id=user_id,
            agent_id=agent_id,
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
            raise ServiceException(400, "套餐时长必须大于 0", "INVALID_DURATION")

        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")

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
            quota_metric=(
                SubscriptionService.QUOTA_METRIC_COST
                if SubscriptionService._normalized_text(plan_type) in {"daily", "weekly", "monthly"}
                and start_time >= SubscriptionService.QUOTA_RULE_CUTOVER_AT
                else None
            ),
            quota_value=(
                SubscriptionService.UNLIMITED_MONTHLY_DAILY_COST_LIMIT
                if SubscriptionService._normalized_text(plan_type) in {"daily", "weekly", "monthly"}
                and start_time >= SubscriptionService.QUOTA_RULE_CUTOVER_AT
                else Decimal("0")
            ),
            agent_id=user.agent_id,
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
        auto_commit: bool = True,
        agent_id: Optional[int] = None,
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise ServiceException(404, "套餐模板不存在", "PLAN_NOT_FOUND")
        if plan.status != "active":
            raise ServiceException(400, "套餐模板未启用", "PLAN_INACTIVE")
        if activation_mode not in {"append", "override"}:
            raise ServiceException(400, "套餐生效模式不合法", "INVALID_ACTIVATION_MODE")

        now = SubscriptionService.get_current_time()
        current_active = SubscriptionService.resolve_active_subscription(db, user_id, now)
        start_time = now
        if activation_mode == "append" and current_active and current_active.end_time > now:
            start_time = current_active.end_time
        elif activation_mode == "override" and current_active:
            current_active.status = "cancelled"

        end_time = start_time + timedelta(days=int(plan.duration_days))
        plan_strategy = SubscriptionService._resolve_plan_quota_strategy(plan)
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
            quota_metric=plan_strategy["quota_metric"],
            quota_value=plan_strategy["quota_limit"],
            reset_period=plan.reset_period,
            reset_timezone=plan.reset_timezone,
            agent_id=agent_id if agent_id is not None else user.agent_id,
        )
        db.add(subscription)
        db.flush()
        SubscriptionService.refresh_user_subscription_state(db, user_id, now)
        if auto_commit:
            db.commit()
            db.refresh(subscription)
        return SubscriptionService._serialize_subscription(subscription)

    @staticmethod
    def cancel_subscription(db: Session, user_id: int) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")

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
            "message": "套餐已取消，已切换为余额模式",
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
            if SubscriptionService._requires_daily_cycle(subscription):
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
        now = SubscriptionService.get_current_time()
        if status:
            if status == "active":
                query = query.filter(
                    SubscriptionService._active_status_filter(),
                    UserSubscription.start_time <= now,
                    UserSubscription.end_time >= now,
                )
            elif status == "expired":
                query = query.filter(
                    or_(UserSubscription.status.is_(None), UserSubscription.status != "cancelled"),
                    UserSubscription.end_time < now,
                )
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
            if SubscriptionService._requires_daily_cycle(subscription):
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
    def list_agent_subscriptions(
        db: Session,
        agent_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            db.query(UserSubscription, SysUser)
            .join(SysUser, UserSubscription.user_id == SysUser.id)
            .filter(UserSubscription.agent_id == agent_id)
        )
        now = SubscriptionService.get_current_time()
        if status:
            if status == "active":
                query = query.filter(
                    SubscriptionService._active_status_filter(),
                    UserSubscription.start_time <= now,
                    UserSubscription.end_time >= now,
                )
            elif status == "expired":
                query = query.filter(
                    or_(UserSubscription.status.is_(None), UserSubscription.status != "cancelled"),
                    UserSubscription.end_time < now,
                )
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
            if SubscriptionService._requires_daily_cycle(subscription):
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
            raise ServiceException(404, "套餐记录不存在", "SUBSCRIPTION_NOT_FOUND")

        subscription, user = row
        usage_summary = SubscriptionService._build_usage_summary_map(db, [subscription]).get(
            subscription.id,
            SubscriptionService._empty_usage_summary(),
        )
        current_cycle = None
        if SubscriptionService._requires_daily_cycle(subscription):
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
