"""Validated administrator inputs for cache simulation."""
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class CacheSimulationConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    ttl_minutes: int = Field(..., strict=True, ge=1, le=1440)
    version: int = Field(..., strict=True, ge=1)


class CacheSimulationRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(..., strict=True, gt=0)
    group_id: int = Field(..., strict=True, gt=0)
    enabled: StrictBool = True


class CacheSimulationRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    generation: int = Field(..., strict=True, ge=1)
