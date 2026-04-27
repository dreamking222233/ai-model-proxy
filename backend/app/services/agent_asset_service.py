"""Agent asset pool orchestration service."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.agent import (
    Agent,
    AgentBalance,
    AgentBalanceRecord,
    AgentImageBalance,
    AgentImageCreditRecord,
    AgentSubscriptionInventory,
    AgentSubscriptionInventoryRecord,
)
from app.models.log import ConsumptionRecord, ImageCreditRecord, UserBalance, UserImageBalance
from app.models.user import SysUser
from app.services.subscription_service import SubscriptionService


class AgentAssetService:
    """Transactional agent asset pool operations."""

    @staticmethod
    def _normalize_decimal(value, code: str, scale: str = "0.001") -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(Decimal(scale))
        except (InvalidOperation, TypeError, ValueError):
            raise ServiceException(400, "金额格式不正确", code)
        if amount <= Decimal("0"):
            raise ServiceException(400, "金额必须大于 0", code)
        return amount

    @staticmethod
    def _get_agent(db: Session, agent_id: int) -> Agent:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")
        return agent

    @staticmethod
    def _get_agent_balance_for_update(db: Session, agent_id: int) -> AgentBalance:
        balance = (
            db.query(AgentBalance)
            .filter(AgentBalance.agent_id == agent_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = AgentBalance(agent_id=agent_id, balance=0, total_recharged=0, total_allocated=0, total_reclaimed=0)
            db.add(balance)
            db.flush()
            balance = (
                db.query(AgentBalance)
                .filter(AgentBalance.agent_id == agent_id)
                .with_for_update()
                .first()
            )
        return balance

    @staticmethod
    def _get_agent_image_balance_for_update(db: Session, agent_id: int) -> AgentImageBalance:
        balance = (
            db.query(AgentImageBalance)
            .filter(AgentImageBalance.agent_id == agent_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = AgentImageBalance(agent_id=agent_id, balance=0, total_recharged=0, total_allocated=0, total_reclaimed=0)
            db.add(balance)
            db.flush()
            balance = (
                db.query(AgentImageBalance)
                .filter(AgentImageBalance.agent_id == agent_id)
                .with_for_update()
                .first()
            )
        return balance

    @staticmethod
    def _get_agent_subscription_inventory_for_update(
        db: Session,
        agent_id: int,
        plan_id: int,
    ) -> AgentSubscriptionInventory:
        inventory = (
            db.query(AgentSubscriptionInventory)
            .filter(
                AgentSubscriptionInventory.agent_id == agent_id,
                AgentSubscriptionInventory.plan_id == plan_id,
            )
            .with_for_update()
            .first()
        )
        if not inventory:
            inventory = AgentSubscriptionInventory(
                agent_id=agent_id,
                plan_id=plan_id,
                total_granted=0,
                total_used=0,
                remaining_count=0,
            )
            db.add(inventory)
            db.flush()
            inventory = (
                db.query(AgentSubscriptionInventory)
                .filter(
                    AgentSubscriptionInventory.agent_id == agent_id,
                    AgentSubscriptionInventory.plan_id == plan_id,
                )
                .with_for_update()
                .first()
            )
        return inventory

    @staticmethod
    def recharge_agent_balance(
        db: Session,
        agent_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        AgentAssetService._get_agent(db, agent_id)
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_BALANCE_AMOUNT", "0.000001")
        balance = AgentAssetService._get_agent_balance_for_update(db, agent_id)
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + amount_decimal
        balance.total_recharged = Decimal(str(balance.total_recharged or 0)) + amount_decimal

        db.add(AgentBalanceRecord(
            agent_id=agent_id,
            target_user_id=None,
            related_code_id=None,
            action_type="platform_recharge",
            change_amount=amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(balance)
        return {
            "agent_id": agent_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_allocated": float(balance.total_allocated),
            "total_reclaimed": float(balance.total_reclaimed),
            "recharged_amount": float(amount_decimal),
        }

    @staticmethod
    def recharge_agent_image_balance(
        db: Session,
        agent_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        AgentAssetService._get_agent(db, agent_id)
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_IMAGE_BALANCE_AMOUNT", "0.001")
        balance = AgentAssetService._get_agent_image_balance_for_update(db, agent_id)
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + amount_decimal
        balance.total_recharged = Decimal(str(balance.total_recharged or 0)) + amount_decimal

        db.add(AgentImageCreditRecord(
            agent_id=agent_id,
            target_user_id=None,
            action_type="platform_recharge",
            change_amount=amount_decimal,
            balance_before=balance_before,
            balance_after=balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(balance)
        return {
            "agent_id": agent_id,
            "balance": float(balance.balance),
            "total_recharged": float(balance.total_recharged),
            "total_allocated": float(balance.total_allocated),
            "total_reclaimed": float(balance.total_reclaimed),
            "recharged_amount": float(amount_decimal),
        }

    @staticmethod
    def grant_user_balance(
        db: Session,
        agent_id: int,
        user_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_BALANCE_AMOUNT", "0.000001")
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.role != "user":
            raise ServiceException(403, "代理余额只能发放给终端用户", "INVALID_AGENT_TARGET_USER")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        agent_balance = AgentAssetService._get_agent_balance_for_update(db, agent_id)
        if Decimal(str(agent_balance.balance or 0)) < amount_decimal:
            raise ServiceException(400, "代理余额不足", "AGENT_BALANCE_INSUFFICIENT")

        user_balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not user_balance:
            raise ServiceException(404, "用户余额记录不存在", "BALANCE_NOT_FOUND")

        agent_before = Decimal(str(agent_balance.balance or 0))
        user_before = Decimal(str(user_balance.balance or 0))

        agent_balance.balance = agent_before - amount_decimal
        agent_balance.total_allocated = Decimal(str(agent_balance.total_allocated or 0)) + amount_decimal
        user_balance.balance = user_before + amount_decimal
        user_balance.total_recharged = Decimal(str(user_balance.total_recharged or 0)) + amount_decimal

        db.add(AgentBalanceRecord(
            agent_id=agent_id,
            target_user_id=user_id,
            related_code_id=None,
            action_type="grant_user_balance",
            change_amount=-amount_decimal,
            balance_before=agent_before,
            balance_after=agent_balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.add(ConsumptionRecord(
            user_id=user_id,
            agent_id=agent_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=-amount_decimal,
            balance_before=user_before,
            balance_after=user_balance.balance,
        ))
        db.commit()
        db.refresh(agent_balance)
        db.refresh(user_balance)
        return {
            "agent_id": agent_id,
            "user_id": user_id,
            "agent_balance": float(agent_balance.balance),
            "user_balance": float(user_balance.balance),
            "allocated_amount": float(amount_decimal),
        }

    @staticmethod
    def reclaim_user_balance(
        db: Session,
        agent_id: int,
        user_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_BALANCE_AMOUNT", "0.000001")
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.role != "user":
            raise ServiceException(403, "只能从终端用户回收代理余额", "INVALID_AGENT_TARGET_USER")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        agent_balance = AgentAssetService._get_agent_balance_for_update(db, agent_id)
        user_balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not user_balance:
            raise ServiceException(404, "用户余额记录不存在", "BALANCE_NOT_FOUND")

        user_before = Decimal(str(user_balance.balance or 0))
        if user_before < amount_decimal:
            raise ServiceException(400, "用户余额不足", "INSUFFICIENT_BALANCE")
        agent_before = Decimal(str(agent_balance.balance or 0))

        user_balance.balance = user_before - amount_decimal
        user_balance.total_consumed = Decimal(str(user_balance.total_consumed or 0)) + amount_decimal
        agent_balance.balance = agent_before + amount_decimal
        agent_balance.total_reclaimed = Decimal(str(agent_balance.total_reclaimed or 0)) + amount_decimal

        db.add(AgentBalanceRecord(
            agent_id=agent_id,
            target_user_id=user_id,
            related_code_id=None,
            action_type="reclaim_user_balance",
            change_amount=amount_decimal,
            balance_before=agent_before,
            balance_after=agent_balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.add(ConsumptionRecord(
            user_id=user_id,
            agent_id=agent_id,
            request_id=None,
            model_name=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=amount_decimal,
            balance_before=user_before,
            balance_after=user_balance.balance,
        ))
        db.commit()
        db.refresh(agent_balance)
        db.refresh(user_balance)
        return {
            "agent_id": agent_id,
            "user_id": user_id,
            "agent_balance": float(agent_balance.balance),
            "user_balance": float(user_balance.balance),
            "reclaimed_amount": float(amount_decimal),
        }

    @staticmethod
    def grant_user_image_credits(
        db: Session,
        agent_id: int,
        user_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_IMAGE_BALANCE_AMOUNT", "0.001")
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.role != "user":
            raise ServiceException(403, "代理图片积分只能发放给终端用户", "INVALID_AGENT_TARGET_USER")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        agent_balance = AgentAssetService._get_agent_image_balance_for_update(db, agent_id)
        if Decimal(str(agent_balance.balance or 0)) < amount_decimal:
            raise ServiceException(400, "代理图片积分不足", "AGENT_IMAGE_BALANCE_INSUFFICIENT")

        user_balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not user_balance:
            user_balance = UserImageBalance(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
            db.add(user_balance)
            db.flush()
            user_balance = (
                db.query(UserImageBalance)
                .filter(UserImageBalance.user_id == user_id)
                .with_for_update()
                .first()
            )

        agent_before = Decimal(str(agent_balance.balance or 0))
        user_before = Decimal(str(user_balance.balance or 0))

        agent_balance.balance = agent_before - amount_decimal
        agent_balance.total_allocated = Decimal(str(agent_balance.total_allocated or 0)) + amount_decimal
        user_balance.balance = user_before + amount_decimal
        user_balance.total_recharged = Decimal(str(user_balance.total_recharged or 0)) + amount_decimal

        db.add(AgentImageCreditRecord(
            agent_id=agent_id,
            target_user_id=user_id,
            action_type="grant_user_image_credit",
            change_amount=-amount_decimal,
            balance_before=agent_before,
            balance_after=agent_balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.add(ImageCreditRecord(
            user_id=user_id,
            agent_id=agent_id,
            request_id=None,
            model_name=None,
            change_amount=amount_decimal,
            balance_before=user_before,
            balance_after=user_balance.balance,
            multiplier=Decimal("1"),
            action_type="recharge",
            operator_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(agent_balance)
        db.refresh(user_balance)
        return {
            "agent_id": agent_id,
            "user_id": user_id,
            "agent_image_credit_balance": float(agent_balance.balance),
            "user_image_credit_balance": float(user_balance.balance),
            "allocated_amount": float(amount_decimal),
        }

    @staticmethod
    def reclaim_user_image_credits(
        db: Session,
        agent_id: int,
        user_id: int,
        amount,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        amount_decimal = AgentAssetService._normalize_decimal(amount, "INVALID_AGENT_IMAGE_BALANCE_AMOUNT", "0.001")
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.role != "user":
            raise ServiceException(403, "只能从终端用户回收图片积分", "INVALID_AGENT_TARGET_USER")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        agent_balance = AgentAssetService._get_agent_image_balance_for_update(db, agent_id)
        user_balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not user_balance:
            raise ServiceException(404, "用户图片积分记录不存在", "IMAGE_CREDIT_BALANCE_NOT_FOUND")

        user_before = Decimal(str(user_balance.balance or 0))
        if user_before < amount_decimal:
            raise ServiceException(400, "用户图片积分不足", "INSUFFICIENT_IMAGE_CREDITS")
        agent_before = Decimal(str(agent_balance.balance or 0))

        user_balance.balance = user_before - amount_decimal
        user_balance.total_consumed = Decimal(str(user_balance.total_consumed or 0)) + amount_decimal
        agent_balance.balance = agent_before + amount_decimal
        agent_balance.total_reclaimed = Decimal(str(agent_balance.total_reclaimed or 0)) + amount_decimal

        db.add(AgentImageCreditRecord(
            agent_id=agent_id,
            target_user_id=user_id,
            action_type="reclaim_user_image_credit",
            change_amount=amount_decimal,
            balance_before=agent_before,
            balance_after=agent_balance.balance,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.add(ImageCreditRecord(
            user_id=user_id,
            agent_id=agent_id,
            request_id=None,
            model_name=None,
            change_amount=-amount_decimal,
            balance_before=user_before,
            balance_after=user_balance.balance,
            multiplier=Decimal("1"),
            action_type="deduct",
            operator_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(agent_balance)
        db.refresh(user_balance)
        return {
            "agent_id": agent_id,
            "user_id": user_id,
            "agent_image_credit_balance": float(agent_balance.balance),
            "user_image_credit_balance": float(user_balance.balance),
            "reclaimed_amount": float(amount_decimal),
        }

    @staticmethod
    def recharge_agent_subscription_inventory(
        db: Session,
        agent_id: int,
        plan_id: int,
        count: int,
        operator_user_id: int | None = None,
        remark: str | None = None,
    ) -> dict:
        AgentAssetService._get_agent(db, agent_id)
        if int(count or 0) <= 0:
            raise ServiceException(400, "库存数量必须大于 0", "INVALID_SUBSCRIPTION_INVENTORY_COUNT")
        inventory = AgentAssetService._get_agent_subscription_inventory_for_update(db, agent_id, plan_id)
        before = int(inventory.remaining_count or 0)
        inventory.total_granted = int(inventory.total_granted or 0) + int(count)
        inventory.remaining_count = before + int(count)

        db.add(AgentSubscriptionInventoryRecord(
            agent_id=agent_id,
            plan_id=plan_id,
            target_user_id=None,
            action_type="platform_recharge",
            change_count=int(count),
            remaining_before=before,
            remaining_after=inventory.remaining_count,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        db.refresh(inventory)
        return {
            "agent_id": agent_id,
            "plan_id": plan_id,
            "total_granted": inventory.total_granted,
            "total_used": inventory.total_used,
            "remaining_count": inventory.remaining_count,
            "recharged_count": int(count),
        }

    @staticmethod
    def grant_user_subscription(
        db: Session,
        agent_id: int,
        user_id: int,
        plan_id: int,
        operator_user_id: int | None = None,
        activation_mode: str = "append",
        remark: str | None = None,
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.role != "user":
            raise ServiceException(403, "代理套餐只能发放给终端用户", "INVALID_AGENT_TARGET_USER")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        inventory = AgentAssetService._get_agent_subscription_inventory_for_update(db, agent_id, plan_id)
        before = int(inventory.remaining_count or 0)
        if before <= 0:
            raise ServiceException(400, "代理套餐库存不足", "AGENT_SUBSCRIPTION_INVENTORY_INSUFFICIENT")

        inventory.total_used = int(inventory.total_used or 0) + 1
        inventory.remaining_count = before - 1

        result = SubscriptionService.activate_plan_subscription(
            db,
            user_id=user_id,
            plan_id=plan_id,
            operator_id=operator_user_id,
            activation_mode=activation_mode,
            auto_commit=False,
            agent_id=agent_id,
        )
        subscription_id = result.get("id")

        db.add(AgentSubscriptionInventoryRecord(
            agent_id=agent_id,
            plan_id=plan_id,
            target_user_id=user_id,
            action_type="grant_user_subscription",
            change_count=-1,
            remaining_before=before,
            remaining_after=inventory.remaining_count,
            operator_user_id=operator_user_id,
            remark=remark,
        ))
        db.commit()
        return {
            "agent_id": agent_id,
            "user_id": user_id,
            "plan_id": plan_id,
            "subscription_id": subscription_id,
            "remaining_count": inventory.remaining_count,
            "subscription": result,
        }
