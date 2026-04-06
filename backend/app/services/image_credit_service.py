"""Image credit balance and ledger service."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.log import UserImageBalance, ImageCreditRecord


class ImageCreditService:
    """Manage user image credits and ledger records."""

    @staticmethod
    def get_balance(db: Session, user_id: int) -> dict:
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if not balance:
            balance = ImageCreditService.ensure_balance_record(db, user_id)
            db.commit()
            db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": int(balance.balance or 0),
            "total_recharged": int(balance.total_recharged or 0),
            "total_consumed": int(balance.total_consumed or 0),
            "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
        }

    @staticmethod
    def ensure_balance_record(db: Session, user_id: int) -> UserImageBalance:
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if balance:
            return balance

        balance = UserImageBalance(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(balance)
        db.flush()
        return balance

    @staticmethod
    def recharge(db: Session, user_id: int, amount: int, operator_id: int | None = None, reason: str | None = None) -> dict:
        if amount <= 0:
            raise ServiceException(400, "Recharge amount must be positive", "INVALID_IMAGE_CREDIT_AMOUNT")

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

        balance_before = int(balance.balance or 0)
        balance.balance = balance_before + int(amount)
        balance.total_recharged = int(balance.total_recharged or 0) + int(amount)

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            change_amount=int(amount),
            balance_before=balance_before,
            balance_after=int(balance.balance),
            multiplier=1,
            action_type="recharge",
            operator_id=operator_id,
            remark=reason,
        ))
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": int(balance.balance or 0),
            "total_recharged": int(balance.total_recharged or 0),
            "total_consumed": int(balance.total_consumed or 0),
            "recharged_amount": int(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def deduct(db: Session, user_id: int, amount: int, operator_id: int | None = None, reason: str | None = None) -> dict:
        if amount <= 0:
            raise ServiceException(400, "Deduct amount must be positive", "INVALID_IMAGE_CREDIT_AMOUNT")

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Image credit balance not found", "IMAGE_CREDIT_BALANCE_NOT_FOUND")

        balance_before = int(balance.balance or 0)
        if balance_before < int(amount):
            raise ServiceException(400, "Insufficient image credits", "INSUFFICIENT_IMAGE_CREDITS")

        balance.balance = balance_before - int(amount)
        balance.total_consumed = int(balance.total_consumed or 0) + int(amount)

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            change_amount=-int(amount),
            balance_before=balance_before,
            balance_after=int(balance.balance),
            multiplier=1,
            action_type="deduct",
            operator_id=operator_id,
            remark=reason,
        ))
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": int(balance.balance or 0),
            "total_recharged": int(balance.total_recharged or 0),
            "total_consumed": int(balance.total_consumed or 0),
            "deducted_amount": int(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def check_balance(db: Session, user_id: int, amount: int) -> None:
        if amount <= 0:
            return
        balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        if not balance or int(balance.balance or 0) < int(amount):
            raise ServiceException(402, "图片积分不足，请联系管理员充值", "INSUFFICIENT_IMAGE_CREDITS")

    @staticmethod
    def deduct_for_request(
        db: Session,
        user_id: int,
        request_id: str,
        model_name: str,
        amount: int,
        multiplier: int,
        remark: str | None = None,
    ) -> dict:
        if amount <= 0:
            raise ServiceException(400, "Image credit amount must be positive", "INVALID_IMAGE_CREDIT_AMOUNT")

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Image credit balance not found", "IMAGE_CREDIT_BALANCE_NOT_FOUND")

        balance_before = int(balance.balance or 0)
        if balance_before < int(amount):
            raise ServiceException(402, "图片积分不足，请联系管理员充值", "INSUFFICIENT_IMAGE_CREDITS")

        balance.balance = balance_before - int(amount)
        balance.total_consumed = int(balance.total_consumed or 0) + int(amount)

        db.add(ImageCreditRecord(
            user_id=user_id,
            request_id=request_id,
            model_name=model_name,
            change_amount=-int(amount),
            balance_before=balance_before,
            balance_after=int(balance.balance),
            multiplier=int(multiplier or 1),
            action_type="request",
            operator_id=None,
            remark=remark,
        ))
        db.flush()

        return {
            "balance_before": balance_before,
            "balance_after": int(balance.balance),
            "charged_amount": int(amount),
        }
