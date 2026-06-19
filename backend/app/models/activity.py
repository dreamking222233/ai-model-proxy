"""ORM models for limited-time activity features."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    DECIMAL,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database import Base


class DragonBoatLotteryEntry(Base):
    """Dragon Boat Festival lottery registration and winner record."""

    __tablename__ = "dragon_boat_lottery_entry"
    __table_args__ = (
        UniqueConstraint("user_id", name="uk_dragon_boat_lottery_user"),
        UniqueConstraint("prize_rank", name="uk_dragon_boat_lottery_prize_rank"),
        Index("idx_dragon_boat_lottery_status", "status"),
        Index("idx_dragon_boat_lottery_prize_rank", "prize_rank"),
        Index("idx_dragon_boat_lottery_created_at", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(64), nullable=False)
    email = Column(String(128), nullable=False)
    agent_id = Column(BigInteger, nullable=True, index=True)
    qualification_type = Column(String(32), nullable=False)
    qualification_detail = Column(String(255), nullable=True)
    total_recharged_snapshot = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_consumed_snapshot = Column(DECIMAL(12, 6), nullable=False, default=0)
    subscription_id_snapshot = Column(BigInteger, nullable=True)
    status = Column(String(16), nullable=False, default="registered")
    prize_rank = Column(BigInteger, nullable=True)
    prize_amount = Column(DECIMAL(12, 6), nullable=False, default=0)
    drawn_by_user_id = Column(BigInteger, nullable=True)
    drawn_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
