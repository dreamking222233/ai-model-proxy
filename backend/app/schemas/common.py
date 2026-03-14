"""Common response schemas used across the application."""

from pydantic import BaseModel
from typing import Optional, Any, List


class ResponseModel(BaseModel):
    """Standard API response wrapper."""

    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PageResponse(BaseModel):
    """Paginated API response wrapper."""

    code: int = 200
    message: str = "success"
    data: Optional[List[Any]] = None
    total: int = 0
    page: int = 1
    page_size: int = 20
