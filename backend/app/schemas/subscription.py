from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


MODEL_SERIES = {"gpt", "claude", "grok", "gemini", "other"}


class SubscriptionPlanPayload(BaseModel):
    model_config = {"protected_namespaces": ()}
    plan_code: str = Field(..., min_length=2, max_length=64)
    plan_name: str = Field(..., min_length=1, max_length=64)
    plan_kind: str
    duration_mode: str = "custom"
    duration_days: int = Field(..., gt=0)
    quota_metric: Optional[str] = None
    quota_value: Optional[Decimal] = Field(None, ge=0)
    model_scope: str = "all_models"
    model_series: List[str] = Field(default_factory=list)

    @field_validator("model_scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        if value not in {"all_models", "selected_series"}:
            raise ValueError("model_scope 不合法")
        return value

    @field_validator("model_series")
    @classmethod
    def validate_series(cls, values: List[str]) -> List[str]:
        normalized = [str(v).strip().lower() for v in values]
        if len(set(normalized)) != len(normalized) or any(v not in MODEL_SERIES for v in normalized):
            raise ValueError("model_series 不合法")
        return normalized


class SubscriptionBonusGrantCreate(BaseModel):
    user_id: int
    source_subscription_id: int
    grant_request_id: str = Field(..., min_length=1, max_length=64)
    duration_mode: str = "fixed_days"
    duration_days: Optional[int] = Field(None, gt=0)
    daily_quota_usd: Decimal = Field(..., gt=0)
    remark: Optional[str] = None


class SubscriptionBonusGrantCancel(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)
