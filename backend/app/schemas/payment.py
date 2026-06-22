"""Payment-related request schemas."""

from decimal import Decimal, InvalidOperation
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class UserRechargeOrderCreateRequest(BaseModel):
    """Create online recharge order request."""

    amount_cny: Optional[Decimal] = None
    payment_channel: str = Field("alipay", pattern="^(alipay|wechat)$")
    recharge_type: str = Field("balance", pattern="^(balance|image_credit|subscription)$")
    subscription_plan_id: Optional[int] = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_recharge_payload(self):
        if self.recharge_type == "subscription":
            if not self.subscription_plan_id:
                raise ValueError("套餐订单必须选择套餐模板")
            return self

        if self.amount_cny is None:
            raise ValueError("充值金额不能为空")
        try:
            value = Decimal(str(self.amount_cny))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("充值金额格式不正确") from exc
        if value < Decimal("1"):
            raise ValueError("充值金额不能小于 1")
        return self


class AgentCashAdjustRequest(BaseModel):
    """Admin manual agent cash adjustment request."""

    amount: Decimal
    remark: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_amount(self):
        try:
            value = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("调整金额格式不正确") from exc
        if value == Decimal("0"):
            raise ValueError("调整金额不能为 0")
        return self


class AgentCashWithdrawRequest(BaseModel):
    """Admin offline withdrawal request."""

    amount: Decimal = Field(..., gt=0)
    transfer_method: str = Field("offline_other", max_length=32)
    remark: Optional[str] = Field(None, max_length=255)


class AgentSubscriptionSaleSettleRequest(BaseModel):
    """Admin subscription sale rebate settlement request."""

    remark: Optional[str] = Field(None, max_length=255)


class AgentSubscriptionSaleBatchSettleRequest(BaseModel):
    """Admin batch subscription sale rebate settlement request."""

    ids: List[int] = Field(..., min_length=1)
    remark: Optional[str] = Field(None, max_length=255)
