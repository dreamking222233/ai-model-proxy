"""Non-stream passthrough wrapper.

系统内部请求体分段缓存已停用。该包装器仅保留旧调用接口，避免改动所有代理
分支；真实缓存只从 CPA/上游响应 usage 字段读取。
"""
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.database import release_session_connection
from app.models.user import SysUser


class CacheMiddleware:
    """非流式请求透传包装器。"""

    @staticmethod
    async def wrap_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[[], Awaitable[Dict[str, Any]]],
        unified_model: Any,
        request_format: str,
        requested_model: str,
        cache_state: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Execute the upstream call without internal request-body cache analysis."""
        cache_info = None
        if cache_state is not None:
            cache_state["cache_info"] = cache_info
        release_session_connection(db)
        response = await upstream_call()
        return response, cache_info

    @staticmethod
    def get_billing_tokens(
        cache_info: Optional[Dict[str, Any]],
        user: SysUser,
        actual_tokens: Dict[str, int],
    ) -> tuple[int, int]:
        """请求体缓存不影响真实计费，始终按实际 tokens 计费。"""
        return actual_tokens["input_tokens"], actual_tokens["output_tokens"]
