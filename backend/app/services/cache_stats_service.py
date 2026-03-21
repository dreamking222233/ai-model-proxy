"""
缓存统计服务
负责记录缓存命中/未命中日志，更新统计数据
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
from app.models.cache_log import CacheLog, CacheStatus
from app.models.user import SysUser
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


class CacheStatsService:
    """缓存统计服务类"""

    def __init__(self, db: Union[AsyncSession, Session]):
        """
        初始化缓存统计服务

        Args:
            db: 数据库会话（兼容 AsyncSession 和同步 Session）
        """
        self.db = db
        self.redis = redis_client
        # 一次性检测 session 类型，避免每次调用都 try/except
        self._is_async = isinstance(db, AsyncSession)

    async def _execute(self, stmt):
        """兼容 AsyncSession 和同步 Session 执行 SQL"""
        if self._is_async:
            return await self.db.execute(stmt)
        return self.db.execute(stmt)

    async def _commit(self):
        """兼容 AsyncSession 和同步 Session 提交事务"""
        if self._is_async:
            await self.db.commit()
        else:
            self.db.commit()

    async def _rollback(self):
        """兼容 AsyncSession 和同步 Session 回滚事务"""
        if self._is_async:
            await self.db.rollback()
        else:
            self.db.rollback()

    async def record_cache_hit(
        self,
        user_id: int,
        cache_key: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        saved_tokens: int,
        saved_cost: float,
        ttl: int
    ):
        """
        记录缓存命中（修复：添加事务处理）

        Args:
            user_id: 用户ID
            cache_key: 缓存键
            model: 模型名称
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            saved_tokens: 节省的 tokens
            saved_cost: 节省的费用
            ttl: 缓存时长
        """
        try:
            # 1. 写入数据库日志
            cache_log = CacheLog(
                cache_key=cache_key,
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_status=CacheStatus.HIT,
                saved_tokens=saved_tokens,
                saved_cost=saved_cost,
                ttl=ttl
            )
            self.db.add(cache_log)

            # 2. 更新用户表统计
            await self._execute(
                update(SysUser)
                .where(SysUser.id == user_id)
                .values(
                    cache_hit_count=SysUser.cache_hit_count + 1,
                    cache_saved_tokens=SysUser.cache_saved_tokens + saved_tokens
                )
            )

            # 3. 提交事务
            await self._commit()

            # 4. 更新 Redis 统计（事务成功后）
            today = datetime.now().strftime("%Y-%m-%d")
            stats_key = f"cache:stats:{user_id}:{today}"
            if self.redis.client:
                self.redis.client.hincrby(stats_key, "hit_count", 1)
                self.redis.client.hincrbyfloat(stats_key, "saved_tokens", saved_tokens)
                self.redis.client.hincrbyfloat(stats_key, "saved_cost", saved_cost)
                self.redis.client.expire(stats_key, 30 * 24 * 3600)  # 30 天

            logger.info(f"Cache HIT recorded: user={user_id}, key={cache_key[:8]}..., saved_tokens={saved_tokens}")

        except Exception as e:
            await self._rollback()
            logger.error(f"Failed to record cache hit: {e}")

    async def record_cache_miss(
        self,
        user_id: int,
        cache_key: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        ttl: int
    ):
        """
        记录缓存未命中（修复：添加事务处理）

        Args:
            user_id: 用户ID
            cache_key: 缓存键
            model: 模型名称
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            ttl: 缓存时长
        """
        try:
            # 1. 写入数据库日志
            cache_log = CacheLog(
                cache_key=cache_key,
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_status=CacheStatus.MISS,
                saved_tokens=0,
                saved_cost=0.0,
                ttl=ttl
            )
            self.db.add(cache_log)

            # 2. 提交事务（兼容 AsyncSession 和同步 Session）
            await self._commit()

            # 3. 更新 Redis 统计（事务成功后）
            today = datetime.now().strftime("%Y-%m-%d")
            stats_key = f"cache:stats:{user_id}:{today}"
            if self.redis.client:
                self.redis.client.hincrby(stats_key, "miss_count", 1)

            logger.info(f"Cache MISS recorded: user={user_id}, key={cache_key[:8]}...")

        except Exception as e:
            await self._rollback()
            logger.error(f"Failed to record cache miss: {e}")

    async def record_cache_bypass(
        self,
        user_id: int,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reason: str = "conditions_not_met"
    ):
        """
        记录缓存跳过（可选，用于分析）（修复：添加事务处理）

        Args:
            user_id: 用户ID
            model: 模型名称
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            reason: 跳过原因
        """
        try:
            # 1. 写入数据库日志
            cache_log = CacheLog(
                cache_key=f"bypass_{reason}",
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_status=CacheStatus.BYPASS,
                saved_tokens=0,
                saved_cost=0.0,
                ttl=0
            )
            self.db.add(cache_log)

            # 2. 提交事务
            await self._commit()

            logger.debug(f"Cache BYPASS recorded: user={user_id}, reason={reason}")

        except Exception as e:
            await self._rollback()
            logger.error(f"Failed to record cache bypass: {e}")

    async def get_user_stats(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取用户缓存统计

        Args:
            user_id: 用户ID
            start_date: 开始日期（YYYY-MM-DD）
            end_date: 结束日期（YYYY-MM-DD）

        Returns:
            统计数据字典
        """
        try:
            # 从数据库查询
            query = select(
                CacheLog.cache_status,
                func.count(CacheLog.id).label("count"),
                func.sum(CacheLog.saved_tokens).label("total_saved_tokens"),
                func.sum(CacheLog.saved_cost).label("total_saved_cost")
            ).where(CacheLog.user_id == user_id)

            if start_date:
                query = query.where(CacheLog.created_at >= start_date)
            if end_date:
                query = query.where(CacheLog.created_at <= end_date)

            query = query.group_by(CacheLog.cache_status)

            result = await self._execute(query)
            rows = result.fetchall()

            stats = {
                "hit_count": 0,
                "miss_count": 0,
                "bypass_count": 0,
                "saved_tokens": 0,
                "saved_cost": 0.0
            }

            for row in rows:
                if row.cache_status == CacheStatus.HIT:
                    stats["hit_count"] = row.count
                    stats["saved_tokens"] = int(row.total_saved_tokens or 0)
                    stats["saved_cost"] = float(row.total_saved_cost or 0.0)
                elif row.cache_status == CacheStatus.MISS:
                    stats["miss_count"] = row.count
                elif row.cache_status == CacheStatus.BYPASS:
                    stats["bypass_count"] = row.count

            # 计算命中率
            total_cacheable = stats["hit_count"] + stats["miss_count"]
            stats["hit_rate"] = stats["hit_count"] / total_cacheable if total_cacheable > 0 else 0.0

            return stats

        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return {
                "hit_count": 0,
                "miss_count": 0,
                "bypass_count": 0,
                "saved_tokens": 0,
                "saved_cost": 0.0,
                "hit_rate": 0.0
            }

    async def update_user_cache_stats(self, user_id: int):
        """
        更新用户表的缓存统计（从数据库聚合）

        Args:
            user_id: 用户ID
        """
        try:
            # 查询用户的总统计
            result = await self._execute(
                select(
                    func.count(CacheLog.id).label("hit_count"),
                    func.sum(CacheLog.saved_tokens).label("saved_tokens")
                ).where(
                    CacheLog.user_id == user_id,
                    CacheLog.cache_status == CacheStatus.HIT
                )
            )
            row = result.fetchone()

            if row:
                await self._execute(
                    update(SysUser)
                    .where(SysUser.id == user_id)
                    .values(
                        cache_hit_count=row.hit_count or 0,
                        cache_saved_tokens=row.saved_tokens or 0
                    )
                )
                await self._commit()

                logger.info(f"Updated user cache stats: user={user_id}")

        except Exception as e:
            await self._rollback()
            logger.error(f"Failed to update user cache stats: {e}")
