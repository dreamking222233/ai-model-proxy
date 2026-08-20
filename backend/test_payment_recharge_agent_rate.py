"""Regression tests for agent recharge pricing and settlement rates."""

from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.user.payment import list_subscription_plans
from app.config import settings
from app.core.exceptions import ServiceException
from app.database import Base
from app.models.agent import Agent, AgentSubscriptionSaleRecord
from app.models.log import (
    ConsumptionRecord,
    ImageCreditRecord,
    OperationLog,
    SubscriptionPlan,
    SystemConfig,
    UserBalance,
    UserImageBalance,
    UserSubscription,
)
from app.models.payment import (
    AgentCashBalance,
    AgentCashLedger,
    PaymentRechargeOrder,
    PaymentRechargeSettlement,
)
from app.models.promotion import UserPromotionLink, UserPromotionRelation, UserPromotionReward
from app.models.user import SysUser
from app.schemas.agent import AgentSiteConfigUpdate
from app.services.agent_service import AgentAuditContext, AgentService, AgentSiteContext
from app.services.log_service import LogService
from app.services.payment_service import PaymentService
from app.services.promotion_service import PromotionService
from app.services.subscription_service import SubscriptionService


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, agent=None):
        self.agent = agent
        self.initial_agent = agent
        self.initial_agent_values = {
            column.name: getattr(agent, column.name)
            for column in Agent.__table__.columns
        } if agent is not None else {}
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0

    def query(self, model):
        return _Query(self.agent if model is Agent else None)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, Agent):
            self.agent = value

    def flush(self):
        for index, value in enumerate(self.added, start=1):
            if getattr(value, "id", None) is None:
                value.id = index

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1
        self.agent = self.initial_agent
        if self.initial_agent is not None:
            for field, value in self.initial_agent_values.items():
                setattr(self.initial_agent, field, value)

    def refresh(self, value):
        return None


class _PromotionQuery(_Query):
    def with_for_update(self):
        return self


class _PromotionDb:
    def __init__(self, rows):
        self.rows = rows
        self.added = []

    def query(self, model):
        return _PromotionQuery(self.rows.get(model))

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None

    def begin_nested(self):
        return nullcontext()


def _agent(**overrides):
    values = {
        "id": 7,
        "agent_code": "agent-7",
        "agent_name": "Agent 7",
        "status": "active",
        "online_recharge_enabled": 1,
        "subscription_online_recharge_enabled": 1,
        "custom_recharge_rate_enabled": 1,
        "custom_recharge_rate": Decimal("1"),
    }
    values.update(overrides)
    return Agent(**values)


class PaymentRechargeAgentRateTest(unittest.TestCase):
    def test_custom_balance_rate_changes_user_credit_but_not_agent_settlement_rate(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="balance",
            user_recharge_rate=Decimal("1"),
        )

        self.assertEqual(Decimal("100.000000"), credited_usd)
        self.assertEqual(Decimal("0.000"), credited_image_credits)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("85.71"), agent_income_cny)

    def test_custom_image_rate_changes_user_credit_but_not_agent_settlement_rate(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="image_credit",
            user_recharge_rate=Decimal("1"),
        )

        self.assertEqual(Decimal("0.000000"), credited_usd)
        self.assertEqual(Decimal("100.000"), credited_image_credits)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("85.71"), agent_income_cny)

    def test_custom_rate_at_settlement_ceiling_has_zero_agent_income(self):
        credited_usd, _, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="balance",
            user_recharge_rate=Decimal("7"),
        )

        self.assertEqual(Decimal("700.000000"), credited_usd)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("0.00"), agent_income_cny)

    def test_agent_balance_recharge_uses_seven_to_one_settlement_rate(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="balance",
        )

        self.assertEqual(Decimal("7"), settings.RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE)
        self.assertEqual(Decimal("500.000000"), credited_usd)
        self.assertEqual(Decimal("0.000"), credited_image_credits)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("28.57"), agent_income_cny)

    def test_agent_image_credit_recharge_uses_seven_to_one_settlement_rate(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="image_credit",
        )

        self.assertEqual(Decimal("7"), settings.RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE)
        self.assertEqual(Decimal("0.000000"), credited_usd)
        self.assertEqual(Decimal("500.000"), credited_image_credits)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("28.57"), agent_income_cny)

    def test_platform_recharge_has_no_agent_income(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=None,
            recharge_type="balance",
        )

        self.assertEqual(Decimal("500.000000"), credited_usd)
        self.assertEqual(Decimal("0.000"), credited_image_credits)
        self.assertEqual(Decimal("7"), agent_rate)
        self.assertEqual(Decimal("0.00"), agent_income_cny)

    def test_subscription_type_does_not_use_recharge_agent_rate(self):
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(
            Decimal("100"),
            agent_id=1,
            recharge_type="subscription",
        )

        self.assertEqual(Decimal("0.000000"), credited_usd)
        self.assertEqual(Decimal("0.000"), credited_image_credits)
        self.assertEqual(Decimal("0.000000"), agent_rate)
        self.assertEqual(Decimal("0.00"), agent_income_cny)


