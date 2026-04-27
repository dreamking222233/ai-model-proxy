"""Agent request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field


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
