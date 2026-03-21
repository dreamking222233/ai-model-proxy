"""
核心缓存服务
负责缓存的读取、保存和清空操作（仅使用 Redis）
"""
import json
import time
import logging
from typing import Optional, Dict, Any, List
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class CacheService:
    """缓存服务类"""

    def __init__(self):
        """初始化缓存服务"""
        self.redis = redis_client

    async def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        查询 Redis 缓存

        Args:
            cache_key: 缓存键

        Returns:
            缓存的响应数据，未命中返回 None
        """
        try:
            cached_data = self.redis.get(f"cache:content:{cache_key}")
            if cached_data:
                logger.info(f"Cache HIT: key={cache_key[:8]}...")
                return json.loads(cached_data)
            logger.debug(f"Cache MISS: key={cache_key[:8]}...")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data: {e}")
            # 删除损坏的缓存
            self.redis.delete(f"cache:content:{cache_key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cache: {e}")
            return None

    async def save_response(
        self,
        cache_key: str,
        response: Dict[str, Any],
        user_id: int,
        ttl: int = 3600
    ) -> bool:
        """
        保存响应到 Redis（修复：添加 user_id 参数并调用 add_user_cache_key）

        Args:
            cache_key: 缓存键
            response: 响应数据
            user_id: 用户ID
            ttl: 缓存时长（秒）

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            cache_data = {
                "response": response,
                "model": response.get("model"),
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
                "created_at": int(time.time())
            }

            success = self.redis.set(
                f"cache:content:{cache_key}",
                json.dumps(cache_data, ensure_ascii=False),
                ex=ttl
            )

            if success:
                # 添加缓存键到用户集合（用于 clear_user_cache）
                await self.add_user_cache_key(user_id, cache_key)
                logger.info(f"Cache saved: key={cache_key[:8]}..., user={user_id}, ttl={ttl}s")
            else:
                logger.warning(f"Failed to save cache: key={cache_key[:8]}...")

            return success
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False

    async def clear_user_cache(self, user_id: int) -> int:
        """
        清空用户的所有缓存

        注意：需要维护用户缓存键集合才能实现此功能
        当前实现为简化版本，实际使用时需要在保存缓存时同步维护 user_keys 集合

        Args:
            user_id: 用户ID

        Returns:
            清空的缓存数量
        """
        try:
            # 方案：维护用户缓存键集合
            user_cache_keys_key = f"cache:user_keys:{user_id}"

            if not self.redis.client:
                logger.warning("Redis client not available")
                return 0

            # 获取用户的所有缓存键
            cache_keys = self.redis.client.smembers(user_cache_keys_key)

            count = 0
            for cache_key in cache_keys:
                # 兼容非流式 (cache:content:{key}) 和流式 (cache:stream:{key}) 两种格式
                key_str = cache_key.decode() if isinstance(cache_key, bytes) else cache_key
                if key_str.startswith("stream:"):
                    # 流式缓存键，格式为 "stream:{cache_key}"
                    if self.redis.delete(f"cache:{key_str}"):
                        count += 1
                else:
                    # 非流式缓存键，直接用 cache:content:{key}
                    if self.redis.delete(f"cache:content:{key_str}"):
                        count += 1

            # 清空用户缓存键集合
            self.redis.delete(user_cache_keys_key)

            logger.info(f"Cleared {count} cache entries for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to clear user cache: {e}")
            return 0

    async def add_user_cache_key(self, user_id: int, cache_key: str):
        """
        将缓存键添加到用户的缓存键集合

        在保存缓存时调用此方法，用于支持 clear_user_cache 功能

        Args:
            user_id: 用户ID
            cache_key: 缓存键
        """
        try:
            if not self.redis.client:
                return

            user_cache_keys_key = f"cache:user_keys:{user_id}"
            self.redis.client.sadd(user_cache_keys_key, cache_key)
            # 设置过期时间（30天）
            self.redis.client.expire(user_cache_keys_key, 30 * 24 * 3600)
        except Exception as e:
            logger.error(f"Failed to add user cache key: {e}")

    async def save_stream_response(
        self,
        cache_key: str,
        data: Dict[str, Any],
        user_id: int,
        ttl: int = 3600,
    ) -> bool:
        """
        保存流式响应到 Redis

        Args:
            cache_key: 缓存键
            data: 流式响应数据（包含 chunks、model、usage、protocol）
            user_id: 用户ID
            ttl: 缓存时长（秒）

        Returns:
            成功返回 True，失败返回 False
        """
        try:
            success = self.redis.set(
                f"cache:stream:{cache_key}",
                json.dumps(data, ensure_ascii=False),
                ex=ttl,
            )

            if success:
                await self.add_user_cache_key(user_id, f"stream:{cache_key}")
                logger.info(
                    f"Stream cache saved: key={cache_key[:8]}..., user={user_id}, ttl={ttl}s"
                )
            else:
                logger.warning(f"Failed to save stream cache: key={cache_key[:8]}...")

            return bool(success)
        except Exception as e:
            logger.error(f"Failed to save stream cache: {e}")
            return False

    async def get_stream_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存的流式响应

        Args:
            cache_key: 缓存键

        Returns:
            缓存的流式响应数据，未命中返回 None
        """
        try:
            cached_data = self.redis.get(f"cache:stream:{cache_key}")
            if cached_data:
                logger.info(f"Stream cache HIT: key={cache_key[:8]}...")
                return json.loads(cached_data)
            logger.debug(f"Stream cache MISS: key={cache_key[:8]}...")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode stream cached data: {e}")
            self.redis.delete(f"cache:stream:{cache_key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get stream cache: {e}")
            return None

    def get_cache_stats(self, user_id: int, date: str) -> Dict[str, Any]:
        """
        获取用户某天的缓存统计（从 Redis）

        Args:
            user_id: 用户ID
            date: 日期字符串（YYYY-MM-DD）

        Returns:
            统计数据字典
        """
        try:
            if not self.redis.client:
                return {"hit_count": 0, "miss_count": 0, "saved_tokens": 0, "saved_cost": 0.0}

            stats_key = f"cache:stats:{user_id}:{date}"
            stats = self.redis.client.hgetall(stats_key)

            return {
                "hit_count": int(stats.get("hit_count", 0)),
                "miss_count": int(stats.get("miss_count", 0)),
                "saved_tokens": int(stats.get("saved_tokens", 0)),
                "saved_cost": float(stats.get("saved_cost", 0.0))
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"hit_count": 0, "miss_count": 0, "saved_tokens": 0, "saved_cost": 0.0}


# 全局缓存服务实例
cache_service = CacheService()
