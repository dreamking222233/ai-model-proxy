"""Subscription management service."""
from __future__ import annotations

from typing import Optional

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.user import SysUser
from app.models.log import ConsumptionRecord, UserSubscription
from app.core.exceptions import ServiceException


class SubscriptionService:
    """User subscription management operations."""

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
    def _serialize_subscription(
        subscription: UserSubscription,
        user: Optional[SysUser] = None,
        usage_summary: Optional[dict] = None,
    ) -> dict:
        result = {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "plan_name": subscription.plan_name,
            "plan_type": subscription.plan_type,
            "start_time": subscription.start_time.isoformat() if subscription.start_time else None,
            "end_time": subscription.end_time.isoformat() if subscription.end_time else None,
            "status": subscription.status,
            "created_by": subscription.created_by,
            "created_at": subscription.created_at.isoformat() if subscription.created_at else None,
            "updated_at": subscription.updated_at.isoformat() if subscription.updated_at else None,
            "usage_summary": usage_summary or SubscriptionService._empty_usage_summary(),
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

        summary_map = {
            subscription.id: SubscriptionService._empty_usage_summary()
            for subscription in subscriptions
        }
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
            "input_cost": float(record.input_cost),
            "output_cost": float(record.output_cost),
            "total_cost": float(record.total_cost),
            "balance_before": float(record.balance_before),
            "balance_after": float(record.balance_after),
            "billing_mode": record.billing_mode,
            "subscription_id": record.subscription_id,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    @staticmethod
    def activate_subscription(
        db: Session,
        user_id: int,
        plan_name: str,
        plan_type: str,
        duration_days: int,
        operator_id: int,
    ) -> dict:
        """
        Activate a subscription for a user.

        Args:
            user_id: target user.
            plan_name: subscription plan name (e.g., "月卡", "季卡", "年卡").
            plan_type: plan type (monthly/quarterly/yearly/custom).
            duration_days: subscription duration in days.
            operator_id: admin user performing the operation.

        Returns:
            dict with subscription info.

        Raises:
            ServiceException: if user not found or invalid parameters.
        """
        if duration_days <= 0:
            raise ServiceException(400, "Duration must be positive", "INVALID_DURATION")

        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        # Calculate start and end time
        start_time = datetime.utcnow()

        # If user already has an active subscription, extend from current expiration
        if user.subscription_type == "unlimited" and user.subscription_expires_at:
            if user.subscription_expires_at > start_time:
                start_time = user.subscription_expires_at

        end_time = start_time + timedelta(days=duration_days)

        # Update user subscription info
        user.subscription_type = "unlimited"
        user.subscription_expires_at = end_time

        # Create subscription record
        subscription = UserSubscription(
            user_id=user_id,
            plan_name=plan_name,
            plan_type=plan_type,
            start_time=start_time,
            end_time=end_time,
            status="active",
            created_by=operator_id,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        return {
            "id": subscription.id,
            "user_id": subscription.user_id,
            "plan_name": subscription.plan_name,
            "plan_type": subscription.plan_type,
            "start_time": subscription.start_time.isoformat(),
            "end_time": subscription.end_time.isoformat(),
            "status": subscription.status,
            "created_by": subscription.created_by,
        }

    @staticmethod
    def cancel_subscription(db: Session, user_id: int) -> dict:
        """
        Cancel a user's subscription and switch to balance mode.

        Args:
            user_id: target user.

        Returns:
            dict with updated user info.

        Raises:
            ServiceException: if user not found.
        """
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        # Switch to balance mode
        user.subscription_type = "balance"
        user.subscription_expires_at = None

        # Mark active subscriptions as cancelled
        active_subs = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.user_id == user_id,
                UserSubscription.status == "active",
            )
            .all()
        )
        for sub in active_subs:
            sub.status = "cancelled"

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
        """
        List subscription records for a user with pagination.

        Returns:
            Tuple of (list of subscription dicts, total count).
        """
        query = db.query(UserSubscription).filter(UserSubscription.user_id == user_id)

        total = query.count()
        subscriptions = (
            query.order_by(UserSubscription.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        usage_summary_map = SubscriptionService._build_usage_summary_map(db, subscriptions)
        result = [
            SubscriptionService._serialize_subscription(
                s,
                usage_summary=usage_summary_map.get(s.id),
            )
            for s in subscriptions
        ]
        return result, total

    @staticmethod
    def list_all_subscriptions(
        db: Session,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List all subscription records with optional status filter.

        Returns:
            Tuple of (list of subscription dicts with user info, total count).
        """
        query = db.query(UserSubscription, SysUser).join(
            SysUser, UserSubscription.user_id == SysUser.id
        )

        if status:
            query = query.filter(UserSubscription.status == status)

        total = query.count()
        results = (
            query.order_by(UserSubscription.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        subscriptions = [sub for sub, _ in results]
        usage_summary_map = SubscriptionService._build_usage_summary_map(db, subscriptions)
        result = [
            SubscriptionService._serialize_subscription(
                sub,
                user=user,
                usage_summary=usage_summary_map.get(sub.id),
            )
            for sub, user in results
        ]
        return result, total

    @staticmethod
    def get_subscription_usage_detail(
        db: Session,
        subscription_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        subscription_row = (
            db.query(UserSubscription, SysUser)
            .join(SysUser, UserSubscription.user_id == SysUser.id)
            .filter(UserSubscription.id == subscription_id)
            .first()
        )
        if not subscription_row:
            raise ServiceException(404, "Subscription not found", "SUBSCRIPTION_NOT_FOUND")

        subscription, user = subscription_row
        usage_summary = SubscriptionService._build_usage_summary_map(db, [subscription]).get(
            subscription.id,
            SubscriptionService._empty_usage_summary(),
        )

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
            ),
            "summary": usage_summary,
            "records": [
                SubscriptionService._serialize_consumption_record(record)
                for record in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def check_and_expire_subscriptions(db: Session) -> int:
        """
        Check and expire subscriptions that have passed their end_time.
        This should be called by a scheduled task.

        Returns:
            Number of subscriptions expired.
        """
        now = datetime.utcnow()

        # Find active subscriptions that have expired
        expired_subs = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.status == "active",
                UserSubscription.end_time < now,
            )
            .all()
        )

        count = 0
        for sub in expired_subs:
            sub.status = "expired"

            # Recalculate the user's remaining subscription window after expiring this record.
            user = db.query(SysUser).filter(SysUser.id == sub.user_id).first()
            if user:
                latest_active_subscription = (
                    db.query(UserSubscription)
                    .filter(
                        UserSubscription.user_id == sub.user_id,
                        UserSubscription.status == "active",
                        UserSubscription.end_time >= now,
                    )
                    .order_by(UserSubscription.end_time.desc(), UserSubscription.id.desc())
                    .first()
                )
                if latest_active_subscription:
                    user.subscription_type = "unlimited"
                    user.subscription_expires_at = latest_active_subscription.end_time
                else:
                    user.subscription_type = "balance"
                    user.subscription_expires_at = None

            count += 1

        if count > 0:
            db.commit()

        return count
