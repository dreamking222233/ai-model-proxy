"""ORM models for unified_model, model_channel_mapping, and model_override_rule tables."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, SmallInteger, DECIMAL, Time, func, UniqueConstraint,
)

from app.database import Base


class UnifiedModel(Base):
    """Unified model definition."""

    __tablename__ = "unified_model"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_name = Column(String(128), nullable=False, unique=True, comment="Unified model name for user requests")
    display_name = Column(String(128), nullable=True)
    model_type = Column(String(20), nullable=False, default="chat")
    model_series = Column(String(32), nullable=False, default="other", comment="Model series: gpt/claude/grok/gemini/other")
    protocol_type = Column(String(20), nullable=False, default="openai")
    max_tokens = Column(Integer, nullable=True)
    input_price_per_million = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Input price per million tokens (USD)")
    output_price_per_million = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Output price per million tokens (USD)")
    cache_creation_price_per_million = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Prompt cache creation price per million tokens (USD)")
    billing_type = Column(String(20), nullable=False, default="token", comment="Billing type: token/request/image_credit/free")
    request_price = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Fixed price per successful request (USD)")
    image_credit_multiplier = Column(DECIMAL(12, 3), nullable=False, default=1, comment="Default image credits consumed per request")
    long_context_billing_enabled = Column(SmallInteger, nullable=False, default=0, comment="Whether to apply 2x billing above 256k context tokens")
    security_monitor_enabled = Column(SmallInteger, nullable=False, default=0, comment="Whether security risk monitoring is enabled for this model")
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
    default_reasoning_effort = Column(String(16), nullable=True, comment="Default reasoning effort for mapped GPT upstreams")
    enabled = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ModelImageResolutionRule(Base):
    """Per-model Google image resolution billing rule."""

    __tablename__ = "model_image_resolution_rule"
    __table_args__ = (
        UniqueConstraint("unified_model_id", "resolution_code", name="uk_model_resolution_code"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    unified_model_id = Column(BigInteger, nullable=False, index=True)
    resolution_code = Column(String(16), nullable=False, comment="512/1K/2K/4K")
    enabled = Column(SmallInteger, nullable=False, default=1)
    credit_cost = Column(DECIMAL(12, 3), nullable=False, default=1, comment="Image credits consumed for this resolution")
    is_default = Column(SmallInteger, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ModelPriceAdjustmentRule(Base):
    """Price multiplier rule by model series/type and Beijing-time schedule."""

    __tablename__ = "model_price_adjustment_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    model_series = Column(String(32), nullable=False, default="all", comment="gpt/claude/grok/gemini/other/all")
    model_type = Column(String(20), nullable=False, default="all", comment="chat/image/video/embedding/completion/all")
    billing_type = Column(String(20), nullable=False, default="all", comment="token/request/image_credit/free/all")
    multiplier = Column(DECIMAL(12, 6), nullable=False, default=1)
    schedule_type = Column(String(20), nullable=False, default="always", comment="always/daily_time")
    start_time = Column(Time, nullable=True, comment="Daily start time in Asia/Shanghai")
    end_time = Column(Time, nullable=True, comment="Daily end time in Asia/Shanghai")
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(SmallInteger, nullable=False, default=1)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserPriceAdjustmentRule(Base):
    """User-specific price multiplier rule by model series/type and Beijing-time schedule."""

    __tablename__ = "user_price_adjustment_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    user_id = Column(BigInteger, nullable=False, index=True)
    model_series = Column(String(32), nullable=False, default="all", comment="gpt/claude/grok/gemini/other/all")
    model_type = Column(String(20), nullable=False, default="all", comment="chat/image/video/embedding/completion/all")
    billing_type = Column(String(20), nullable=False, default="all", comment="token/request/image_credit/free/all")
    multiplier = Column(DECIMAL(12, 6), nullable=False, default=1)
    schedule_type = Column(String(20), nullable=False, default="always", comment="always/daily_time")
    start_time = Column(Time, nullable=True, comment="Daily start time in Asia/Shanghai")
    end_time = Column(Time, nullable=True, comment="Daily end time in Asia/Shanghai")
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(SmallInteger, nullable=False, default=1)
    description = Column(Text, nullable=True)
    created_by = Column(BigInteger, nullable=True, index=True)
    updated_by = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


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
