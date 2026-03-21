"""
缓存日志模型
记录缓存命中、未命中和跳过的日志
"""
from sqlalchemy import Column, Integer, String, Enum, DECIMAL, DateTime, BigInteger, ForeignKey, func
from app.database import Base
import enum


class CacheStatus(str, enum.Enum):
    """缓存状态枚举"""
    HIT = "HIT"       # 缓存命中
    MISS = "MISS"     # 缓存未命中
    BYPASS = "BYPASS" # 跳过缓存


class CacheLog(Base):
    """缓存日志表"""
    __tablename__ = "cache_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cache_key = Column(String(64), nullable=False, index=True, comment="Cache Key (SHA256)")
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False, index=True, comment="User ID")
    model = Column(String(100), nullable=False, comment="Model name")
    prompt_tokens = Column(Integer, nullable=False, comment="Prompt tokens")
    completion_tokens = Column(Integer, nullable=False, comment="Completion tokens")
    cache_status = Column(Enum(CacheStatus), nullable=False, comment="Cache status")
    saved_tokens = Column(Integer, nullable=False, default=0, comment="Saved tokens")
    saved_cost = Column(DECIMAL(10, 6), nullable=False, default=0.0, comment="Saved cost in USD")
    ttl = Column(Integer, nullable=False, comment="Cache TTL in seconds")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="Created at")

    def __repr__(self):
        return f"<CacheLog(id={self.id}, user_id={self.user_id}, status={self.cache_status}, model={self.model})>"
