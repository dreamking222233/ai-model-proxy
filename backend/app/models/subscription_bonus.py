"""Promotional subscription quota ledger models."""
from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime, Date, DECIMAL, UniqueConstraint, func
from app.database import Base


class SubscriptionBonusGrant(Base):
    __tablename__ = "subscription_bonus_grant"
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    grant_request_id = Column(String(64), nullable=False, unique=True, index=True)
    normalized_payload_hash = Column(String(64), nullable=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    agent_id = Column(BigInteger, nullable=True, index=True)
    source_subscription_id = Column(BigInteger, nullable=False, index=True)
    duration_mode = Column(String(20), nullable=False)
    duration_days = Column(Integer, nullable=True)
    daily_quota_usd = Column(DECIMAL(20, 6), nullable=False, default=0)
    model_series = Column(Text, nullable=True, comment="JSON array; empty means all bonus-enabled models")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    created_by = Column(BigInteger, nullable=True)
    cancelled_by = Column(BigInteger, nullable=True)
    cancel_reason = Column(String(255), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SubscriptionBonusUsageCycle(Base):
    __tablename__ = "subscription_bonus_usage_cycle"
    __table_args__ = (UniqueConstraint("bonus_grant_id", "cycle_index", name="uk_bonus_cycle"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    bonus_grant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    cycle_index = Column(Integer, nullable=False)
    cycle_date = Column(Date, nullable=False)
    cycle_start_at = Column(DateTime, nullable=False)
    cycle_end_at = Column(DateTime, nullable=False)
    quota_limit_usd = Column(DECIMAL(20, 6), nullable=False, default=0)
    used_amount_usd = Column(DECIMAL(20, 6), nullable=False, default=0)
    reserved_amount_usd = Column(DECIMAL(20, 6), nullable=False, default=0)
    version = Column(BigInteger, nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SubscriptionPlanModelSeries(Base):
    __tablename__ = "subscription_plan_model_series"
    __table_args__ = (UniqueConstraint("plan_id", "model_series", name="uk_plan_model_series"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    plan_id = Column(BigInteger, nullable=False, index=True)
    model_series = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserSubscriptionModelSeries(Base):
    __tablename__ = "user_subscription_model_series"
    __table_args__ = (UniqueConstraint("subscription_id", "model_series", name="uk_subscription_model_series"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    subscription_id = Column(BigInteger, nullable=False, index=True)
    model_series = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
