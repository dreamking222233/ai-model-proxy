"""Redemption code service for generating and redeeming codes."""
from __future__ import annotations

from typing import Optional

import secrets
import string
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.redemption import RedemptionCode
from app.models.log import UserBalance
from app.core.exceptions import ServiceException


class RedemptionService:
    """Service for managing redemption codes."""

    @staticmethod
    def generate_code(length: int = 16) -> str:
        """Generate a random redemption code."""
        chars = string.ascii_uppercase + string.digits
        # Exclude confusing characters: 0, O, I, 1
        chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('1', '')
        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def create_redemption_code(
        db: Session,
        admin_id: int,
        amount: float,
        expires_days: Optional[int] = None,
    ) -> dict:
        """
        Create a single redemption code.

        Args:
            admin_id: The admin user ID creating the code.
            amount: The amount to credit when redeemed.
            expires_days: Days until expiration (None = never expires).

        Returns:
            Dict with code details.
        """
        code = RedemptionService.generate_code()
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        redemption = RedemptionCode(
            code=code,
            amount=Decimal(str(amount)),
            status="unused",
            created_by=admin_id,
            expires_at=expires_at,
        )
        db.add(redemption)
        db.commit()
        db.refresh(redemption)

        return {
            "id": redemption.id,
            "code": redemption.code,
            "amount": float(redemption.amount),
            "status": redemption.status,
            "expires_at": redemption.expires_at.isoformat() if redemption.expires_at else None,
            "created_at": redemption.created_at.isoformat(),
        }

    @staticmethod
    def batch_create_codes(
        db: Session,
        admin_id: int,
        amount: float,
        count: int,
        expires_days: Optional[int] = None,
    ) -> list[dict]:
        """
        Batch create multiple redemption codes.

        Args:
            admin_id: The admin user ID creating the codes.
            amount: The amount to credit when redeemed.
            count: Number of codes to generate.
            expires_days: Days until expiration (None = never expires).

        Returns:
            List of code dicts.
        """
        if count > 1000:
            raise ServiceException(400, "Cannot generate more than 1000 codes at once")

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        codes = []
        for _ in range(count):
            code = RedemptionService.generate_code()
            redemption = RedemptionCode(
                code=code,
                amount=Decimal(str(amount)),
                status="unused",
                created_by=admin_id,
                expires_at=expires_at,
            )
            db.add(redemption)
            codes.append({
                "code": code,
                "amount": float(amount),
                "expires_at": expires_at.isoformat() if expires_at else None,
            })

        db.commit()
        return codes

    @staticmethod
    def check_user_redeemed(db: Session, user_id: int) -> bool:
        """
        Check if a user has already redeemed any code.

        Args:
            user_id: The user to check.

        Returns:
            True if the user has already redeemed a code.
        """
        count = db.query(RedemptionCode).filter(
            RedemptionCode.used_by == user_id,
            RedemptionCode.status == "used"
        ).count()
        return count > 0

    @staticmethod
    def get_user_redemption_info(db: Session, user_id: int) -> dict:
        """
        Get user's redemption usage info.

        Args:
            user_id: The user to query.

        Returns:
            Dict with has_redeemed flag and optional redemption details.
        """
        record = db.query(RedemptionCode).filter(
            RedemptionCode.used_by == user_id,
            RedemptionCode.status == "used"
        ).first()

        if record:
            return {
                "has_redeemed": True,
                "redeemed_amount": float(record.amount),
                "redeemed_at": record.used_at.isoformat() if record.used_at else None,
            }
        return {"has_redeemed": False}

    @staticmethod
    def redeem_code(db: Session, user_id: int, code: str) -> dict:
        """
        Redeem a code for a user.

        Each user can only redeem ONE code in total.

        Args:
            user_id: The user redeeming the code.
            code: The redemption code.

        Returns:
            Dict with redemption result.

        Raises:
            ServiceException: If code is invalid, already used, expired,
                              or user has already redeemed a code.
        """
        # Check if user has already redeemed any code (one-time limit)
        already_redeemed = db.query(RedemptionCode).filter(
            RedemptionCode.used_by == user_id,
            RedemptionCode.status == "used"
        ).count()
        if already_redeemed > 0:
            raise ServiceException(400, "每位用户仅能使用一次兑换码，您已兑换过", "USER_ALREADY_REDEEMED")

        # Find the code with row-level lock to prevent concurrent redemption
        redemption = db.query(RedemptionCode).filter(
            RedemptionCode.code == code.upper()
        ).with_for_update().first()

        if not redemption:
            raise ServiceException(404, "兑换码不存在", "CODE_NOT_FOUND")

        # Check if already used
        if redemption.status == "used":
            raise ServiceException(400, "兑换码已被使用", "CODE_ALREADY_USED")

        # Check if expired
        if redemption.status == "expired":
            raise ServiceException(400, "兑换码已过期", "CODE_EXPIRED")

        if redemption.expires_at and redemption.expires_at < datetime.utcnow():
            redemption.status = "expired"
            db.commit()
            raise ServiceException(400, "兑换码已过期", "CODE_EXPIRED")

        # Get user balance
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if not balance:
            raise ServiceException(404, "用户余额记录不存在", "BALANCE_NOT_FOUND")

        # Update balance
        old_balance = float(balance.balance)
        balance.balance += redemption.amount
        balance.total_recharged += redemption.amount

        # Mark code as used
        redemption.status = "used"
        redemption.used_by = user_id
        redemption.used_at = datetime.utcnow()

        db.commit()

        return {
            "amount": float(redemption.amount),
            "old_balance": old_balance,
            "new_balance": float(balance.balance),
            "redeemed_at": redemption.used_at.isoformat(),
        }

    @staticmethod
    def list_codes(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> tuple[list[dict], int]:
        """
        List redemption codes with pagination.

        Returns:
            Tuple of (list of codes, total count).
        """
        from app.models.user import SysUser

        query = db.query(RedemptionCode)

        if status:
            query = query.filter(RedemptionCode.status == status)
        if created_by:
            query = query.filter(RedemptionCode.created_by == created_by)

        total = query.count()
        codes = (
            query.order_by(RedemptionCode.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = []
        for c in codes:
            # Get username if code was used
            username = None
            if c.used_by:
                user = db.query(SysUser).filter(SysUser.id == c.used_by).first()
                if user:
                    username = user.username

            result.append({
                "id": c.id,
                "code": c.code,
                "amount": float(c.amount),
                "status": c.status,
                "created_by": c.created_by,
                "used_by": c.used_by,
                "username": username,
                "used_at": c.used_at.isoformat() if c.used_at else None,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "created_at": c.created_at.isoformat(),
            })

        return result, total

    @staticmethod
    def delete_code(db: Session, code_id: int) -> None:
        """Delete a redemption code (only if unused)."""
        code = db.query(RedemptionCode).filter(RedemptionCode.id == code_id).first()
        if not code:
            raise ServiceException(404, "兑换码不存在", "CODE_NOT_FOUND")

        if code.status == "used":
            raise ServiceException(400, "已使用的兑换码不能删除", "CODE_ALREADY_USED")

        db.delete(code)
        db.commit()
