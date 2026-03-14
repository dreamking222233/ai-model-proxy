"""Unified model, channel mapping, and override rule schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# ===========================================================================
# Unified Model
# ===========================================================================

class UnifiedModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(..., min_length=1, max_length=128)
    display_name: Optional[str] = Field(None, max_length=128)
    model_type: str = Field(default="chat", max_length=20)
    protocol_type: str = Field(default="openai", max_length=20)
    max_tokens: Optional[int] = Field(None, gt=0)
    input_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    output_price_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    enabled: int = Field(default=1, ge=0, le=1)
    description: Optional[str] = None


class UnifiedModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_name: Optional[str] = Field(None, min_length=1, max_length=128)
    display_name: Optional[str] = Field(None, max_length=128)
    model_type: Optional[str] = Field(None, max_length=20)
    protocol_type: Optional[str] = Field(None, max_length=20)
    max_tokens: Optional[int] = Field(None, gt=0)
    input_price_per_million: Optional[Decimal] = Field(None, ge=0)
    output_price_per_million: Optional[Decimal] = Field(None, ge=0)
    enabled: Optional[int] = Field(None, ge=0, le=1)
    description: Optional[str] = None


class UnifiedModelInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    model_name: str
    display_name: Optional[str] = None
    model_type: str
    protocol_type: str
    max_tokens: Optional[int] = None
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    enabled: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===========================================================================
# Model-Channel Mapping
# ===========================================================================

class ModelChannelMappingCreate(BaseModel):
    unified_model_id: int
    channel_id: int
    actual_model_name: str = Field(..., min_length=1, max_length=128)
    enabled: int = Field(default=1, ge=0, le=1)


class ModelChannelMappingInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unified_model_id: int
    channel_id: int
    actual_model_name: str
    enabled: int
    channel_name: Optional[str] = None
    created_at: Optional[datetime] = None


# ===========================================================================
# Model Override Rule
# ===========================================================================

class ModelOverrideRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    rule_type: str = Field(..., max_length=30)
    source_pattern: str = Field(..., max_length=128)
    target_unified_model_id: int
    enabled: int = Field(default=1, ge=0, le=1)
    priority: int = Field(default=10, ge=1)


class ModelOverrideRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    rule_type: Optional[str] = Field(None, max_length=30)
    source_pattern: Optional[str] = Field(None, max_length=128)
    target_unified_model_id: Optional[int] = None
    enabled: Optional[int] = Field(None, ge=0, le=1)
    priority: Optional[int] = Field(None, ge=1)


class ModelOverrideRuleInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rule_type: str
    source_pattern: str
    target_unified_model_id: int
    enabled: int
    priority: int
    target_model_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
