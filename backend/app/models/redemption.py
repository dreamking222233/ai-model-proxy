"""Redemption code ORM model."""
from sqlalchemy import Column, BigInteger, String, DECIMAL, Enum, DateTime, func
from app.database import Base


class RedemptionCode(Base):
    """兑换码表"""
    __tablename__ = "redemption_code"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, comment="兑换码")
    amount = Column(DECIMAL(12, 6), nullable=False, comment="兑换金额(美元)")
    status = Column(
        Enum("unused", "used", "expired", name="redemption_status"),
        nullable=False,
        default="unused",
        comment="状态"
    )
    created_by = Column(BigInteger, nullable=False, comment="创建者(管理员ID)")
    used_by = Column(BigInteger, nullable=True, comment="使用者(用户ID)")
    used_at = Column(DateTime, nullable=True, comment="使用时间")
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
