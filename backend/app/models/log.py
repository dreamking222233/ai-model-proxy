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
    status = Column(String(10), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    client_ip = Column(String(45), nullable=True)
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
    input_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    output_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_cost = Column(DECIMAL(12, 6), nullable=False, default=0)
    balance_before = Column(DECIMAL(12, 6), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 6), nullable=False, default=0)
    billing_mode = Column(String(20), nullable=True, index=True, comment="balance=按量计费, subscription=套餐计费")
    subscription_id = Column(BigInteger, nullable=True, index=True, comment="关联套餐ID")
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
