"""
AI 请求缓存中间件
在 ProxyService 调用前后插入缓存逻辑
"""
import logging
import os
from typing import Dict, Any, Optional, Callable, Awaitable
from sqlalchemy.orm import Session

from app.services.cache_service import cache_service
from app.services.cache_stats_service import CacheStatsService
from app.services.cache_key_generator import should_cache, generate_cache_key
from app.models.user import SysUser

logger = logging.getLogger(__name__)


class CacheMiddleware:
    """缓存中间件类"""

    @staticmethod
    async def wrap_request(
        request_body: Dict[str, Any],
        headers: Dict[str, str],
        user: SysUser,
        db: Session,
        upstream_call: Callable[[], Awaitable[Dict[str, Any]]],
        unified_model: Any,
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        包装请求，添加缓存逻辑

        Args:
            request_body: 请求体
            headers: 请求头
            user: 用户对象
            db: 数据库会话
            upstream_call: 上游 API 调用函数（无参数）
            unified_model: 统一模型对象（用于计算费用）

        Returns:
            (response, cache_info) 元组
            - response: API 响应
            - cache_info: 缓存信息（命中时包含原始 tokens，未命中时为 None）
        """
        # 检查全局缓存开关
        if os.getenv("CACHE_ENABLED", "true").lower() != "true":
            logger.debug("Cache globally disabled")
            response = await upstream_call()
            return response, None

        cache_info = None

        try:
            # 1. 判断是否应该缓存
            if not should_cache(request_body, headers, user):
                logger.debug(f"Cache bypassed for user {user.id}")
                response = await upstream_call()
                return response, None

            # 2. 生成 cache key
            cache_key = generate_cache_key(request_body)
            logger.debug(f"Cache key generated: {cache_key[:8]}... for user {user.id}")

            # 3. 查询缓存
            cached_response = await cache_service.get_cached_response(cache_key)

            if cached_response:
                # 缓存命中
                logger.info(f"Cache HIT for user {user.id}, key={cache_key[:8]}...")

                # 构造缓存信息（用于计费）
                cache_info = {
                    "is_cache_hit": True,
                    "cache_key": cache_key,
                    "original_prompt_tokens": cached_response["prompt_tokens"],
                    "original_completion_tokens": cached_response["completion_tokens"],
                    "model": cached_response["model"],
                }

                # 记录缓存命中统计
                stats_service = CacheStatsService(db)
                saved_tokens = cached_response["prompt_tokens"] + cached_response["completion_tokens"]
                saved_cost = CacheMiddleware._calculate_saved_cost(
                    cached_response["prompt_tokens"],
                    cached_response["completion_tokens"],
                    unified_model
                )

                await stats_service.record_cache_hit(
                    user_id=user.id,
                    cache_key=cache_key,
                    model=cached_response["model"],
                    prompt_tokens=cached_response["prompt_tokens"],
                    completion_tokens=cached_response["completion_tokens"],
                    saved_tokens=saved_tokens,
                    saved_cost=saved_cost,
                    ttl=3600
                )

                return cached_response["response"], cache_info

            # 4. 缓存未命中：调用上游 API
            logger.info(f"Cache MISS for user {user.id}, key={cache_key[:8]}...")
            response = await upstream_call()

            # 5. 保存响应到缓存
            try:
                ttl = int(headers.get("X-Cache-TTL", 3600))
                await cache_service.save_response(
                    cache_key=cache_key,
                    response=response,
                    user_id=user.id,
                    ttl=ttl
                )

                # 记录缓存未命中统计
                stats_service = CacheStatsService(db)
                await stats_service.record_cache_miss(
                    user_id=user.id,
                    cache_key=cache_key,
                    model=response.get("model", "unknown"),
                    prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=response.get("usage", {}).get("completion_tokens", 0),
                    ttl=ttl
                )
            except Exception as e:
                logger.error(f"Failed to save cache: {e}")

            return response, None

        except Exception as e:
            logger.error(f"Cache middleware error: {e}")
            # 缓存失败不影响核心功能
            response = await upstream_call()
            return response, None

    @staticmethod
    def _calculate_saved_cost(
        prompt_tokens: int,
        completion_tokens: int,
        unified_model: Any
    ) -> float:
        """
        计算节省的费用

        Args:
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            unified_model: 统一模型对象

        Returns:
            节省的费用（美元）
        """
        try:
            input_cost = (prompt_tokens / 1_000_000) * float(unified_model.input_price_per_million)
            output_cost = (completion_tokens / 1_000_000) * float(unified_model.output_price_per_million)
            return input_cost + output_cost
        except Exception as e:
            logger.error(f"Failed to calculate saved cost: {e}")
            return 0.0

    @staticmethod
    def get_billing_tokens(
        cache_info: Optional[Dict[str, Any]],
        user: SysUser,
        actual_tokens: Dict[str, int]
    ) -> tuple[int, int]:
        """
        根据缓存信息和用户配置，返回应该计费的 tokens

        Args:
            cache_info: 缓存信息（来自 wrap_request）
            user: 用户对象
            actual_tokens: 实际 tokens（缓存未命中时使用）

        Returns:
            (input_tokens, output_tokens) 元组
        """
        # 缓存未命中或不应缓存
        if not cache_info or not cache_info.get("is_cache_hit"):
            return actual_tokens["input_tokens"], actual_tokens["output_tokens"]

        # 缓存命中：根据 cache_billing_enabled 决定
        if user.cache_billing_enabled == 1:
            # 按缓存后计费（0 tokens）
            logger.info(f"User {user.id} enabled cache billing, billing 0 tokens")
            return 0, 0
        else:
            # 按原始 tokens 计费
            logger.info(f"User {user.id} disabled cache billing, billing original tokens")
            return (
                cache_info["original_prompt_tokens"],
                cache_info["original_completion_tokens"]
            )
