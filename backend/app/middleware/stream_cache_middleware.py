"""
流式请求缓存中间件
缓存完整响应，命中时模拟流式输出（SSE 格式）
"""
import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.user import SysUser
from app.services.cache_key_generator import generate_cache_key, should_cache
from app.services.cache_service import cache_service
from app.services.cache_stats_service import CacheStatsService

logger = logging.getLogger(__name__)

# =====================================================================
# StreamCollector: 收集流式响应 chunks 和时间间隔
# =====================================================================


class StreamCollector:
    """收集流式响应内容，用于事后保存到缓存"""

    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.last_chunk_time = self.start_time

    def add_chunk(self, content: str, finish_reason: Optional[str] = None):
        """
        添加一个 chunk

        Args:
            content: chunk 的文本内容
            finish_reason: 结束原因（stop / end_turn / None）
        """
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

    def get_collected_data(
        self,
        model: str,
        usage: Dict[str, int],
        protocol: str,
    ) -> Dict[str, Any]:
        """
        获取收集的完整数据（用于保存到缓存）

        Args:
            model: 模型名称
            usage: 用量信息 {"prompt_tokens": N, "completion_tokens": N}
            protocol: 协议类型（"openai" | "anthropic" | "responses"）
        """
        return {
            "chunks": self.chunks,
            "model": model,
            "usage": usage,
            "protocol": protocol,
            "total_duration_ms": int((time.time() - self.start_time) * 1000),
        }


# =====================================================================
# SSE 格式构造函数
# =====================================================================


def _format_openai_sse(chunk: Dict[str, Any], model: str) -> str:
    """
    构造 OpenAI 格式的 SSE chunk

    格式:
        data: {"id":"...","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}
    """
    chunk_id = f"chatcmpl-cache-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    if chunk.get("finish_reason"):
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": chunk["finish_reason"],
                }
            ],
        }
    else:
        data = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk["content"]},
                    "finish_reason": None,
                }
            ],
        }

    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _format_anthropic_sse(chunk: Dict[str, Any], model: str = "claude-3-5-sonnet-20241022") -> str:
    """
    构造 Anthropic 格式的 SSE chunk

    Anthropic 协议需要发送完整的事件序列：
    - 内容 chunk: content_block_delta 事件
    - 结束 chunk: 跳过（由 replay_cached_stream 统一发送结束序列）
    """
    if chunk.get("finish_reason"):
        # 结束 chunk 不发送事件，由外层 replay_cached_stream 统一处理结束序列
        return ""
    else:
        data = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "text_delta",
                "text": chunk["content"],
            },
        }
        return f"event: content_block_delta\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _format_responses_sse(chunk: Dict[str, Any]) -> str:
    """
    构造 Responses API 格式的 SSE chunk（与 Anthropic 格式类似）

    结束 chunk 返回空字符串，由 replay_cached_stream 统一处理结束序列
    """
    if chunk.get("finish_reason"):
        # 结束 chunk 不发送事件，由外层 replay_cached_stream 统一处理
        return ""
    else:
        data = {
            "type": "response.output_text.delta",
            "delta": chunk["content"],
        }
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# =====================================================================
# StreamCacheMiddleware
# =====================================================================


