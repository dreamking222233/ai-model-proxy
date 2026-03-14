"""ORM models for sys_user and user_api_key tables."""

from sqlalchemy import (
    Column, BigInteger, String, DateTime, SmallInteger, func,
)

from app.database import Base


class SysUser(Base):
    """System user model."""

    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True)
    email = Column(String(128), nullable=False, unique=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(10), nullable=False, default="user")
    status = Column(SmallInteger, nullable=False, default=1, comment="1=normal, 0=disabled")
    avatar = Column(String(512), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserApiKey(Base):
    """User API key model."""

    __tablename__ = "user_api_key"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(128), nullable=False, comment="Key display name")
    key_prefix = Column(String(16), nullable=False, comment="Display prefix e.g. sk-xxxx")
    key_hash = Column(String(64), nullable=False, unique=True, comment="SHA256 hash")
    key_full = Column(String(128), nullable=True, comment="Full API key plaintext")
    status = Column(String(10), nullable=False, default="active")
    expires_at = Column(DateTime, nullable=True)
    total_requests = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
