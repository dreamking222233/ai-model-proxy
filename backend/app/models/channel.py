"""ORM model for channel table."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, SmallInteger, func,
)

from app.database import Base


class Channel(Base):
    """Channel (model provider) model."""

    __tablename__ = "channel"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    base_url = Column(String(512), nullable=False)
    api_key = Column(Text, nullable=False, comment="Encrypted API key")
    protocol_type = Column(String(20), nullable=False, default="openai")
    provider_variant = Column(
        String(32),
        nullable=False,
        default="default",
        comment="Provider subtype such as default/google-official/google-vertex-image",
    )
    auth_header_type = Column(
        String(32),
        nullable=False,
        default="x-api-key",
        comment="Auth header type: x-api-key, anthropic-api-key, x-goog-api-key, authorization"
    )
    priority = Column(Integer, nullable=False, default=10, comment="Priority, 1=highest")
    enabled = Column(SmallInteger, nullable=False, default=1)
    is_healthy = Column(SmallInteger, nullable=False, default=1)
    health_score = Column(Integer, nullable=False, default=100, comment="Health score 0-100")
    failure_count = Column(Integer, nullable=False, default=0, comment="Consecutive failure count")
    circuit_breaker_until = Column(DateTime, nullable=True, comment="Circuit breaker expiry")
    health_check_model = Column(String(128), nullable=True, comment="Preferred model used for health checks")
    last_health_check_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
