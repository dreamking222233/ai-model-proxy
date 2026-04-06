"""ORM models for unified_model, model_channel_mapping, and model_override_rule tables."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, SmallInteger, DECIMAL, func,
)

from app.database import Base


class UnifiedModel(Base):
    """Unified model definition."""

    __tablename__ = "unified_model"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(128), nullable=False, unique=True, comment="Unified model name for user requests")
    display_name = Column(String(128), nullable=True)
    model_type = Column(String(20), nullable=False, default="chat")
    protocol_type = Column(String(20), nullable=False, default="openai")
    max_tokens = Column(Integer, nullable=True)
    input_price_per_million = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Input price per million tokens (USD)")
    output_price_per_million = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Output price per million tokens (USD)")
    billing_type = Column(String(20), nullable=False, default="token", comment="Billing type: token/image_credit/free")
    image_credit_multiplier = Column(Integer, nullable=False, default=1, comment="Image credits consumed per request")
    enabled = Column(SmallInteger, nullable=False, default=1)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ModelChannelMapping(Base):
    """Model-to-channel mapping."""

    __tablename__ = "model_channel_mapping"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    unified_model_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False, index=True)
    actual_model_name = Column(String(128), nullable=False, comment="Actual model name in this channel")
    enabled = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ModelOverrideRule(Base):
    """Model override rule for request redirection."""

    __tablename__ = "model_override_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    rule_type = Column(String(30), nullable=False)
    source_pattern = Column(String(128), nullable=False, comment="*=all, or specific model name")
    target_unified_model_id = Column(BigInteger, nullable=False)
    enabled = Column(SmallInteger, nullable=False, default=1)
    priority = Column(Integer, nullable=False, default=10, comment="Rule priority, lower=higher")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
