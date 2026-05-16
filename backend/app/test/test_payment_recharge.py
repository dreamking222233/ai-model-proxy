"""Tests for recharge order settlement and agent cash ledger."""

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from unittest import TestCase
from unittest.mock import patch

from app.database import Base
from app.models.agent import Agent
from app.models.log import UserBalance, ConsumptionRecord
from app.models.payment import PaymentRechargeOrder, AgentCashBalance, AgentCashLedger, AgentCashWithdrawal
from app.models.user import SysUser
from app.core.exceptions import ServiceException
from app.services.agent_service import AgentSiteContext
from app.services.agent_cash_service import AgentCashService
from app.services.payment_service import PaymentService
from app.config import settings


class PaymentRechargeTestCase(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()
        self._id_counters = defaultdict(int)
        event.listen(self.db, "before_flush", self._assign_sqlite_bigint_ids)
        settings.ALIPAY_ENABLED = True
        settings.RECHARGE_USER_CNY_TO_USD_RATE = Decimal("5")
        settings.RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE = Decimal("10")

    def tearDown(self):
        event.remove(self.db, "before_flush", self._assign_sqlite_bigint_ids)
        self.db.close()
        self.engine.dispose()

    def _assign_sqlite_bigint_ids(self, session, flush_context, instances):
        """SQLite only autoincrements INTEGER PRIMARY KEY, not BIGINT."""
        for obj in session.new:
            if not hasattr(obj, "id") or getattr(obj, "id", None) is not None:
                continue
            counter_key = obj.__class__
            self._id_counters[counter_key] += 1
            setattr(obj, "id", self._id_counters[counter_key])

    def _create_user(self, user_id: int, agent_id=None) -> SysUser:
        user = SysUser(
            id=user_id,
            username=f"user{user_id}",
            email=f"user{user_id}@example.com",
            password_hash="hash",
            role="user",
            agent_id=agent_id,
            status=1,
        )
        self.db.add(user)
        self.db.add(UserBalance(user_id=user_id, balance=0, total_recharged=0, total_consumed=0))
        self.db.commit()
        return user

    def test_create_recharge_order_calculates_agent_income(self):
        user = self._create_user(1, agent_id=9)
        with patch.object(PaymentService, "_validate_payment_config"), patch.object(
            PaymentService,
            "build_alipay_page_pay_url",
            return_value="https://alipay.example.com/pay",
        ), patch.object(
            PaymentService,
            "build_order_return_url",
            return_value="https://agent.example.com/user/recharge?order_no=ALPTEST",
        ):
            result = PaymentService.create_recharge_order(self.db, user, Decimal("10.00"), site_context=None)

        order = result["order"]
        self.assertEqual(order["amount_cny"], 10.0)
        self.assertEqual(order["credited_usd"], 50.0)
        self.assertEqual(order["agent_income_cny"], 5.0)
        self.assertEqual(order["status"], "pending")

    def test_apply_paid_order_is_idempotent(self):
        self._create_user(2)
        order = PaymentRechargeOrder(
            order_no="ALP202605160001",
            payment_channel="alipay",
            user_id=2,
            agent_id=None,
            site_scope="platform",
            source_host="www.example.com",
            return_url_snapshot="https://www.example.com/user/recharge?order_no=ALP202605160001",
            amount_cny=Decimal("10.00"),
            credited_usd=Decimal("50.000000"),
            agent_settlement_rate=Decimal("10.000000"),
            agent_income_cny=Decimal("0.00"),
            status="pending",
            subject="AI 平台在线充值",
            body="test",
        )
        self.db.add(order)
        self.db.commit()

        payload = {
            "app_id": settings.ALIPAY_APP_ID,
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "10.00",
            "alipay_trade_no": "TRADE-001",
        }
        PaymentService._apply_paid_order(self.db, order.order_no, payload, source="query")
        PaymentService._apply_paid_order(self.db, order.order_no, payload, source="query")

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 2).first()
        self.assertEqual(Decimal(str(balance.balance)), Decimal("50.000000"))
        self.assertEqual(self.db.query(ConsumptionRecord).filter(ConsumptionRecord.user_id == 2).count(), 1)

    def test_apply_paid_order_credits_agent_cash(self):
        self.db.add(Agent(id=7, agent_code="agent-7", agent_name="Agent 7", status="active"))
        self.db.commit()
        self._create_user(3, agent_id=7)
        order = PaymentRechargeOrder(
            order_no="ALP202605160002",
            payment_channel="alipay",
            user_id=3,
            agent_id=7,
            site_scope="agent",
            source_host="agent.example.com",
            return_url_snapshot="https://agent.example.com/user/recharge?order_no=ALP202605160002",
            amount_cny=Decimal("10.00"),
            credited_usd=Decimal("50.000000"),
            agent_settlement_rate=Decimal("10.000000"),
            agent_income_cny=Decimal("5.00"),
            status="pending",
            subject="AI 平台在线充值",
            body="test",
        )
        self.db.add(order)
        self.db.commit()

        PaymentService._apply_paid_order(self.db, order.order_no, {
            "app_id": settings.ALIPAY_APP_ID,
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "10.00",
            "alipay_trade_no": "TRADE-002",
        }, source="notify")

        cash_balance = self.db.query(AgentCashBalance).filter(AgentCashBalance.agent_id == 7).first()
        self.assertIsNotNone(cash_balance)
        self.assertEqual(Decimal(str(cash_balance.balance)), Decimal("5.00"))
        self.assertEqual(self.db.query(AgentCashLedger).filter(AgentCashLedger.agent_id == 7).count(), 1)

    def test_apply_paid_order_allows_zero_agent_income(self):
        self.db.add(Agent(id=9, agent_code="agent-9", agent_name="Agent 9", status="active"))
        self.db.commit()
        self._create_user(4, agent_id=9)
        order = PaymentRechargeOrder(
            order_no="ALP202605160003",
            payment_channel="alipay",
            user_id=4,
            agent_id=9,
            site_scope="agent",
            source_host="agent.example.com",
            return_url_snapshot="https://agent.example.com/user/recharge?order_no=ALP202605160003",
            amount_cny=Decimal("0.01"),
            credited_usd=Decimal("0.050000"),
            agent_settlement_rate=Decimal("10.000000"),
            agent_income_cny=Decimal("0.00"),
            status="pending",
            subject="AI 平台在线充值",
            body="test",
        )
        self.db.add(order)
        self.db.commit()

        PaymentService._apply_paid_order(self.db, order.order_no, {
            "app_id": settings.ALIPAY_APP_ID,
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "0.01",
            "alipay_trade_no": "TRADE-003",
        }, source="notify")

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == 4).first()
        self.assertEqual(Decimal(str(balance.balance)), Decimal("0.050000"))
        self.assertEqual(self.db.query(AgentCashLedger).filter(AgentCashLedger.agent_id == 9).count(), 0)

    def test_assert_recharge_enabled_for_disabled_agent_site(self):
        context = AgentSiteContext(
            host="agent.example.com",
            site_scope="agent",
            is_api_host=False,
            agent=Agent(id=10, agent_code="agent-10", agent_name="Agent 10", status="active", online_recharge_enabled=0),
        )
        with self.assertRaises(ServiceException) as cm:
            PaymentService.assert_recharge_enabled_for_site(context)
        self.assertEqual(cm.exception.error_code, "AGENT_ONLINE_RECHARGE_DISABLED")

    def test_withdraw_agent_cash_deducts_balance(self):
        self.db.add(Agent(id=8, agent_code="agent-8", agent_name="Agent 8", status="active"))
        self.db.add(AgentCashBalance(agent_id=8, balance=Decimal("12.50"), total_income=Decimal("12.50"), total_withdrawn=0, total_adjusted=0))
        self.db.commit()

        result = AgentCashService.withdraw_agent_cash(
            self.db,
            agent_id=8,
            amount=Decimal("2.50"),
            transfer_method="wechat",
            operator_user_id=99,
            remark="test withdraw",
        )

        self.assertEqual(result["balance"], 10.0)
        self.assertEqual(result["total_withdrawn"], 2.5)
        self.assertEqual(self.db.query(AgentCashWithdrawal).filter(AgentCashWithdrawal.agent_id == 8).count(), 1)
        self.assertEqual(self.db.query(AgentCashLedger).filter(AgentCashLedger.agent_id == 8).count(), 1)
