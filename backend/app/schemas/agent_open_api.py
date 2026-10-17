"""Request contracts for agent open API administration and endpoints."""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AgentOpenApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] = Field(..., min_length=1, max_length=6)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


class AgentOpenApiKeyScopesUpdate(BaseModel):
    scopes: list[str] = Field(..., min_length=1, max_length=6)


class OpenApiEmailCodeRequest(BaseModel):
    email: EmailStr


class OpenApiRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    email_code: str | None = Field(default=None, min_length=4, max_length=12)
    invite_code: str | None = Field(default=None, max_length=32)


class OpenApiLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class OpenApiRechargeOrderRequest(BaseModel):
    amount_cny: Decimal = Field(..., ge=Decimal("1.00"), le=Decimal("10000.00"), decimal_places=2)
    payment_channel: Literal["alipay", "wechat"]
    recharge_rate_code: Literal["a", "b", "c", "d", "e", "f", "g"] = "e"


class OpenApiRechargeOrderFilters(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    user_id: int | None = Field(default=None, gt=0)
    status: Literal["pending", "paid", "closed", "failed"] | None = None
    payment_channel: Literal["alipay", "wechat"] | None = None
    recharge_type: Literal["balance", "image_credit", "subscription"] | None = None
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
