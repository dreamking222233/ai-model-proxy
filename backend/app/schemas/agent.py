"""Agent request/response schemas."""

from decimal import Decimal, InvalidOperation
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AgentCreate(BaseModel):
    agent_code: str = Field(..., min_length=2, max_length=64)
    agent_name: str = Field(..., min_length=1, max_length=128)
    owner_user_id: Optional[int] = None
    owner_username: Optional[str] = Field(None, min_length=3, max_length=64)
    owner_email: Optional[str] = Field(None, max_length=128)
    owner_password: Optional[str] = Field(None, min_length=6, max_length=128)
    status: Optional[str] = Field("active", max_length=16)
    frontend_domain: Optional[str] = Field(None, max_length=255)
    api_domain: Optional[str] = Field(None, max_length=255)
    site_title: Optional[str] = Field(None, max_length=128)
    site_subtitle: Optional[str] = Field(None, max_length=255)
    announcement_title: Optional[str] = Field(None, max_length=128)
    announcement_content: Optional[str] = None
    support_wechat: Optional[str] = Field(None, max_length=128)
    support_qq: Optional[str] = Field(None, max_length=64)
    quickstart_api_base_url: Optional[str] = Field(None, max_length=512)
    allow_self_register: Optional[int] = Field(1, ge=0, le=1)
    theme_config_json: Optional[str] = None


class AgentUpdate(BaseModel):
    agent_code: Optional[str] = Field(None, min_length=2, max_length=64)
    agent_name: Optional[str] = Field(None, min_length=1, max_length=128)
    owner_user_id: Optional[int] = None
    status: Optional[str] = Field(None, max_length=16)
    frontend_domain: Optional[str] = Field(None, max_length=255)
    api_domain: Optional[str] = Field(None, max_length=255)
    site_title: Optional[str] = Field(None, max_length=128)
    site_subtitle: Optional[str] = Field(None, max_length=255)
    announcement_title: Optional[str] = Field(None, max_length=128)
    announcement_content: Optional[str] = None
    support_wechat: Optional[str] = Field(None, max_length=128)
    support_qq: Optional[str] = Field(None, max_length=64)
    quickstart_api_base_url: Optional[str] = Field(None, max_length=512)
    allow_self_register: Optional[int] = Field(None, ge=0, le=1)
    theme_config_json: Optional[str] = None


class AgentBalanceRecharge(BaseModel):
    amount: float = Field(..., gt=0)
    remark: Optional[str] = Field(None, max_length=255)


class AgentImageBalanceRecharge(BaseModel):
    amount: float = Field(..., gt=0)
    remark: Optional[str] = Field(None, max_length=255)


class AgentSubscriptionInventoryRecharge(BaseModel):
    plan_id: int = Field(..., gt=0)
    count: int = Field(..., gt=0)
    remark: Optional[str] = Field(None, max_length=255)


class AgentRedemptionAmountRuleCreate(BaseModel):
    amount: float = Field(..., gt=0)
    agent_id: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field("active", max_length=16)
    sort_order: Optional[int] = Field(0, ge=0)


class AgentGrantSubscriptionRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    plan_id: int = Field(..., gt=0)
    activation_mode: Optional[str] = Field("append", max_length=16)
    remark: Optional[str] = Field(None, max_length=255)


class AgentDailyLimitUpsert(BaseModel):
    resource_type: str = Field(..., max_length=32)
    plan_id: Optional[int] = Field(None, gt=0)
    daily_limit: float = Field(..., ge=0)
    status: Optional[str] = Field("active", max_length=16)

    @model_validator(mode="after")
    def validate_subscription_limit(self):
        if self.resource_type == "subscription":
            try:
                value = Decimal(str(self.daily_limit))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError("套餐每日额度格式不正确") from exc
            if value != value.to_integral_value():
                raise ValueError("套餐每日额度必须是整数")
        return self


class AgentDailyLimitBatchUpsert(BaseModel):
    items: List[AgentDailyLimitUpsert] = Field(default_factory=list)


class AgentSettlementSettleRequest(BaseModel):
    agent_id: int = Field(..., gt=0)
    resource_type: str = Field(..., max_length=32)
    quantity: float = Field(..., gt=0)
    plan_id: Optional[int] = Field(None, gt=0)
    start_date: Optional[str] = Field(None, max_length=10)
    end_date: Optional[str] = Field(None, max_length=10)
    remark: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_subscription_quantity(self):
        if self.resource_type == "subscription":
            try:
                value = Decimal(str(self.quantity))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError("套餐结算数量格式不正确") from exc
            if value != value.to_integral_value():
                raise ValueError("套餐结算数量必须是整数")
        return self
