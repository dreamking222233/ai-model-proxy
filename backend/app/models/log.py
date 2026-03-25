"""ORM models for health_check_log, request_log, system_config, operation_log, user_balance, consumption_record."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, SmallInteger, DECIMAL, func,
)

from app.database import Base


class HealthCheckLog(Base):
    """Health check log entry."""

    __tablename__ = "health_check_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, nullable=False, index=True)
    channel_name = Column(String(128), nullable=False)
    model_name = Column(String(128), nullable=True)
    status = Column(String(10), nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime, nullable=False, server_default=func.now())


class RequestLog(Base):
    """Request log entry."""

    __tablename__ = "request_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False, unique=True, comment="UUID")
    user_id = Column(BigInteger, nullable=True, index=True)
    user_api_key_id = Column(BigInteger, nullable=True)
    channel_id = Column(BigInteger, nullable=True, index=True)
    channel_name = Column(String(128), nullable=True)
    requested_model = Column(String(128), nullable=True, index=True, comment="User-requested model name")
    actual_model = Column(String(128), nullable=True, comment="Actually dispatched model name")
    protocol_type = Column(String(20), nullable=True)
    is_stream = Column(SmallInteger, nullable=True, default=0)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    response_time_ms = Column(Integer, nullable=True)
    cache_status = Column(String(20), nullable=True, comment="Request body cache status")
    cache_hit_segments = Column(Integer, nullable=True, default=0)
    cache_miss_segments = Column(Integer, nullable=True, default=0)
    cache_bypass_segments = Column(Integer, nullable=True, default=0)
    cache_reused_tokens = Column(Integer, nullable=True, default=0)
    cache_new_tokens = Column(Integer, nullable=True, default=0)
    cache_reused_chars = Column(Integer, nullable=True, default=0)
    cache_new_chars = Column(Integer, nullable=True, default=0)
    logical_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_read_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_creation_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_creation_5m_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_creation_1h_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_prompt_cache_status = Column(String(20), nullable=True, comment="Anthropic prompt cache status")
    conversation_session_id = Column(String(64), nullable=True, index=True, comment="Conversation session id")
    conversation_match_status = Column(String(20), nullable=True, comment="Conversation match status")
    compression_mode = Column(String(32), nullable=True, comment="Conversation compaction mode")
    compression_status = Column(String(64), nullable=True, comment="Conversation compaction status")
    original_estimated_input_tokens = Column(Integer, nullable=True, default=0)
    compressed_estimated_input_tokens = Column(Integer, nullable=True, default=0)
    compression_saved_estimated_tokens = Column(Integer, nullable=True, default=0)
    compression_ratio = Column(DECIMAL(10, 4), nullable=True, default=0)
    compression_fallback_reason = Column(Text, nullable=True)
    upstream_session_mode = Column(String(20), nullable=True, comment="Upstream session mode")
    upstream_session_id = Column(String(128), nullable=True, comment="Upstream session id")
    status = Column(String(10), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    client_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class RequestCacheSummary(Base):
    """Per-request request-body cache analysis summary."""

    __tablename__ = "request_cache_summary"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False, unique=True, index=True, comment="Request UUID")
    user_id = Column(BigInteger, nullable=True, index=True)
    requested_model = Column(String(128), nullable=True, index=True)
    protocol_type = Column(String(20), nullable=True)
    request_format = Column(String(32), nullable=True, comment="anthropic_messages/openai_chat/responses")
    cache_status = Column(String(20), nullable=False, default="BYPASS")
    hit_segment_count = Column(Integer, nullable=False, default=0)
    miss_segment_count = Column(Integer, nullable=False, default=0)
    bypass_segment_count = Column(Integer, nullable=False, default=0)
    reused_tokens = Column(Integer, nullable=False, default=0)
    new_tokens = Column(Integer, nullable=False, default=0)
    reused_chars = Column(Integer, nullable=False, default=0)
    new_chars = Column(Integer, nullable=False, default=0)
    ttl_seconds = Column(Integer, nullable=False, default=0)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class SystemConfig(Base):
    """System configuration key-value store."""

    __tablename__ = "system_config"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(128), nullable=False, unique=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(10), nullable=False, default="string")
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class OperationLog(Base):
    """Operation audit log."""

    __tablename__ = "operation_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    username = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True)
    target_id = Column(BigInteger, nullable=True)
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserBalance(Base):
    """User balance tracking."""

    __tablename__ = "user_balance"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True)
    balance = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Balance (USD)")
    total_recharged = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Total recharged")
    total_consumed = Column(DECIMAL(12, 6), nullable=False, default=0, comment="Total consumed")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ConsumptionRecord(Base):
    """Per-request consumption record for billing."""

    __tablename__ = "consumption_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    request_id = Column(String(36), nullable=True, index=True)
    model_name = Column(String(128), nullable=True)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    logical_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_read_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_cache_creation_input_tokens = Column(Integer, nullable=True, default=0)
    upstream_prompt_cache_status = Column(String(20), nullable=True, comment="Anthropic prompt cache status")
    input_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    output_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    balance_before = Column(DECIMAL(12, 6), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 6), nullable=False, default=0)
    billing_mode = Column(String(20), nullable=True, index=True, comment="balance=按量计费, subscription=套餐计费")
    subscription_id = Column(BigInteger, nullable=True, index=True, comment="关联套餐ID")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ConversationSession(Base):
    """Conversation session state metadata."""

    __tablename__ = "conversation_session"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    requested_model = Column(String(128), nullable=True, index=True)
    protocol_type = Column(String(20), nullable=True, index=True)
    channel_id = Column(BigInteger, nullable=True, index=True)
    system_hash = Column(String(64), nullable=False, index=True)
    tools_hash = Column(String(64), nullable=False, index=True)
    message_count = Column(Integer, nullable=False, default=0)
    last_message_hash = Column(String(64), nullable=True, index=True)
    compression_mode = Column(String(32), nullable=True, default="shadow")
    upstream_session_mode = Column(String(20), nullable=True, default="stateless")
    upstream_session_id = Column(String(128), nullable=True)
    state_version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="active", index=True)
    last_shadow_saved_tokens = Column(Integer, nullable=False, default=0)
    cooldown_until = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ConversationCheckpoint(Base):
    """Persisted conversation history checkpoint summary."""

    __tablename__ = "conversation_checkpoint"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    checkpoint_seq = Column(Integer, nullable=False, default=1)
    source_turn_start = Column(Integer, nullable=False, default=0)
    source_turn_end = Column(Integer, nullable=False, default=0)
    source_hash = Column(String(64), nullable=False, index=True)
    summary_json = Column(Text, nullable=False)
    summary_token_estimate = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserSubscription(Base):
    """User subscription record."""

    __tablename__ = "user_subscription"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    plan_name = Column(String(64), nullable=False, comment="套餐名称")
    plan_type = Column(String(20), nullable=False, comment="套餐类型: monthly/quarterly/yearly/custom")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=False, comment="结束时间")
    status = Column(String(10), nullable=False, default="active", comment="状态: active/expired/cancelled")
    created_by = Column(BigInteger, nullable=True, comment="创建者（管理员ID）")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