class StreamCacheMiddleware:
    """流式请求缓存中间件"""

    @staticmethod
    def _should_cache_stream(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
    ) -> bool:
        """
        判断流式请求是否应该缓存

        对流式请求特殊处理：临时移除 stream=True 标志，复用 should_cache 逻辑
        """
        # 全局缓存开关
        if os.getenv("CACHE_ENABLED", "true").lower() != "true":
            return False

        # 构造临时请求体（移除 stream=True，避免 should_cache 直接 bypass）
        temp_body = dict(request_body)
        temp_body.pop("stream", None)

        # 复用 should_cache 逻辑（此时 stream 字段不存在，不会被 bypass）
        return should_cache(temp_body, headers, user)

    @staticmethod
    async def replay_cached_stream(
        cached_data: Dict[str, Any],
        protocol: str,
    ) -> AsyncGenerator[str, None]:
        """
        从缓存重放流式响应

        Args:
            cached_data: 缓存的完整响应数据
            protocol: 协议类型（"openai" | "anthropic" | "responses"）

        Yields:
            SSE 格式的流式响应字符串
        """
        chunks: List[Dict[str, Any]] = cached_data.get("chunks", [])
        model: str = cached_data.get("model", "unknown")
        usage = cached_data.get("usage", {})
        response_id = f"resp_cache_{uuid.uuid4().hex[:8]}"

        # Anthropic 协议需要先发送 message_start 事件
        if protocol == "anthropic":
            message_start = {
                "type": "message_start",
                "message": {
                    "id": f"msg_cache_{uuid.uuid4().hex[:8]}",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": model,
                    "usage": {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": 0,
                    },
                },
            }
            yield f"event: message_start\ndata: {json.dumps(message_start, ensure_ascii=False)}\n\n"
            # content_block_start
            content_block_start = {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            }
            yield f"event: content_block_start\ndata: {json.dumps(content_block_start, ensure_ascii=False)}\n\n"

        # Responses API 需要先发送包围事件
        elif protocol == "responses":
            yield f"data: {json.dumps({'type': 'response.created', 'response': {'id': response_id, 'object': 'realtime.response', 'status': 'in_progress', 'model': model}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.in_progress', 'response': {'id': response_id, 'object': 'realtime.response', 'status': 'in_progress', 'model': model}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.output_item.added', 'response_id': response_id, 'output_index': 0, 'item': {'id': f'item_{uuid.uuid4().hex[:8]}', 'object': 'realtime.item', 'type': 'message', 'status': 'in_progress', 'role': 'assistant', 'content': []}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.content_part.added', 'response_id': response_id, 'output_index': 0, 'content_index': 0, 'part': {'type': 'text', 'text': ''}}, ensure_ascii=False)}\n\n"

        for chunk in chunks:
            # 模拟真实延迟（delta_ms 是与上一个 chunk 的间隔）
            delta_ms = chunk.get("delta_ms", 0)
            if delta_ms > 0:
                # 最长等待 200ms 避免过慢（压缩延迟）
                wait_ms = min(delta_ms, 200)
                await asyncio.sleep(wait_ms / 1000.0)

            # 根据协议格式化 SSE
            if protocol == "openai":
                yield _format_openai_sse(chunk, model)
            elif protocol == "anthropic":
                sse = _format_anthropic_sse(chunk, model)
                if sse:
                    yield sse
            elif protocol == "responses":
                sse = _format_responses_sse(chunk)
                if sse:
                    yield sse
            else:
                # 默认 OpenAI 格式
                yield _format_openai_sse(chunk, model)

        # 发送结束标记
        if protocol == "openai":
            yield "data: [DONE]\n\n"
        elif protocol == "anthropic":
            # 始终发送完整的结束序列：content_block_stop + message_delta + message_stop
            # （_format_anthropic_sse 对 finish_reason chunk 返回空字符串，由此处统一处理）
            content_block_stop = {"type": "content_block_stop", "index": 0}
            yield f"event: content_block_stop\ndata: {json.dumps(content_block_stop, ensure_ascii=False)}\n\n"
            message_delta = {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": usage.get("completion_tokens", 0)},
            }
            yield f"event: message_delta\ndata: {json.dumps(message_delta, ensure_ascii=False)}\n\n"
            yield "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
        elif protocol == "responses":
            # Responses API 完整结束序列
            full_text = "".join(c.get("content", "") for c in chunks if not c.get("finish_reason"))
            yield f"data: {json.dumps({'type': 'response.output_text.done', 'response_id': response_id, 'output_index': 0, 'content_index': 0, 'text': full_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.content_part.done', 'response_id': response_id, 'output_index': 0, 'content_index': 0, 'part': {'type': 'text', 'text': full_text}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.output_item.done', 'response_id': response_id, 'output_index': 0, 'item': {'id': f'item_{uuid.uuid4().hex[:8]}', 'object': 'realtime.item', 'type': 'message', 'status': 'completed', 'role': 'assistant', 'content': [{'type': 'text', 'text': full_text}]}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'response.completed', 'response': {'id': response_id, 'object': 'realtime.response', 'status': 'completed', 'model': model, 'usage': {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0), 'total_tokens': usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)}}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    @staticmethod
    async def wrap_stream_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[[], AsyncGenerator[str, None]],
        unified_model: Any,
        protocol: str,
        model: str,
        billing_callback: Optional[Callable[[int, int, bool], None]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        包装流式请求，处理缓存逻辑

        流程:
            1. 判断是否应该缓存
            2. 若应缓存：查询 Redis 缓存
            3. 缓存命中 → 重放缓存
            4. 缓存未命中 → 调用上游，同时收集 chunks，完成后保存缓存

        Args:
            request_body: 请求体
            headers: 请求头
            user: 用户对象
            db: 数据库会话
            upstream_call: 上游流式调用（AsyncGenerator），接受 collector 参数
            unified_model: 统一模型对象（用于计算费用）
            protocol: 协议类型（"openai" | "anthropic" | "responses"）
            model: 模型名称
            billing_callback: 计费回调函数（input_tokens, output_tokens, is_cache_hit）

        Yields:
            SSE 格式的流式响应字符串
        """
        # 1. 判断是否应该缓存
        if not StreamCacheMiddleware._should_cache_stream(request_body, headers, user):
            logger.debug(f"Stream cache bypassed for user {user.id}")
            # BYPASS：传入虚拟的 collector 和 collected_usage，不使用它们
            dummy_collector = StreamCollector()
            dummy_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
            async for chunk in upstream_call(dummy_collector, dummy_usage):
                yield chunk
            return

        # 2. 生成 cache key（使用无 stream 标志的请求体）
        temp_body = dict(request_body)
        temp_body.pop("stream", None)
        cache_key = generate_cache_key(temp_body)
        logger.debug(f"Stream cache key: {cache_key[:8]}... for user {user.id}")

        # 3. 查询缓存
        try:
            cached_data = await cache_service.get_stream_response(cache_key)
        except Exception as e:
            logger.error(f"Stream cache lookup failed: {e}")
            cached_data = None

        if cached_data:
            # ── 缓存命中 ──
            logger.info(f"Stream cache HIT for user {user.id}, key={cache_key[:8]}...")
            cache_status = "HIT"

            # 记录缓存命中统计
            try:
                usage = cached_data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                saved_tokens = prompt_tokens + completion_tokens

                stats_service = CacheStatsService(db)
                saved_cost = 0.0
                try:
                    input_cost = (prompt_tokens / 1_000_000) * float(
                        unified_model.input_price_per_million
                    )
                    output_cost = (completion_tokens / 1_000_000) * float(
                        unified_model.output_price_per_million
                    )
                    saved_cost = input_cost + output_cost
                except Exception:
                    pass

                await stats_service.record_cache_hit(
                    user_id=user.id,
                    cache_key=cache_key,
                    model=cached_data.get("model", model),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    saved_tokens=saved_tokens,
                    saved_cost=saved_cost,
                    ttl=3600,
                )
            except Exception as e:
                logger.error(f"Failed to record stream cache hit stats: {e}")

            # 计费（缓存命中）
            if billing_callback:
                try:
                    usage = cached_data.get("usage", {})
                    billing_callback(
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                        True,  # is_cache_hit=True
                    )
                except Exception as e:
                    logger.error(f"Billing callback error on cache hit: {e}")

            # 重放缓存
            async for sse_line in StreamCacheMiddleware.replay_cached_stream(
                cached_data, protocol
            ):
                yield sse_line
            return

        # ── 缓存未命中 ──
        logger.info(f"Stream cache MISS for user {user.id}, key={cache_key[:8]}...")
        cache_status = "MISS"

        # 4. 调用上游，同时收集 chunks
        collector = StreamCollector()
        collected_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        stream_success = False

        try:
            async for sse_line in upstream_call(collector, collected_usage):
                yield sse_line
            stream_success = True
        except Exception as e:
            logger.error(f"Stream upstream call failed: {e}")
            raise
        finally:
            # 5. 保存缓存（仅在流式响应成功完成时）
            if stream_success and collector.chunks:
                try:
                    ttl = int(headers.get("X-Cache-TTL", 3600))
                    cached_data_to_save = collector.get_collected_data(
                        model=model,
                        usage=collected_usage,
                        protocol=protocol,
                    )
                    await cache_service.save_stream_response(
                        cache_key=cache_key,
                        data=cached_data_to_save,
                        user_id=user.id,
                        ttl=ttl,
                    )

                    # 记录缓存未命中统计
                    stats_service = CacheStatsService(db)
                    await stats_service.record_cache_miss(
                        user_id=user.id,
                        cache_key=cache_key,
                        model=model,
                        prompt_tokens=collected_usage.get("prompt_tokens", 0),
                        completion_tokens=collected_usage.get("completion_tokens", 0),
                        ttl=ttl,
                    )
                except Exception as e:
                    logger.error(f"Failed to save stream cache: {e}")
