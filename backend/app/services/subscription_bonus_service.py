"""Promotional quota grant management and rolling-cycle helpers."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.core.exceptions import ServiceException
from app.models.user import SysUser
from app.models.log import UserSubscription
from app.models.subscription_bonus import SubscriptionBonusGrant, SubscriptionBonusUsageCycle
from app.models.model import UnifiedModel
from app.services.subscription_service import SubscriptionService


class SubscriptionBonusService:
    @staticmethod
    def _serialize(grant: SubscriptionBonusGrant) -> dict:
        return {
            "id": grant.id, "grant_request_id": grant.grant_request_id,
            "user_id": grant.user_id, "source_subscription_id": grant.source_subscription_id,
            "duration_mode": grant.duration_mode, "duration_days": grant.duration_days,
            "daily_quota_usd": str(grant.daily_quota_usd),
            "model_series": json.loads(grant.model_series) if grant.model_series else [],
            "start_time": grant.start_time.isoformat(), "end_time": grant.end_time.isoformat(),
            "status": grant.status, "remark": grant.remark,
        }

    @staticmethod
    def create_grant(db: Session, payload: dict, operator_id: int) -> dict:
        user_id = int(payload["user_id"])
        user = db.query(SysUser).filter(SysUser.id == user_id).with_for_update().first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        normalized = dict(payload)
        normalized["daily_quota_usd"] = str(Decimal(str(payload["daily_quota_usd"])))
        digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        existing = db.query(SubscriptionBonusGrant).filter(
            SubscriptionBonusGrant.grant_request_id == payload["grant_request_id"]
        ).first()
        if existing:
            if existing.normalized_payload_hash != digest:
                raise ServiceException(409, "赠送请求幂等键内容冲突", "IDEMPOTENCY_CONFLICT")
            return SubscriptionBonusService._serialize(existing)

        now = SubscriptionService.get_current_time()
        subscription = db.query(UserSubscription).filter(
            UserSubscription.id == int(payload["source_subscription_id"]),
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
            UserSubscription.start_time <= now,
            UserSubscription.end_time > now,
        ).first()
        if not subscription:
            raise ServiceException(400, "当前套餐不存在或已过期", "SUBSCRIPTION_NOT_ACTIVE")
        mode = str(payload.get("duration_mode") or "fixed_days")
        if mode not in {"fixed_days", "subscription_end"}:
            raise ServiceException(400, "赠送时长模式不合法", "INVALID_DURATION_MODE")
        if mode == "subscription_end":
            end_time = subscription.end_time
            days = None
        else:
            days = int(payload.get("duration_days") or 0)
            if days <= 0:
                raise ServiceException(400, "赠送天数必须大于 0", "INVALID_DURATION_DAYS")
            end_time = now + timedelta(days=days)
            if end_time > subscription.end_time:
                raise ServiceException(400, "赠送期限超过套餐到期时间", "BONUS_END_EXCEEDS_SUBSCRIPTION")
        grant = SubscriptionBonusGrant(
            grant_request_id=payload["grant_request_id"], normalized_payload_hash=digest,
            user_id=user_id, agent_id=getattr(user, "agent_id", None),
            source_subscription_id=subscription.id, duration_mode=mode, duration_days=days,
            daily_quota_usd=Decimal(str(payload["daily_quota_usd"])), start_time=now,
            end_time=end_time, status="active", created_by=operator_id, remark=payload.get("remark"),
            model_series=json.dumps(payload.get("model_series") or [], ensure_ascii=False),
        )
        db.add(grant)
        db.commit(); db.refresh(grant)
        return SubscriptionBonusService._serialize(grant)

    @staticmethod
    def list_grants(db: Session, user_id: int) -> list[dict]:
        rows = db.query(SubscriptionBonusGrant).filter(
            SubscriptionBonusGrant.user_id == user_id
        ).order_by(SubscriptionBonusGrant.end_time.asc(), SubscriptionBonusGrant.id.asc()).all()
        return [SubscriptionBonusService._serialize(row) for row in rows]

    @staticmethod
    def active_summary(db: Session, user_id: int, now=None) -> list[dict]:
        now = now or SubscriptionService.get_current_time()
        grants = db.query(SubscriptionBonusGrant).filter(
            SubscriptionBonusGrant.user_id == user_id,
            SubscriptionBonusGrant.status == "active",
            SubscriptionBonusGrant.start_time <= now,
            SubscriptionBonusGrant.end_time > now,
        ).order_by(SubscriptionBonusGrant.end_time.asc(), SubscriptionBonusGrant.id.asc()).all()
        enabled_series = [row[0] for row in db.query(UnifiedModel.model_series).filter(
            UnifiedModel.enabled == 1,
            UnifiedModel.bonus_quota_enabled == 1,
        ).distinct().all() if row[0]]
        # Keep the configured series when available and infer legacy rows defensively.
        enabled_series = sorted({str(series).strip().lower() for series in enabled_series if series})
        result = []
        for grant in grants:
            index = int((now - grant.start_time).total_seconds() // 86400)
            cycle = db.query(SubscriptionBonusUsageCycle).filter_by(bonus_grant_id=grant.id, cycle_index=index).first()
            quota = Decimal(str((cycle.quota_limit_usd if cycle else grant.daily_quota_usd) or 0))
            used = Decimal(str((cycle.used_amount_usd if cycle else 0) or 0))
            reserved = Decimal(str((cycle.reserved_amount_usd if cycle else 0) or 0))
            cycle_end = min(grant.start_time + timedelta(days=index + 1), grant.end_time)
            result.append({
                "grant_id": grant.id,
                "daily_quota_usd": float(quota),
                "used_amount_usd": float(used),
                "reserved_amount_usd": float(reserved),
                "remaining_amount_usd": float(max(quota - used - reserved, Decimal("0"))),
                "start_time": grant.start_time.isoformat(),
                "end_time": grant.end_time.isoformat(),
                "next_reset_at": (cycle.cycle_end_at if cycle else cycle_end).isoformat(),
                "model_series": json.loads(grant.model_series) if grant.model_series else [],
                "eligible_model_series": enabled_series,
                "model_scope": "selected_series" if grant.model_series else "all_bonus_models",
            })
        return result

    @staticmethod
    def cancel_grant(db: Session, grant_id: int, operator_id: int, reason: str | None = None) -> dict:
        grant = db.query(SubscriptionBonusGrant).filter(SubscriptionBonusGrant.id == grant_id).with_for_update().first()
        if not grant:
            raise ServiceException(404, "赠送批次不存在", "BONUS_GRANT_NOT_FOUND")
        if grant.status != "cancelled":
            grant.status = "cancelled"; grant.cancelled_by = operator_id
            grant.cancel_reason = reason; grant.cancelled_at = SubscriptionService.get_current_time()
            db.commit(); db.refresh(grant)
        return SubscriptionBonusService._serialize(grant)

    @staticmethod
    def get_or_create_cycle(db: Session, grant: SubscriptionBonusGrant, now):
        if now < grant.start_time or now >= grant.end_time:
            return None
        index = int((now - grant.start_time).total_seconds() // 86400)
        start = grant.start_time + timedelta(days=index)
        end = min(start + timedelta(days=1), grant.end_time)
        cycle = db.query(SubscriptionBonusUsageCycle).filter_by(
            bonus_grant_id=grant.id, cycle_index=index
        ).with_for_update().first()
        if cycle:
            return cycle
        cycle = SubscriptionBonusUsageCycle(
            bonus_grant_id=grant.id, user_id=grant.user_id, cycle_index=index,
            cycle_date=start.date(), cycle_start_at=start, cycle_end_at=end,
            quota_limit_usd=grant.daily_quota_usd,
        )
        db.add(cycle); db.flush()
        return cycle

    @staticmethod
    def consume_available(db: Session, user_id: int, amount: Decimal, now) -> Decimal:
        """Consume promotional USD quota from earliest-expiring active grants."""
        remaining = Decimal(str(amount or 0))
        consumed = Decimal("0")
        if remaining <= 0:
            return consumed
        grants = db.query(SubscriptionBonusGrant).filter(
            SubscriptionBonusGrant.user_id == user_id,
            SubscriptionBonusGrant.status == "active",
            SubscriptionBonusGrant.start_time <= now,
            SubscriptionBonusGrant.end_time > now,
        ).order_by(SubscriptionBonusGrant.end_time.asc(), SubscriptionBonusGrant.id.asc()).with_for_update().all()
        for grant in grants:
            if remaining <= 0:
                break
            cycle = SubscriptionBonusService.get_or_create_cycle(db, grant, now)
            if not cycle:
                continue
            available = Decimal(str(cycle.quota_limit_usd or 0)) - Decimal(str(cycle.used_amount_usd or 0)) - Decimal(str(cycle.reserved_amount_usd or 0))
            take = min(max(available, Decimal("0")), remaining)
            if take <= 0:
                continue
            cycle.used_amount_usd = Decimal(str(cycle.used_amount_usd or 0)) + take
            cycle.request_count = int(cycle.request_count or 0) + 1
            cycle.version = int(cycle.version or 0) + 1
            consumed += take
            remaining -= take
        return consumed
