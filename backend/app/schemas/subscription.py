from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from app.core.model_series import MODEL_SERIES_VALUES as MODEL_SERIES


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
    allowed_model_ids: List[int] = Field(default_factory=list)

    @field_validator("model_scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        if value not in {"all_models", "selected_series", "selected_models"}:
            raise ValueError("model_scope 不合法")
        return value

    @field_validator("model_series")
    @classmethod
    def validate_series(cls, values: List[str]) -> List[str]:
        normalized = [str(v).strip().lower() for v in values]
        if len(set(normalized)) != len(normalized) or any(v not in MODEL_SERIES for v in normalized):
            raise ValueError("model_series 不合法")
        return normalized

    @field_validator("allowed_model_ids")
    @classmethod
    def validate_allowed_model_ids(cls, values: List[int]) -> List[int]:
        result = []
        seen = set()
        for item in values or []:
            model_id = int(item)
            if model_id <= 0:
                raise ValueError("allowed_model_ids 不合法")
            if model_id not in seen:
                seen.add(model_id)
                result.append(model_id)
        return result


class SubscriptionBonusGrantCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    user_id: int
    source_subscription_id: int
    grant_request_id: str = Field(..., min_length=1, max_length=64)
    duration_mode: str = "fixed_days"
    duration_days: Optional[int] = Field(None, gt=0)
    daily_quota_usd: Decimal = Field(..., gt=0)
    model_series: List[str] = Field(default_factory=list)
    remark: Optional[str] = None

    @field_validator("model_series")
    @classmethod
    def validate_bonus_series(cls, values: List[str]) -> List[str]:
        normalized = [str(v).strip().lower() for v in values]
        if len(set(normalized)) != len(normalized) or any(v not in MODEL_SERIES for v in normalized):
            raise ValueError("model_series 不合法")
        return normalized


class SubscriptionBonusGrantCancel(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)
