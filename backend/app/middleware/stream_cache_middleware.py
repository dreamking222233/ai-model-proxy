"""Streaming passthrough wrapper.

系统内部请求体分段缓存已停用。该包装器仅保留旧调用接口和流式 usage 收集能力。
"""
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import release_session_connection
from app.models.user import SysUser


class StreamCollector:
    """兼容现有上游调用签名的占位收集器。"""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.last_chunk_time = self.start_time
        self.first_chunk_time: Optional[float] = None

    def add_chunk(self, content: str, finish_reason: Optional[str] = None):
        """保留原接口，避免影响调用方。"""
        current_time = time.time()
        delta_ms = int((current_time - self.last_chunk_time) * 1000)
        self.chunks.append(
            {
                "content": content,
                "delta_ms": max(0, delta_ms),
                "finish_reason": finish_reason,
            }
        )
        if content and self.first_chunk_time is None:
            self.first_chunk_time = current_time
        self.last_chunk_time = current_time


class StreamCacheMiddleware:
    """流式请求透传包装器。"""

    @staticmethod
    async def wrap_stream_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[..., AsyncGenerator[str, None]],
        unified_model: Any,
        protocol: str,
        request_format: str,
        model: str,
        billing_callback: Optional[Callable[[int, int, bool], None]] = None,
        cache_state: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream upstream response without internal request-body cache analysis."""
        cache_info = None
        if cache_state is not None:
            cache_state["cache_info"] = cache_info
        collector = StreamCollector()
        if cache_state is not None:
            cache_state["stream_collector"] = collector
        collected_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        if cache_state is not None:
            cache_state["collected_usage"] = collected_usage
        release_session_connection(db)
        async for chunk in upstream_call(collector, collected_usage):
            if cache_state is not None and collected_usage.get("_first_stream_output_time") is not None:
                cache_state["first_stream_output_time"] = collected_usage["_first_stream_output_time"]
            yield chunk
