"""
Redis 客户端封装
提供连接池管理、异常处理，不降级到内存缓存
"""
import os
import logging
from typing import Optional
import redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 客户端封装类"""

    def __init__(self):
        """初始化 Redis 连接池（修复：失败时抛出异常）"""
        try:
            self.pool = ConnectionPool(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD") or None,
                db=int(os.getenv("REDIS_DB", 0)),
                max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", 10)),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.client = redis.Redis(connection_pool=self.pool)
            # 测试连接
            self.client.ping()
            logger.info("Redis client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            # 如果 CACHE_ENABLED=true 但 Redis 连接失败，抛出异常
            if os.getenv("CACHE_ENABLED", "true").lower() == "true":
                logger.warning("Cache is enabled but Redis connection failed. Cache will be disabled.")
            self.client = None

    def get(self, key: str) -> Optional[str]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，失败返回 None
        """
        if not self.client:
            return None

        try:
            return self.client.get(key)
        except RedisConnectionError as e:
            logger.error(f"Redis connection failed on GET: {e}")
            return None
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: str, ex: int = 3600) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ex: 过期时间（秒）

        Returns:
            成功返回 True，失败返回 False
        """
        if not self.client:
            return False

        try:
            return self.client.set(key, value, ex=ex)
        except RedisConnectionError as e:
            logger.error(f"Redis connection failed on SET: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        删除缓存键

        Args:
            key: 缓存键

        Returns:
            成功返回 True，失败返回 False
        """
        if not self.client:
            return False

        try:
            return self.client.delete(key) > 0
        except RedisConnectionError as e:
            logger.error(f"Redis connection failed on DELETE: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        检查键是否存在

        Args:
            key: 缓存键

        Returns:
            存在返回 True，否则返回 False
        """
        if not self.client:
            return False

        try:
            return self.client.exists(key) > 0
        except RedisConnectionError as e:
            logger.error(f"Redis connection failed on EXISTS: {e}")
            return False
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False

    def close(self):
        """关闭 Redis 连接"""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis client closed")
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")


# 全局 Redis 客户端实例
redis_client = RedisClient()
