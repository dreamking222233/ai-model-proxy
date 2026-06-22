"""ORM models for agent tenant, balances, and inventory."""

from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, Date, SmallInteger, DECIMAL, func, UniqueConstraint,
)

from app.database import Base


class Agent(Base):
    """Agent tenant / white-label site."""

    __tablename__ = "agent"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_code = Column(String(64), nullable=False, unique=True, index=True)
    agent_name = Column(String(128), nullable=False)
    owner_user_id = Column(BigInteger, nullable=True, index=True)
    status = Column(String(16), nullable=False, default="active", index=True)
    frontend_domain = Column(String(255), nullable=True, unique=True, index=True)
    api_domain = Column(String(255), nullable=True, unique=True, index=True)
    site_title = Column(String(128), nullable=True)
    site_subtitle = Column(String(255), nullable=True)
    announcement_title = Column(String(128), nullable=True)
    announcement_content = Column(Text, nullable=True)
    support_wechat = Column(String(128), nullable=True)
    support_qq = Column(String(64), nullable=True)
    quickstart_api_base_url = Column(String(512), nullable=True)
    allow_self_register = Column(SmallInteger, nullable=False, default=1)
    online_recharge_enabled = Column(SmallInteger, nullable=False, default=1)
    subscription_online_recharge_enabled = Column(SmallInteger, nullable=False, default=1)
    theme_config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentBalance(Base):
    """Agent distributable USD balance pool."""

    __tablename__ = "agent_balance"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, unique=True, index=True)
    balance = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_recharged = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_allocated = Column(DECIMAL(12, 6), nullable=False, default=0)
    total_reclaimed = Column(DECIMAL(12, 6), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentBalanceRecord(Base):
    """Ledger for agent USD balance movements."""

    __tablename__ = "agent_balance_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=True, index=True)
    related_code_id = Column(BigInteger, nullable=True, index=True)
    action_type = Column(String(32), nullable=False, index=True)
    change_amount = Column(DECIMAL(12, 6), nullable=False, comment="Signed delta")
    balance_before = Column(DECIMAL(12, 6), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 6), nullable=False, default=0)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentImageBalance(Base):
    """Agent distributable image credit pool."""

    __tablename__ = "agent_image_balance"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, unique=True, index=True)
    balance = Column(DECIMAL(12, 3), nullable=False, default=0)
    total_recharged = Column(DECIMAL(12, 3), nullable=False, default=0)
    total_allocated = Column(DECIMAL(12, 3), nullable=False, default=0)
    total_reclaimed = Column(DECIMAL(12, 3), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentImageCreditRecord(Base):
    """Ledger for agent image credit movements."""

    __tablename__ = "agent_image_credit_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=True, index=True)
    action_type = Column(String(32), nullable=False, index=True)
    change_amount = Column(DECIMAL(12, 3), nullable=False, comment="Signed delta")
    balance_before = Column(DECIMAL(12, 3), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 3), nullable=False, default=0)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentSubscriptionInventory(Base):
    """Per-agent inventory for platform-managed subscription plans."""

    __tablename__ = "agent_subscription_inventory"
    __table_args__ = (
        UniqueConstraint("agent_id", "plan_id", name="uk_agent_subscription_inventory"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    plan_id = Column(BigInteger, nullable=False, index=True)
    total_granted = Column(Integer, nullable=False, default=0)
    total_used = Column(Integer, nullable=False, default=0)
    remaining_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentSubscriptionInventoryRecord(Base):
    """Inventory ledger for agent subscription plan stock."""

    __tablename__ = "agent_subscription_inventory_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    plan_id = Column(BigInteger, nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=True, index=True)
    action_type = Column(String(32), nullable=False, index=True)
    change_count = Column(Integer, nullable=False, comment="Signed delta")
    remaining_before = Column(Integer, nullable=False, default=0)
    remaining_after = Column(Integer, nullable=False, default=0)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentRedemptionAmountRule(Base):
    """Allowed redemption amounts for agents."""

    __tablename__ = "agent_redemption_amount_rule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=True, index=True, comment="NULL=global rule")
    amount = Column(DECIMAL(12, 6), nullable=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentDailyLimit(Base):
    """Daily credit limit for agent settlement-mode allocation."""

    __tablename__ = "agent_daily_limit"
    __table_args__ = (
        UniqueConstraint("agent_id", "resource_type", "plan_id_key", name="uk_agent_daily_limit_resource"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    resource_type = Column(String(32), nullable=False)
    plan_id = Column(BigInteger, nullable=True, index=True)
    plan_id_key = Column(BigInteger, nullable=False, default=0)
    daily_limit = Column(DECIMAL(20, 6), nullable=False, default=0)
    status = Column(String(16), nullable=False, default="active", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentDailyLimitUsage(Base):
    """Daily used amount for agent settlement-mode allocation."""

    __tablename__ = "agent_daily_limit_usage"
    __table_args__ = (
        UniqueConstraint("agent_id", "usage_date", "resource_type", "plan_id_key", name="uk_agent_daily_usage_resource"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    usage_date = Column(Date, nullable=False, index=True)
    resource_type = Column(String(32), nullable=False)
    plan_id = Column(BigInteger, nullable=True, index=True)
    plan_id_key = Column(BigInteger, nullable=False, default=0)
    used_amount = Column(DECIMAL(20, 6), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentSettlementRecord(Base):
    """Pending/settled ledger for agent credit-limit sales."""

    __tablename__ = "agent_settlement_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    target_user_id = Column(BigInteger, nullable=True, index=True)
    business_date = Column(Date, nullable=False, index=True)
    resource_type = Column(String(32), nullable=False, index=True)
    plan_id = Column(BigInteger, nullable=True, index=True)
    plan_code_snapshot = Column(String(64), nullable=True)
    plan_name_snapshot = Column(String(128), nullable=True)
    plan_kind_snapshot = Column(String(32), nullable=True)
    duration_days_snapshot = Column(Integer, nullable=True)
    quota_metric_snapshot = Column(String(32), nullable=True)
    quota_value_snapshot = Column(DECIMAL(20, 6), nullable=True)
    quantity = Column(DECIMAL(20, 6), nullable=False, default=0)
    settled_quantity = Column(DECIMAL(20, 6), nullable=False, default=0)
    unit_amount = Column(DECIMAL(20, 6), nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    source_action = Column(String(64), nullable=False)
    related_subscription_id = Column(BigInteger, nullable=True, index=True)
    related_balance_record_id = Column(BigInteger, nullable=True)
    related_image_record_id = Column(BigInteger, nullable=True)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentSettlementBatch(Base):
    """Admin settlement operation batch."""

    __tablename__ = "agent_settlement_batch"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    resource_type = Column(String(32), nullable=False, index=True)
    plan_id = Column(BigInteger, nullable=True, index=True)
    business_start_date = Column(Date, nullable=True)
    business_end_date = Column(Date, nullable=True)
    settled_quantity = Column(DECIMAL(20, 6), nullable=False, default=0)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentSettlementBatchItem(Base):
    """Records consumed by an admin settlement batch."""

    __tablename__ = "agent_settlement_batch_item"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(BigInteger, nullable=False, index=True)
    settlement_record_id = Column(BigInteger, nullable=False, index=True)
    settled_quantity = Column(DECIMAL(20, 6), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentSubscriptionSaleRecord(Base):
    """Paid user subscription purchase that may require offline agent rebate settlement."""

    __tablename__ = "agent_subscription_sale_record"
    __table_args__ = (
        UniqueConstraint("order_no", name="uk_agent_subscription_sale_order"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, nullable=False, index=True)
    order_no = Column(String(64), nullable=False, index=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    subscription_id = Column(BigInteger, nullable=True, index=True)
    plan_id = Column(BigInteger, nullable=True, index=True)
    plan_code_snapshot = Column(String(64), nullable=True)
    plan_name_snapshot = Column(String(128), nullable=False)
    plan_kind_snapshot = Column(String(32), nullable=True)
    duration_days_snapshot = Column(Integer, nullable=True)
    sale_price_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    agent_cost_price_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    agent_rebate_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    payment_channel = Column(String(32), nullable=False)
    payment_status = Column(String(16), nullable=False, default="paid", index=True)
    rebate_status = Column(String(16), nullable=False, default="pending", index=True)
    settled_at = Column(DateTime, nullable=True)
    settled_by = Column(BigInteger, nullable=True, index=True)
    settlement_remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
