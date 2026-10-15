"""Durable cache simulation rules and immutable accounting decisions."""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Index, Integer, SmallInteger, String, Text, UniqueConstraint, func
from app.database import Base
from sqlalchemy.dialects.mysql import MEDIUMTEXT


class CacheSimulationRule(Base):
    __tablename__ = "cache_simulation_rule"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uk_cache_simulation_pair"),)
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    group_id = Column(BigInteger, nullable=False, index=True)
    enabled = Column(SmallInteger, nullable=False, default=1)
    generation = Column(BigInteger, nullable=False, default=1)
    operator_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class CacheSimulationDecision(Base):
    __tablename__ = "cache_simulation_decision"
    __table_args__ = (
        Index("idx_cache_sim_records", "outcome", "accounting_status", "id"),
        Index("idx_cache_sim_recovery", "decision_status", "accounting_status", "next_retry_at"),
        Index("idx_cache_sim_user_group", "user_id", "group_id", "id"),
    )
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False, unique=True)
    decision_id = Column(String(36), nullable=False, unique=True)
    user_id = Column(BigInteger, nullable=False)
    user_api_key_id = Column(BigInteger, nullable=True)
    group_id = Column(BigInteger, nullable=False)
    unified_model_id = Column(BigInteger, nullable=False)
    username_snapshot = Column(String(64), nullable=False)
    group_name_snapshot = Column(String(128), nullable=False)
    requested_model = Column(String(128), nullable=False)
    protocol = Column(String(20), nullable=False)
    rule_id = Column(BigInteger, nullable=False)
    rule_generation = Column(BigInteger, nullable=False)
    config_version = Column(BigInteger, nullable=False)
    enable_epoch = Column(BigInteger, nullable=False)
    session_digest = Column(String(64), nullable=True, index=True)
    identity_source = Column(String(32), nullable=False)
    identity_confidence = Column(String(20), nullable=False)
    usage_source = Column(String(64), nullable=False)
    decision_status = Column(String(20), nullable=False, default="draft")
    accounting_status = Column(String(20), nullable=False, default="pending")
    state_delivery = Column(String(20), nullable=False, default="pending")
    outcome = Column(String(20), nullable=False, default="skipped")
    reason = Column(String(64), nullable=True)
    coefficient = Column(Integer, nullable=True)
    transferred_tokens = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False)
    context_tokens = Column(BigInteger, nullable=False)
    original_cost = Column(DECIMAL(20, 10), nullable=False, default=0)
    effective_cost = Column(DECIMAL(20, 10), nullable=False, default=0)
    fee_delta = Column(DECIMAL(20, 10), nullable=False, default=0)
    window_id = Column(String(36), nullable=True)
    window_started_at = Column(DateTime, nullable=True)
    window_expires_at = Column(DateTime, nullable=True)
    # JSON text is portable across the supported SQLAlchemy/MySQL versions.
    usage_json = Column(Text, nullable=False)
    snapshot_json = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    proposed_state_json = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=True)
    reservation_json = Column(Text, nullable=True)
    decision_hash = Column(String(64), nullable=True)
    receipt_json = Column(Text, nullable=True)
    recovery_attempts = Column(Integer, nullable=False, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(String(512), nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
