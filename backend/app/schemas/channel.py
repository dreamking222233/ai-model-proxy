"""Channel (model provider) request/response schemas."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class ChannelCreate(BaseModel):
    """Payload for creating a new channel."""

    name: str = Field(..., min_length=1, max_length=128)
    base_url: str = Field(..., min_length=1, max_length=512)
    api_key: str = Field(..., min_length=1)
    protocol_type: str = Field(default="openai", max_length=20)
    priority: int = Field(default=10, ge=1)
    enabled: int = Field(default=1, ge=0, le=1)
    description: Optional[str] = None


class ChannelUpdate(BaseModel):
    """Payload for updating a channel (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    base_url: Optional[str] = Field(None, min_length=1, max_length=512)
    api_key: Optional[str] = Field(None, min_length=1)
    protocol_type: Optional[str] = Field(None, max_length=20)
    priority: Optional[int] = Field(None, ge=1)
    enabled: Optional[int] = Field(None, ge=0, le=1)
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Info / List
# ---------------------------------------------------------------------------

class ChannelInfo(BaseModel):
    """Channel info with masked API key."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    api_key: str = Field(
        ...,
        description="Masked API key, e.g. sk-****xxxx",
    )
    protocol_type: str
    priority: int
    enabled: int
    is_healthy: int
    health_score: int
    failure_count: int
    circuit_breaker_until: Optional[datetime] = None
    last_health_check_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def mask_api_key(raw_key: str) -> str:
        """Mask an API key for safe display.

        Example: ``sk-proj-abcdefgh12345678`` -> ``sk-****5678``
        """
        if len(raw_key) <= 8:
            return "****"
        return f"{raw_key[:3]}****{raw_key[-4:]}"


class ChannelListResponse(BaseModel):
    """Paginated list of channels."""

    code: int = 200
    message: str = "success"
    data: Optional[List[ChannelInfo]] = None
    total: int = 0
    page: int = 1
    page_size: int = 20
