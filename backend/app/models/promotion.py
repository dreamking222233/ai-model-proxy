"""ORM models for user promotion links, relations, and rewards."""

from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, DECIMAL, func, UniqueConstraint,
)

from app.database import Base


class UserPromotionLink(Base):
    """Promotion link owned by a user."""

    __tablename__ = "user_promotion_link"
    __table_args__ = (
        UniqueConstraint("invite_code", name="uk_user_promotion_link_code"),
        UniqueConstraint("user_id", name="uk_user_promotion_link_user"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    agent_id = Column(BigInteger, nullable=True, index=True)
    site_scope = Column(String(16), nullable=False, default="platform", index=True)
    site_host = Column(String(255), nullable=True, index=True)
    invite_code = Column(String(32), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="active", index=True)
    register_count = Column(BigInteger, nullable=False, default=0)
    recharge_user_count = Column(BigInteger, nullable=False, default=0)
    total_reward_usd = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_reward_image_credits = Column(DECIMAL(12, 3), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserPromotionRelation(Base):
    """Binding between promoter and invited user."""

    __tablename__ = "user_promotion_relation"
    __table_args__ = (
        UniqueConstraint("invited_user_id", name="uk_user_promotion_relation_invited"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    promoter_user_id = Column(BigInteger, nullable=False, index=True)
    promoter_agent_id = Column(BigInteger, nullable=True, index=True)
    invite_code = Column(String(32), nullable=False, index=True)
    invite_link_id = Column(BigInteger, nullable=False, index=True)
    invited_user_id = Column(BigInteger, nullable=False, index=True)
    invited_agent_id = Column(BigInteger, nullable=True, index=True)
    site_scope = Column(String(16), nullable=False, default="platform", index=True)
    site_host = Column(String(255), nullable=True, index=True)
    first_recharged_at = Column(DateTime, nullable=True)
    total_recharge_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    total_reward_usd = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_reward_image_credits = Column(DECIMAL(12, 3), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class UserPromotionReward(Base):
    """Reward record created from an invited user's successful recharge."""

    __tablename__ = "user_promotion_reward"
    __table_args__ = (
        UniqueConstraint("order_no", "reward_asset_type", name="uk_user_promotion_reward_order_asset"),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    relation_id = Column(BigInteger, nullable=False, index=True)
    promoter_user_id = Column(BigInteger, nullable=False, index=True)
    promoter_agent_id = Column(BigInteger, nullable=True, index=True)
    invited_user_id = Column(BigInteger, nullable=False, index=True)
    invite_code = Column(String(32), nullable=False, index=True)
    order_id = Column(BigInteger, nullable=False, index=True)
    order_no = Column(String(64), nullable=False, index=True)
    recharge_type = Column(String(32), nullable=False, default="balance", index=True)
    amount_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    credited_usd = Column(DECIMAL(12, 6), nullable=False, default=0)
    credited_image_credits = Column(DECIMAL(12, 3), nullable=False, default=0)
    reward_asset_type = Column(String(32), nullable=False, default="balance", index=True)
    reward_amount = Column(DECIMAL(12, 6), nullable=False, default=0)
    reward_rate = Column(DECIMAL(12, 6), nullable=False, default=0)
    status = Column(String(16), nullable=False, default="applied", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
