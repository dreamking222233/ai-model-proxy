"""Balance management service."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.log import UserBalance, ConsumptionRecord
from app.core.exceptions import ServiceException


class BalanceService:
    """User balance queries and admin recharge operations."""

    @staticmethod
    def get_balance(db: Session, user_id: int) -> dict:
        """
        Get the balance record for a user.

        Returns:
            dict with ``user_id``, ``balance``, ``total_recharged``, ``total_consumed``.

        Raises:
            ServiceException: if balance record not found.
        """
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
        }

    @staticmethod
    def recharge(db: Session, user_id: int, amount: Decimal, operator_id: int) -> dict:
        """
        Add funds to a user's balance.

        Uses ``SELECT ... FOR UPDATE`` to prevent race conditions.

        Args:
            user_id: target user.
            amount: positive Decimal amount to add.
            operator_id: admin user performing the recharge.

        Returns:
            dict with updated balance info.

        Raises:
            ServiceException: if balance record not found or amount invalid.
        """
        if amount <= 0:
            raise ServiceException(400, "Recharge amount must be positive", "INVALID_AMOUNT")

        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        balance_before = float(balance.balance)
        balance.balance += amount
        balance.total_recharged += amount

        # Write a consumption record for the recharge (positive amount)
        record = ConsumptionRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=-amount,  # negative cost = recharge
            balance_before=Decimal(str(balance_before)),
            balance_after=balance.balance,
        )
        db.add(record)
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "recharged_amount": float(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def deduct(db: Session, user_id: int, amount: Decimal, operator_id: int, reason: str = None) -> dict:
        """
        Deduct funds from a user's balance (admin operation).

        Args:
            user_id: target user.
            amount: positive Decimal amount to deduct.
            operator_id: admin user performing the deduction.
            reason: optional reason for deduction.

        Returns:
            dict with updated balance info.

        Raises:
            ServiceException: if balance record not found, amount invalid, or insufficient balance.
        """
        if amount <= 0:
            raise ServiceException(400, "Deduct amount must be positive", "INVALID_AMOUNT")

        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "Balance record not found", "BALANCE_NOT_FOUND")

        if balance.balance < amount:
            raise ServiceException(400, "Insufficient balance", "INSUFFICIENT_BALANCE")

        balance_before = float(balance.balance)
        balance.balance -= amount
        balance.total_consumed += amount

        record = ConsumptionRecord(
            user_id=user_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=amount,  # positive cost = deduction
            balance_before=Decimal(str(balance_before)),
            balance_after=balance.balance,
        )
        db.add(record)
        db.commit()
        db.refresh(balance)

        return {
            "user_id": balance.user_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_consumed": float(balance.total_consumed),
            "deducted_amount": float(amount),
            "operator_id": operator_id,
        }

    @staticmethod
    def get_consumption_records(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List consumption records for a user with pagination.

        Returns:
            Tuple of (list of record dicts, total count).
        """
        query = db.query(ConsumptionRecord).filter(ConsumptionRecord.user_id == user_id)

        total = query.count()
        records = (
            query.order_by(ConsumptionRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = [
            {
                "id": r.id,
                "user_id": r.user_id,
                "request_id": r.request_id,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "logical_input_tokens": r.logical_input_tokens or 0,
                "upstream_input_tokens": r.upstream_input_tokens or 0,
                "upstream_cache_read_input_tokens": r.upstream_cache_read_input_tokens or 0,
                "upstream_cache_creation_input_tokens": r.upstream_cache_creation_input_tokens or 0,
                "upstream_prompt_cache_status": r.upstream_prompt_cache_status or "BYPASS",
                "input_cost": float(r.input_cost),
                "output_cost": float(r.output_cost),
                "total_cost": float(r.total_cost),
                "balance_before": float(r.balance_before),
                "balance_after": float(r.balance_after),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
        return result, total
