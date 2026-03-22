"""User-related request/response schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Login credentials."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserInfoBrief(BaseModel):
    """Compact user info returned after login."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    avatar: Optional[str] = None


class LoginResponse(BaseModel):
    """Login result with JWT token and user info."""

    token: str
    user: UserInfoBrief


class RegisterRequest(BaseModel):
    """New user registration payload."""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


# ---------------------------------------------------------------------------
# User detail / admin
# ---------------------------------------------------------------------------

class UserInfo(BaseModel):
    """Full user info (admin view)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    status: int
    avatar: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserUpdate(BaseModel):
    """Fields that can be updated on a user profile."""

    email: Optional[EmailStr] = None
    avatar: Optional[str] = Field(None, max_length=512)
    status: Optional[int] = Field(None, ge=0, le=1)
    role: Optional[str] = Field(None, pattern=r"^(admin|user)$")
    enable_cache: Optional[int] = Field(None, ge=0, le=1)
    cache_billing_enabled: Optional[int] = Field(None, ge=0, le=1)


class PasswordChange(BaseModel):
    """Password change request."""

    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class UserListResponse(BaseModel):
    """Paginated list of users (admin)."""

    code: int = 200
    message: str = "success"
    data: Optional[List[UserInfo]] = None
    total: int = 0
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

class BalanceRechargeRequest(BaseModel):
    """Admin recharge request."""

    user_id: int
    amount: Decimal = Field(..., gt=0)
