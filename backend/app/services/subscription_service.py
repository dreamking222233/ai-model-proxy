"""Subscription management service."""
from __future__ import annotations

from typing import Optional

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import SysUser
from app.models.log import UserSubscription
from app.core.exceptions import ServiceException


class SubscriptionService:
    """User subscription management operations."""

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

        result = [
            {
                "id": s.id,
                "user_id": s.user_id,
                "plan_name": s.plan_name,
                "plan_type": s.plan_type,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "status": s.status,
                "created_by": s.created_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
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

        result = [
            {
                "id": sub.id,
                "user_id": sub.user_id,
                "username": user.username,
                "email": user.email,
                "plan_name": sub.plan_name,
                "plan_type": sub.plan_type,
                "start_time": sub.start_time.isoformat() if sub.start_time else None,
                "end_time": sub.end_time.isoformat() if sub.end_time else None,
                "status": sub.status,
                "created_by": sub.created_by,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
            }
            for sub, user in results
        ]
        return result, total

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

            # Update user subscription type to balance mode
            user = db.query(SysUser).filter(SysUser.id == sub.user_id).first()
            if user and user.subscription_type == "unlimited":
                user.subscription_type = "balance"
                user.subscription_expires_at = None

            count += 1

        if count > 0:
            db.commit()

        return count
