"""ORM models for online recharge orders and agent cash ledger."""

from sqlalchemy import (
    Column, BigInteger, String, DateTime, DECIMAL, Text, func,
)

from app.database import Base


class PaymentRechargeOrder(Base):
    """User online recharge order."""

    __tablename__ = "payment_recharge_order"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_no = Column(String(64), nullable=False, unique=True, index=True)
    payment_channel = Column(String(32), nullable=False, default="alipay", index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    agent_id = Column(BigInteger, nullable=True, index=True)
    site_scope = Column(String(16), nullable=False, default="platform", index=True)
    source_host = Column(String(255), nullable=True, index=True)
    return_url_snapshot = Column(String(512), nullable=True)
    amount_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    credited_usd = Column(DECIMAL(12, 6), nullable=False, default=0)
    agent_settlement_rate = Column(DECIMAL(12, 6), nullable=False, default=0)
    agent_income_cny = Column(DECIMAL(12, 2), nullable=False, default=0)
    status = Column(String(16), nullable=False, default="pending", index=True)
    subject = Column(String(128), nullable=False)
    body = Column(Text, nullable=True)
    alipay_trade_no = Column(String(64), nullable=True, unique=True, index=True)
    wechat_transaction_id = Column(String(64), nullable=True, unique=True, index=True)
    wechat_code_url = Column(Text, nullable=True)
    trade_status = Column(String(32), nullable=True, index=True)
    buyer_logon_id = Column(String(128), nullable=True)
    buyer_user_id = Column(String(64), nullable=True)
    expired_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    notify_raw = Column(Text, nullable=True)
    return_raw = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentCashBalance(Base):
    """Agent cash balance in RMB for online recharge commission."""

    __tablename__ = "agent_cash_balance"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, unique=True, index=True)
    balance = Column(DECIMAL(12, 2), nullable=False, default=0)
    total_income = Column(DECIMAL(12, 2), nullable=False, default=0)
    total_withdrawn = Column(DECIMAL(12, 2), nullable=False, default=0)
    total_adjusted = Column(DECIMAL(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class AgentCashLedger(Base):
    """Agent cash ledger in RMB."""

    __tablename__ = "agent_cash_ledger"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    order_id = Column(BigInteger, nullable=True, index=True)
    withdrawal_id = Column(BigInteger, nullable=True, index=True)
    action_type = Column(String(32), nullable=False, index=True)
    change_amount = Column(DECIMAL(12, 2), nullable=False, default=0)
    balance_before = Column(DECIMAL(12, 2), nullable=False, default=0)
    balance_after = Column(DECIMAL(12, 2), nullable=False, default=0)
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AgentCashWithdrawal(Base):
    """Offline withdrawal record for agent cash balance."""

    __tablename__ = "agent_cash_withdrawal"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(DECIMAL(12, 2), nullable=False, default=0)
    status = Column(String(16), nullable=False, default="completed", index=True)
    transfer_method = Column(String(32), nullable=False, default="offline_other")
    operator_user_id = Column(BigInteger, nullable=True, index=True)
    remark = Column(String(255), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
