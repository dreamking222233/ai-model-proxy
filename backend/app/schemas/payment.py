"""Payment-related request schemas."""

from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class UserRechargeOrderCreateRequest(BaseModel):
    """Create online recharge order request."""

    amount_cny: Decimal = Field(..., ge=1)
    payment_channel: str = Field("alipay", pattern="^(alipay|wechat)$")


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
