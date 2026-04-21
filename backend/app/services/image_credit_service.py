"""Image credit balance and ledger service."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.log import UserImageBalance, ImageCreditRecord


class ImageCreditService:
    """Manage user image credits and ledger records."""

    _SCALE = Decimal("0.001")

    @staticmethod
    def _normalize_amount(value, field_name: str = "amount", allow_zero: bool = False) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(ImageCreditService._SCALE)
        except (InvalidOperation, TypeError, ValueError):
            raise ServiceException(400, f"Invalid {field_name}", "INVALID_IMAGE_CREDIT_AMOUNT")
        if allow_zero:
            if amount < Decimal("0"):
                raise ServiceException(400, f"{field_name} must not be negative", "INVALID_IMAGE_CREDIT_AMOUNT")
        elif amount <= Decimal("0"):
            raise ServiceException(400, f"{field_name} must be positive", "INVALID_IMAGE_CREDIT_AMOUNT")
        return amount

    @staticmethod
    def _to_number(value) -> float:
        return float((value or Decimal("0")).quantize(ImageCreditService._SCALE))

    @staticmethod
    def get_balance(db: Session, user_id: int) -> dict:
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if not balance:
            balance = ImageCreditService.ensure_balance_record(db, user_id)
            db.commit()
            db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": ImageCreditService._to_number(balance.balance),
            "total_recharged": ImageCreditService._to_number(balance.total_recharged),
            "total_consumed": ImageCreditService._to_number(balance.total_consumed),
            "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
        }

    @staticmethod
    def ensure_balance_record(db: Session, user_id: int) -> UserImageBalance:
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if balance:
            return balance

        balance = UserImageBalance(user_id=user_id, balance=Decimal("0"), total_recharged=Decimal("0"), total_consumed=Decimal("0"))
        db.add(balance)
        db.flush()
        return balance

    @staticmethod
    def recharge(db: Session, user_id: int, amount, operator_id: int | None = None, reason: str | None = None) -> dict:
        amount_decimal = ImageCreditService._normalize_amount(amount, "amount")

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = ImageCreditService.ensure_balance_record(db, user_id)
            db.flush()
            balance = (
                db.query(UserImageBalance)
                .filter(UserImageBalance.user_id == user_id)
                .with_for_update()
                .first()
            )

        balance_before = ImageCreditService._normalize_amount(balance.balance or 0, "balance", allow_zero=True)
        balance.balance = balance_before + amount_decimal
        balance.total_recharged = ImageCreditService._normalize_amount(balance.total_recharged or 0, "total_recharged", allow_zero=True) + amount_decimal

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            change_amount=amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            multiplier=Decimal("1"),
            action_type="recharge",
            operator_id=operator_id,
            remark=reason,
        ))
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": ImageCreditService._to_number(balance.balance),
            "total_recharged": ImageCreditService._to_number(balance.total_recharged),
            "total_consumed": ImageCreditService._to_number(balance.total_consumed),
            "recharged_amount": ImageCreditService._to_number(amount_decimal),
            "operator_id": operator_id,
        }

    @staticmethod
    def deduct(db: Session, user_id: int, amount, operator_id: int | None = None, reason: str | None = None) -> dict:
        amount_decimal = ImageCreditService._normalize_amount(amount, "amount")

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Image credit balance not found", "IMAGE_CREDIT_BALANCE_NOT_FOUND")

        balance_before = ImageCreditService._normalize_amount(balance.balance or 0, "balance", allow_zero=True)
        if balance_before < amount_decimal:
            raise ServiceException(400, "Insufficient image credits", "INSUFFICIENT_IMAGE_CREDITS")

        balance.balance = balance_before - amount_decimal
        balance.total_consumed = ImageCreditService._normalize_amount(balance.total_consumed or 0, "total_consumed", allow_zero=True) + amount_decimal

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            change_amount=-amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            multiplier=Decimal("1"),
            action_type="deduct",
            operator_id=operator_id,
            remark=reason,
        ))
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": ImageCreditService._to_number(balance.balance),
            "total_recharged": ImageCreditService._to_number(balance.total_recharged),
            "total_consumed": ImageCreditService._to_number(balance.total_consumed),
            "deducted_amount": ImageCreditService._to_number(amount_decimal),
            "operator_id": operator_id,
        }

    @staticmethod
    def check_balance(db: Session, user_id: int, amount) -> None:
        amount_decimal = ImageCreditService._normalize_amount(amount, "amount", allow_zero=True)
        if amount_decimal <= Decimal("0"):
            return
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if not balance or ImageCreditService._normalize_amount(balance.balance or 0, "balance", allow_zero=True) < amount_decimal:
            raise ServiceException(402, "图片积分不足，请联系管理员充值", "INSUFFICIENT_IMAGE_CREDITS")

    @staticmethod
    def deduct_for_request(
        db: Session,
        user_id: int,
        request_id: str,
        model_name: str,
        amount,
        multiplier,
        image_size: str | None = None,
        remark: str | None = None,
    ) -> dict:
        amount_decimal = ImageCreditService._normalize_amount(amount, "amount")
        multiplier_decimal = ImageCreditService._normalize_amount(multiplier, "multiplier")

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Image credit balance not found", "IMAGE_CREDIT_BALANCE_NOT_FOUND")

        balance_before = ImageCreditService._normalize_amount(balance.balance or 0, "balance", allow_zero=True)
        if balance_before < amount_decimal:
            raise ServiceException(402, "图片积分不足，请联系管理员充值", "INSUFFICIENT_IMAGE_CREDITS")

        balance.balance = balance_before - amount_decimal
        balance.total_consumed = ImageCreditService._normalize_amount(balance.total_consumed or 0, "total_consumed", allow_zero=True) + amount_decimal

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=request_id,
            model_name=model_name,
            change_amount=-amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            multiplier=multiplier_decimal,
            image_size=image_size,
            action_type="request",
            operator_id=None,
            remark=remark,
        ))
        db.flush()

        return {
            "balance_before": ImageCreditService._to_number(balance_before),
            "balance_after": ImageCreditService._to_number(balance.balance),
            "charged_amount": ImageCreditService._to_number(amount_decimal),
        }
