"""
流式缓存中间件已停用。

保留该模块仅为兼容现有调用点；所有流式请求直接透传到上游，不再执行缓存查询、
缓存保存或缓存重放。
"""
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import SysUser


class StreamCollector:
    """兼容现有上游调用签名的占位收集器。"""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.last_chunk_time = self.start_time

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
        self.last_chunk_time = current_time


class StreamCacheMiddleware:
    """已停用的流式缓存中间件占位实现。"""

    @staticmethod
    async def wrap_stream_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[..., AsyncGenerator[str, None]],
        unified_model: Any,
        protocol: str,
        model: str,
        billing_callback: Optional[Callable[[int, int, bool], None]] = None,
    ) -> AsyncGenerator[str, None]:
        """直接透传上游流式响应，不做任何缓存处理。"""
        collector = StreamCollector()
        collected_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        async for chunk in upstream_call(collector, collected_usage):
            yield chunk