class AgentCustomRechargePolicyTest(unittest.TestCase):
    def setUp(self):
        self.payment_settings = patch.multiple(
            settings,
            ALIPAY_ENABLED=True,
            WECHAT_PAY_ENABLED=False,
            RECHARGE_USER_CNY_TO_USD_RATE=Decimal("5"),
            RECHARGE_IMAGE_CREDIT_USER_CNY_RATE=Decimal("5"),
            RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE=Decimal("7"),
            RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE=Decimal("7"),
        )
        self.payment_settings.start()

    def tearDown(self):
        self.payment_settings.stop()

    @staticmethod
    def _audit_context(source="admin"):
        return AgentAuditContext(
            user_id=99,
            username="operator",
            source=source,
            ip_address="127.0.0.1",
        )

    def test_custom_policy_uses_one_rate_and_disables_subscription_purchase(self):
        policy = AgentService.resolve_user_recharge_policy(
            _Db(_agent()),
            SimpleNamespace(agent_id=7),
        )

        self.assertEqual(Decimal("1.000000"), policy.balance_recharge_rate)
        self.assertEqual(Decimal("1.000000"), policy.image_credit_recharge_rate)
        self.assertEqual(Decimal("7"), policy.balance_agent_settlement_rate)
        self.assertEqual(Decimal("7"), policy.max_custom_recharge_rate)
        self.assertTrue(policy.online_recharge_enabled)
        self.assertFalse(policy.subscription_online_recharge_enabled)

    def test_agent_without_permission_keeps_global_rates_and_subscription_setting(self):
        policy = AgentService.resolve_user_recharge_policy(
            _Db(_agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("1"))),
            SimpleNamespace(agent_id=7),
        )

        self.assertEqual(Decimal("5"), policy.balance_recharge_rate)
        self.assertEqual(Decimal("5"), policy.image_credit_recharge_rate)
        self.assertTrue(policy.subscription_online_recharge_enabled)

    def test_missing_or_disabled_agent_fails_closed(self):
        for db in (_Db(None), _Db(_agent(status="disabled"))):
            with self.subTest(agent=db.agent):
                with self.assertRaises(ServiceException) as raised:
                    AgentService.resolve_user_recharge_policy(db, SimpleNamespace(agent_id=7))
                self.assertEqual("AGENT_RECHARGE_POLICY_UNAVAILABLE", raised.exception.error_code)

    def test_invalid_custom_rate_is_rejected_at_runtime(self):
        with self.assertRaises(ServiceException) as raised:
            AgentService.resolve_user_recharge_policy(
                _Db(_agent(custom_recharge_rate=Decimal("7.000001"))),
                SimpleNamespace(agent_id=7),
            )

        self.assertEqual("AGENT_CUSTOM_RECHARGE_RATE_EXCEEDS_LIMIT", raised.exception.error_code)

    def test_rate_boundaries_and_schema_precision(self):
        self.assertEqual(Decimal("0.010000"), AgentService.validate_custom_recharge_rate("0.01"))
        self.assertEqual(Decimal("7.000000"), AgentService.validate_custom_recharge_rate("7"))
        with self.assertRaises(ServiceException):
            AgentService.validate_custom_recharge_rate("7.000001")
        with self.assertRaises(ValidationError):
            AgentSiteConfigUpdate(custom_recharge_rate="1.1234567")

    def test_permission_is_required_and_enabling_validates_saved_rate(self):
        disabled_agent = _agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("1"))
        with self.assertRaises(ServiceException) as denied:
            AgentService.update_agent_site_config(
                _Db(disabled_agent),
                7,
                {"custom_recharge_rate": Decimal("1")},
            )
        self.assertEqual("AGENT_CUSTOM_RECHARGE_RATE_FORBIDDEN", denied.exception.error_code)

        invalid_agent = _agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("8"))
        with self.assertRaises(ServiceException) as invalid:
            AgentService.update_agent(
                _Db(invalid_agent),
                7,
                {"custom_recharge_rate_enabled": 1},
            )
        self.assertEqual("AGENT_CUSTOM_RECHARGE_RATE_EXCEEDS_LIMIT", invalid.exception.error_code)

        valid_agent = _agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("1"))
        updated = AgentService.update_agent(
            _Db(valid_agent),
            7,
            {"custom_recharge_rate_enabled": 1},
        )
        self.assertTrue(updated["custom_recharge_rate_enabled"])

    def test_agent_site_schema_discards_permission_field(self):
        payload = AgentSiteConfigUpdate(custom_recharge_rate_enabled=1).model_dump(exclude_unset=True)
        self.assertNotIn("custom_recharge_rate_enabled", payload)

    def test_shared_api_public_config_still_uses_authenticated_agent_policy(self):
        context = AgentSiteContext(
            host="api.example.test",
            site_scope="platform",
            is_api_host=True,
            request_host="api.example.test",
        )
        config_map = dict(AgentService.PLATFORM_CONFIG_DEFAULTS)
        with patch.object(AgentService, "get_site_context_from_request", return_value=context), patch.object(
            AgentService,
            "_get_platform_config_map",
            return_value=config_map,
        ):
            result = AgentService.build_public_site_config(
                _Db(_agent()),
                host="api.example.test",
                user=SimpleNamespace(agent_id=7),
            )

        self.assertEqual("platform", result["site_scope"])
        self.assertEqual(1.0, result["balance_recharge_rate"])
        self.assertEqual(1.0, result["image_credit_recharge_rate"])
        self.assertFalse(result["subscription_online_recharge_enabled"])

    def test_custom_subscription_order_is_rejected_by_service(self):
        with patch.object(PaymentService, "_validate_payment_config", return_value=None):
            with self.assertRaises(ServiceException) as raised:
                PaymentService.create_recharge_order(
                    _Db(_agent()),
                    user=SimpleNamespace(id=11, agent_id=7),
                    amount_cny=None,
                    recharge_type="subscription",
                    subscription_plan_id=3,
                )

        self.assertEqual("AGENT_CUSTOM_PRICING_SUBSCRIPTION_DISABLED", raised.exception.error_code)

    def test_custom_balance_order_captures_user_and_agent_rate_snapshots(self):
        db = _Db(_agent())
        user = SimpleNamespace(id=11, agent_id=7)
        with patch.object(PaymentService, "_validate_payment_config", return_value=None), patch.object(
            PaymentService,
            "build_order_return_url",
            return_value="https://agent.example.test/user/recharge?order_no=test",
        ), patch.object(
            PaymentService,
            "build_alipay_page_pay_url",
            return_value="https://pay.example.test/order",
        ):
            result = PaymentService.create_recharge_order(
                db,
                user=user,
                amount_cny=Decimal("100"),
                recharge_type="balance",
            )

        order = next(value for value in db.added if isinstance(value, PaymentRechargeOrder))
        self.assertEqual(Decimal("1.000000"), order.user_recharge_rate)
        self.assertEqual(Decimal("7"), order.agent_settlement_rate)
        self.assertEqual(Decimal("100.000000"), order.credited_usd)
        self.assertEqual(Decimal("85.71"), order.agent_income_cny)
        self.assertEqual(1.0, result["order"]["user_recharge_rate"])

    def test_create_with_permission_writes_audit_in_service_transaction(self):
        db = _Db()
        created = AgentService.create_agent(
            db,
            {
                "agent_code": "new-agent",
                "agent_name": "New Agent",
                "custom_recharge_rate_enabled": 1,
            },
            audit_context=self._audit_context(),
        )

        log = next(value for value in db.added if isinstance(value, OperationLog))
        description = json.loads(log.description)
        self.assertTrue(created["custom_recharge_rate_enabled"])
        self.assertEqual("update_agent_recharge_pricing_permission", log.action)
        self.assertEqual("create", description["event"])
        self.assertEqual(1, db.commit_count)

    def test_permission_update_and_audit_share_one_commit(self):
        db = _Db(_agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("1")))
        updated = AgentService.update_agent(
            db,
            7,
            {"custom_recharge_rate_enabled": 1},
            audit_context=self._audit_context(),
        )

        logs = [value for value in db.added if isinstance(value, OperationLog)]
        self.assertTrue(updated["custom_recharge_rate_enabled"])
        self.assertEqual(1, len(logs))
        self.assertEqual(1, db.commit_count)
        self.assertEqual(0, db.rollback_count)

    def test_audit_failure_rolls_back_permission_update(self):
        agent = _agent(custom_recharge_rate_enabled=0, custom_recharge_rate=Decimal("1"))
        db = _Db(agent)
        with patch.object(LogService, "create_operation_log", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                AgentService.update_agent(
                    db,
                    7,
                    {"custom_recharge_rate_enabled": 1},
                    audit_context=self._audit_context(),
                )

        self.assertEqual(0, agent.custom_recharge_rate_enabled)
        self.assertEqual(0, db.commit_count)
        self.assertEqual(1, db.rollback_count)

    def test_agent_rate_update_writes_before_and_after_values(self):
        db = _Db(_agent(custom_recharge_rate=Decimal("1")))
        AgentService.update_agent_site_config(
            db,
            7,
            {"custom_recharge_rate": Decimal("2")},
            audit_context=self._audit_context(source="agent"),
        )

        log = next(value for value in db.added if isinstance(value, OperationLog))
        changes = json.loads(log.description)["changes"]
        self.assertEqual({"before": 1.0, "after": 2.0}, changes["custom_recharge_rate"])
        self.assertEqual(1, db.commit_count)

    def test_promotion_reward_uses_custom_credit_without_reducing_agent_income(self):
        now = datetime.utcnow()
        relation = UserPromotionRelation(
            id=1,
            promoter_user_id=22,
            promoter_agent_id=7,
            invited_user_id=11,
            invite_code="INVITE01",
            invite_link_id=2,
            first_recharged_at=None,
            total_recharge_cny=Decimal("0"),
            total_reward_usd=Decimal("0"),
            total_reward_image_credits=Decimal("0"),
            created_at=now,
        )
        link = UserPromotionLink(
            id=2,
            recharge_user_count=0,
            total_reward_usd=Decimal("0"),
            total_reward_image_credits=Decimal("0"),
        )
        promoter_balance = UserBalance(user_id=22, balance=Decimal("0"), total_recharged=0, total_consumed=0)
        invited = SysUser(id=11, username="invited")
        order = PaymentRechargeOrder(
            id=3,
            order_no="CUSTOM-RATE-ORDER",
            recharge_type="balance",
            user_id=11,
            agent_id=7,
            amount_cny=Decimal("100"),
            credited_usd=Decimal("100"),
            credited_image_credits=Decimal("0"),
            user_recharge_rate=Decimal("1"),
            agent_settlement_rate=Decimal("7"),
            agent_income_cny=Decimal("85.71"),
            status="paid",
            paid_at=now,
            created_at=now,
        )
        db = _PromotionDb({
            UserPromotionRelation: relation,
            SystemConfig.config_value: ("0.2",),
            SysUser: invited,
            UserBalance: promoter_balance,
            UserPromotionLink: link,
        })

        PromotionService.apply_recharge_reward(db, order)

        reward = next(value for value in db.added if isinstance(value, UserPromotionReward))
        self.assertEqual(Decimal("20.000000"), reward.reward_amount)
        self.assertEqual(Decimal("20.000000"), promoter_balance.balance)
        self.assertEqual(Decimal("85.71"), order.agent_income_cny)
        self.assertTrue(any(isinstance(value, ConsumptionRecord) for value in db.added))

    def test_image_promotion_reward_uses_custom_credit_snapshot(self):
        now = datetime.utcnow()
        relation = UserPromotionRelation(
            id=1,
            promoter_user_id=22,
            promoter_agent_id=7,
            invited_user_id=11,
            invite_code="INVITE01",
            invite_link_id=2,
            first_recharged_at=now,
            total_recharge_cny=Decimal("0"),
            total_reward_usd=Decimal("0"),
            total_reward_image_credits=Decimal("0"),
            created_at=now,
        )
        link = UserPromotionLink(
            id=2,
            recharge_user_count=1,
            total_reward_usd=Decimal("0"),
            total_reward_image_credits=Decimal("0"),
        )
        promoter_balance = UserImageBalance(user_id=22, balance=Decimal("0"), total_recharged=0, total_consumed=0)
        order = PaymentRechargeOrder(
            id=4,
            order_no="CUSTOM-IMAGE-ORDER",
            recharge_type="image_credit",
            user_id=11,
            agent_id=7,
            amount_cny=Decimal("100"),
            credited_usd=Decimal("0"),
            credited_image_credits=Decimal("100"),
            user_recharge_rate=Decimal("1"),
            agent_settlement_rate=Decimal("7"),
            agent_income_cny=Decimal("85.71"),
            status="paid",
            paid_at=now,
            created_at=now,
        )
        db = _PromotionDb({
            UserPromotionRelation: relation,
            SystemConfig.config_value: ("0.2",),
            SysUser: None,
            UserImageBalance: promoter_balance,
            UserPromotionLink: link,
        })

        PromotionService.apply_recharge_reward(db, order)

        reward = next(value for value in db.added if isinstance(value, UserPromotionReward))
        self.assertEqual(Decimal("20.000"), reward.reward_amount)
        self.assertEqual(Decimal("20.000"), promoter_balance.balance)
        self.assertEqual(Decimal("85.71"), order.agent_income_cny)
        self.assertTrue(any(isinstance(value, ImageCreditRecord) for value in db.added))


class PaymentRechargeCallbackIntegrationTest(unittest.TestCase):
    """Exercise order snapshots through the real paid-order transaction."""

    TABLES = [
        Agent.__table__,
        SysUser.__table__,
        UserBalance.__table__,
        ConsumptionRecord.__table__,
        UserImageBalance.__table__,
        ImageCreditRecord.__table__,
        SubscriptionPlan.__table__,
        UserSubscription.__table__,
        PaymentRechargeOrder.__table__,
        PaymentRechargeSettlement.__table__,
        AgentCashBalance.__table__,
        AgentCashLedger.__table__,
        AgentSubscriptionSaleRecord.__table__,
    ]

    def setUp(self):
        self.payment_settings = patch.multiple(
            settings,
            ALIPAY_ENABLED=True,
            WECHAT_PAY_ENABLED=False,
            RECHARGE_USER_CNY_TO_USD_RATE=Decimal("5"),
            RECHARGE_IMAGE_CREDIT_USER_CNY_RATE=Decimal("5"),
            RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE=Decimal("7"),
            RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE=Decimal("7"),
        )
        self.payment_settings.start()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=self.TABLES)
        self.db = sessionmaker(bind=self.engine)()
        self._next_ids = {}

        def assign_sqlite_ids(session, _flush_context, _instances):
            for value in session.new:
                if not hasattr(value, "id") or value.id is not None:
                    continue
                model = type(value)
                next_id = self._next_ids.get(model, 1000)
                value.id = next_id
                self._next_ids[model] = next_id + 1

        self._id_listener = assign_sqlite_ids
        event.listen(self.db, "before_flush", self._id_listener)

        self.agent = _agent()
        self.user = SysUser(
            id=11,
            username="callback-user",
            email="callback-user@example.test",
            password_hash="hash",
            role="user",
            agent_id=7,
            status=1,
        )
        self.db.add_all([
            self.agent,
            self.user,
            UserBalance(user_id=11, balance=0, total_recharged=0, total_consumed=0),
            UserImageBalance(user_id=11, balance=0, total_recharged=0, total_consumed=0),
            AgentCashBalance(agent_id=7, balance=0, total_income=0, total_withdrawn=0, total_adjusted=0),
        ])
        self.db.commit()

    def tearDown(self):
        event.remove(self.db, "before_flush", self._id_listener)
        self.db.close()
        self.engine.dispose()
        self.payment_settings.stop()

    def _create_order(self, order_no, recharge_type, subscription_plan_id=None):
        with (
            patch.object(PaymentService, "_validate_payment_config", return_value=None),
            patch.object(PaymentService, "_generate_order_no", return_value=order_no),
            patch.object(
                PaymentService,
                "build_order_return_url",
                return_value=f"https://agent.example.test/user/recharge?order_no={order_no}",
            ),
            patch.object(
                PaymentService,
                "build_alipay_page_pay_url",
                return_value=f"https://pay.example.test/{order_no}",
            ),
        ):
            PaymentService.create_recharge_order(
                self.db,
                user=self.user,
                amount_cny=None if recharge_type == "subscription" else Decimal("100"),
                recharge_type=recharge_type,
                subscription_plan_id=subscription_plan_id,
            )
        return self.db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.order_no == order_no).one()

    def _apply_paid_order(self, order_no, trade_no):
        with (
            patch.object(
                AgentService,
                "resolve_user_recharge_policy",
                side_effect=AssertionError("paid callbacks must not resolve current pricing"),
            ),
            patch.object(PromotionService, "apply_recharge_reward", return_value=None),
        ):
            return PaymentService._apply_paid_order(
                self.db,
                order_no,
                {
                    "trade_status": "TRADE_SUCCESS",
                    "total_amount": "100.00",
                    "alipay_trade_no": trade_no,
                },
            )

    def _change_current_agent_pricing(self):
        self.agent.custom_recharge_rate_enabled = 0
        self.agent.custom_recharge_rate = Decimal("6")
        self.db.commit()

    def test_balance_callback_keeps_snapshot_and_cash_ledger_idempotent(self):
        order = self._create_order("CUSTOM-BALANCE-CALLBACK", "balance")
        self.assertEqual(Decimal("1.000000"), order.user_recharge_rate)
        self.assertEqual(Decimal("100.000000"), order.credited_usd)
        self.assertEqual(Decimal("85.71"), order.agent_income_cny)
        self._change_current_agent_pricing()

        paid = self._apply_paid_order(order.order_no, "TRADE-BALANCE-CALLBACK")
        duplicate = self._apply_paid_order(order.order_no, "TRADE-BALANCE-CALLBACK")

        balance = self.db.query(UserBalance).filter(UserBalance.user_id == self.user.id).one()
        cash = self.db.query(AgentCashBalance).filter(AgentCashBalance.agent_id == self.agent.id).one()
        ledger = self.db.query(AgentCashLedger).one()
        settlement = self.db.query(PaymentRechargeSettlement).one()
        self.assertEqual("paid", paid["status"])
        self.assertEqual("paid", duplicate["status"])
        self.assertEqual(Decimal("100.000000"), balance.balance)
        self.assertEqual(Decimal("100.000000"), balance.total_recharged)
        self.assertEqual(Decimal("85.71"), cash.balance)
        self.assertEqual(Decimal("85.71"), cash.total_income)
        self.assertEqual("balance_recharge_commission", ledger.action_type)
        self.assertEqual(Decimal("85.71"), ledger.change_amount)
        self.assertEqual("applied", settlement.status)
        self.assertEqual(1, self.db.query(ConsumptionRecord).count())
        self.assertEqual(1, self.db.query(AgentCashLedger).count())
        self.assertEqual(1, self.db.query(PaymentRechargeSettlement).count())

    def test_image_callback_uses_creation_snapshot_after_pricing_change(self):
        order = self._create_order("CUSTOM-IMAGE-CALLBACK", "image_credit")
        self.assertEqual(Decimal("1.000000"), order.user_recharge_rate)
        self.assertEqual(Decimal("100.000"), order.credited_image_credits)
        self.assertEqual(Decimal("7.000000"), order.agent_settlement_rate)
        self._change_current_agent_pricing()

        self._apply_paid_order(order.order_no, "TRADE-IMAGE-CALLBACK")

        balance = self.db.query(UserImageBalance).filter(UserImageBalance.user_id == self.user.id).one()
        record = self.db.query(ImageCreditRecord).one()
        cash = self.db.query(AgentCashBalance).filter(AgentCashBalance.agent_id == self.agent.id).one()
        ledger = self.db.query(AgentCashLedger).one()
        self.assertEqual(Decimal("100.000"), balance.balance)
        self.assertEqual(Decimal("100.000"), balance.total_recharged)
        self.assertEqual(Decimal("100.000"), record.change_amount)
        self.assertEqual("recharge", record.action_type)
        self.assertEqual(Decimal("85.71"), cash.balance)
        self.assertEqual("image_credit_recharge_commission", ledger.action_type)

    def test_pending_subscription_completes_after_custom_pricing_is_enabled(self):
        self.agent.custom_recharge_rate_enabled = 0
        self.db.add(SubscriptionPlan(
            id=30,
            plan_code="callback-monthly",
            plan_name="Callback Monthly",
            plan_kind="unlimited",
            duration_mode="month",
            duration_days=30,
            quota_metric=None,
            quota_value=0,
            reset_period="day",
            reset_timezone="Asia/Shanghai",
            sale_price_cny=Decimal("100"),
            agent_cost_price_cny=Decimal("70"),
            online_sale_enabled=1,
            sort_order=1,
            status="active",
        ))
        self.db.commit()
        order = self._create_order("PENDING-SUBSCRIPTION-CALLBACK", "subscription", subscription_plan_id=30)
        self.agent.custom_recharge_rate_enabled = 1
        self.agent.custom_recharge_rate = Decimal("1")
        self.db.commit()

        paid = self._apply_paid_order(order.order_no, "TRADE-SUBSCRIPTION-CALLBACK")

        subscription = self.db.query(UserSubscription).one()
        sale = self.db.query(AgentSubscriptionSaleRecord).one()
        self.db.refresh(self.user)
        self.assertEqual("paid", paid["status"])
        self.assertEqual(subscription.id, paid["subscription_id"])
        self.assertEqual(self.user.id, subscription.user_id)
        self.assertEqual(self.agent.id, subscription.agent_id)
        self.assertEqual("unlimited", self.user.subscription_type)
        self.assertEqual(order.order_no, sale.order_no)
        self.assertEqual(Decimal("30.00"), sale.agent_rebate_cny)

    def test_subscription_list_contract_is_empty_for_custom_pricing(self):
        with patch.object(SubscriptionService, "list_public_purchasable_plans") as list_plans:
            response = list_subscription_plans(
                db=self.db,
                current_user=self.user,
                agent_context=AgentSiteContext(
                    host="agent.example.test",
                    site_scope="agent",
                    is_api_host=False,
                    agent=self.agent,
                ),
            )

        self.assertEqual({"list": [], "total": 0}, response.data)
        list_plans.assert_not_called()


if __name__ == "__main__":
    unittest.main()
