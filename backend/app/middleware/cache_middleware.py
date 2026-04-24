"""
请求体缓存分析中间件。

该中间件只执行系统内部的请求体分段缓存分析与 Redis 读写，不会改变发往上游
的请求参数，也不会基于缓存短路返回旧响应。
"""
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.database import release_session_connection
from app.models.user import SysUser
from app.services.request_body_cache_service import RequestBodyCacheService


class CacheMiddleware:
    """非流式请求体缓存分析中间件。"""

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
        """Analyze request-body cache usage, then execute the upstream call unchanged."""
        cache_info = RequestBodyCacheService.analyze_request(
            db=db,
            user_id=user.id,
            request_body=request_body,
            request_format=request_format,
            requested_model=requested_model,
        )
        if cache_state is not None:
            cache_state["cache_info"] = cache_info
        release_session_connection(db)
        try:
            response = await upstream_call()
        except Exception as exc:
            setattr(exc, "_request_cache_info", cache_info)
            raise
        return response, cache_info

    @staticmethod
    def get_billing_tokens(
        cache_info: Optional[Dict[str, Any]],
        user: SysUser,
        actual_tokens: Dict[str, int],
    ) -> tuple[int, int]:
        """请求体缓存不影响真实计费，始终按实际 tokens 计费。"""
        return actual_tokens["input_tokens"], actual_tokens["output_tokens"]
