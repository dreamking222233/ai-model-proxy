"""
缓存中间件已停用。

保留该模块仅为兼容现有调用点；所有请求直接透传到上游，不再执行缓存读写、
缓存统计或缓存命中计费。
"""
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user import SysUser


class CacheMiddleware:
    """已停用的缓存中间件占位实现。"""

    @staticmethod
    async def wrap_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[[], Awaitable[Dict[str, Any]]],
        unified_model: Any,
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """直接执行上游调用，不做任何缓存处理。"""
        response = await upstream_call()
        return response, None

    @staticmethod
    def get_billing_tokens(
        cache_info: Optional[Dict[str, Any]],
        user: SysUser,
        actual_tokens: Dict[str, int],
    ) -> tuple[int, int]:
        """缓存已停用，始终按实际 tokens 计费。"""
        return actual_tokens["input_tokens"], actual_tokens["output_tokens"]
