"""Redemption code service for generating and redeeming codes."""
from __future__ import annotations

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
        expires_days: int | None = None,
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
        expires_days: int | None = None,
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
    def redeem_code(db: Session, user_id: int, code: str) -> dict:
        """
        Redeem a code for a user.

        Args:
            user_id: The user redeeming the code.
            code: The redemption code.

        Returns:
            Dict with redemption result.

        Raises:
            ServiceException: If code is invalid, already used, or expired.
        """
        # Find the code
        redemption = db.query(RedemptionCode).filter(
            RedemptionCode.code == code.upper()
        ).first()

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
        status: str | None = None,
        created_by: int | None = None,
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
