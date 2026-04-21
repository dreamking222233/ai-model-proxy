"""ORM models for health_check_log, request_log, system_config, operation_log, user_balance, consumption_record."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, SmallInteger, DECIMAL, Date, func, UniqueConstraint,
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
    request_type = Column(String(32), nullable=True, default="chat", comment="chat/responses/image_generation")
    billing_type = Column(String(20), nullable=True, default="token", comment="token/subscription/image_credit/free")
    is_stream = Column(SmallInteger, nullable=True, default=0)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    raw_input_tokens = Column(Integer, nullable=True, default=0)
    raw_output_tokens = Column(Integer, nullable=True, default=0)
    raw_total_tokens = Column(Integer, nullable=True, default=0)
    image_credits_charged = Column(DECIMAL(12, 3), nullable=True, default=0)
    image_count = Column(Integer, nullable=True, default=0)
    image_size = Column(String(16), nullable=True, comment="Google image size such as 1K/2K/4K")
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
    subscription_cycle_id = Column(BigInteger, nullable=True, index=True)
    quota_metric = Column(String(20), nullable=True, comment="total_tokens/cost_usd")
    quota_consumed_amount = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_limit_snapshot = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_used_after = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_cycle_date = Column(Date, nullable=True)
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
    raw_input_tokens = Column(Integer, nullable=True, default=0)
    raw_output_tokens = Column(Integer, nullable=True, default=0)
    raw_total_tokens = Column(Integer, nullable=True, default=0)
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
    subscription_cycle_id = Column(BigInteger, nullable=True, index=True, comment="关联套餐周期ID")
    quota_metric = Column(String(20), nullable=True, comment="total_tokens/cost_usd")
    quota_consumed_amount = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_limit_snapshot = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_used_after = Column(DECIMAL(20, 6), nullable=True, default=0)
    quota_cycle_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class UserImageBalance(Base):
    """User image credit balance tracking."""

    __tablename__ = "user_image_balance"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True)
    balance = Column(DECIMAL(12, 3), nullable=False, default=0, comment="Image credit balance")
    total_recharged = Column(DECIMAL(12, 3), nullable=False, default=0, comment="Total image credits recharged")
    total_consumed = Column(DECIMAL(12, 3), nullable=False, default=0, comment="Total image credits consumed")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ImageCreditRecord(Base):
    """Image credit ledger record."""

    __tablename__ = "image_credit_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    request_id = Column(String(36), nullable=True, index=True)
    model_name = Column(String(128), nullable=True)
    change_amount = Column(DECIMAL(12, 3), nullable=False, comment="Positive for recharge, negative for deduction")
    balance_before = Column(DECIMAL(12, 3), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 3), nullable=False, default=0)
    multiplier = Column(DECIMAL(12, 3), nullable=False, default=1)
    image_size = Column(String(16), nullable=True, comment="Google image size such as 1K/2K/4K")
    action_type = Column(String(20), nullable=False, default="request", comment="request/recharge/deduct")
    operator_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
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
    plan_id = Column(BigInteger, nullable=True, index=True)
    plan_code_snapshot = Column(String(64), nullable=True, comment="套餐编码快照")
    plan_name = Column(String(64), nullable=False, comment="套餐名称")
    plan_type = Column(String(20), nullable=False, comment="套餐类型: monthly/quarterly/yearly/custom")
    plan_kind_snapshot = Column(String(20), nullable=True, comment="unlimited/daily_quota")
    duration_days_snapshot = Column(Integer, nullable=True, default=0)
    quota_metric = Column(String(20), nullable=True, comment="total_tokens/cost_usd")
    quota_value = Column(DECIMAL(20, 6), nullable=True, default=0)
    reset_period = Column(String(20), nullable=True, default="day")
    reset_timezone = Column(String(64), nullable=True, default="Asia/Shanghai")
    activation_mode = Column(String(20), nullable=True, default="append")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=False, comment="结束时间")
    status = Column(String(10), nullable=False, default="active", comment="状态: active/expired/cancelled")
    created_by = Column(BigInteger, nullable=True, comment="创建者（管理员ID）")
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SubscriptionPlan(Base):
    """Subscription plan template managed by admins."""

    __tablename__ = "subscription_plan"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_code = Column(String(64), nullable=False, unique=True, index=True, comment="套餐编码")
    plan_name = Column(String(64), nullable=False, comment="套餐名称")
    plan_kind = Column(String(20), nullable=False, default="unlimited", comment="unlimited/daily_quota")
    duration_mode = Column(String(20), nullable=False, default="custom", comment="day/month/custom")
    duration_days = Column(Integer, nullable=False, default=1, comment="套餐时长（天）")
    quota_metric = Column(String(20), nullable=True, comment="total_tokens/cost_usd")
    quota_value = Column(DECIMAL(20, 6), nullable=True, default=0)
    reset_period = Column(String(20), nullable=False, default="day")
    reset_timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(String(10), nullable=False, default="active", comment="active/inactive")
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class SubscriptionUsageCycle(Base):
    """Daily quota usage ledger for a subscription."""

    __tablename__ = "subscription_usage_cycle"
    __table_args__ = (
        UniqueConstraint("subscription_id", "cycle_date", name="uk_subscription_cycle_date"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    subscription_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    cycle_date = Column(Date, nullable=False, index=True)
    cycle_start_at = Column(DateTime, nullable=False)
    cycle_end_at = Column(DateTime, nullable=False)
    quota_metric = Column(String(20), nullable=False)
    quota_limit = Column(DECIMAL(20, 6), nullable=False, default=0)
    used_amount = Column(DECIMAL(20, 6), nullable=False, default=0)
    request_count = Column(Integer, nullable=False, default=0)
    last_request_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
