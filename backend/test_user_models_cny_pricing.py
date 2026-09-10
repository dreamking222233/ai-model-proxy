"""Regression tests for the conditional RMB model price hint."""

from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.api.user.models import _cny_pricing_context
from app.config import settings
from app.models.agent import Agent


class _AgentDb:
    def __init__(self, agent):
        self.agent = agent

    def query(self, _model):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.agent


class UserModelsCnyPricingTest(unittest.TestCase):
    def _context(self, *, online=True, rate="5"):
        policy = SimpleNamespace(
            online_recharge_enabled=online,
            balance_recharge_rate=Decimal(rate),
        )
        return patch(
            "app.api.user.models.AgentService.resolve_user_recharge_policy",
            return_value=policy,
        )

    def test_standard_online_recharge_rate_enables_hint(self):
        with self._context():
            self.assertEqual(
                {"cny_price_enabled": True, "cny_price_rate": 5},
                _cny_pricing_context(object(), SimpleNamespace(agent_id=None)),
            )

    def test_disabled_online_recharge_hides_hint(self):
        with self._context(online=False):
            self.assertEqual(
                {"cny_price_enabled": False, "cny_price_rate": None},
                _cny_pricing_context(object(), SimpleNamespace(agent_id=7)),
            )

    def test_nonstandard_recharge_rate_hides_hint(self):
        with self._context(rate="3"):
            self.assertEqual(
                {"cny_price_enabled": False, "cny_price_rate": None},
                _cny_pricing_context(object(), SimpleNamespace(agent_id=7)),
            )

    def test_real_agent_policy_honors_online_switch_and_custom_rate(self):
        with patch.multiple(
            settings,
            ALIPAY_ENABLED=True,
            WECHAT_PAY_ENABLED=False,
            RECHARGE_USER_CNY_TO_USD_RATE=Decimal("5"),
            RECHARGE_IMAGE_CREDIT_USER_CNY_RATE=Decimal("5"),
            RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE=Decimal("7"),
            RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE=Decimal("7"),
        ):
            standard_agent = Agent(
                id=7,
                status="active",
                online_recharge_enabled=1,
                custom_recharge_rate_enabled=0,
                custom_recharge_rate=Decimal("5"),
            )
            self.assertEqual(
                {"cny_price_enabled": True, "cny_price_rate": 5},
                _cny_pricing_context(_AgentDb(standard_agent), SimpleNamespace(agent_id=7)),
            )

            custom_agent = Agent(
                id=7,
                status="active",
                online_recharge_enabled=1,
                custom_recharge_rate_enabled=1,
                custom_recharge_rate=Decimal("3"),
            )
            self.assertEqual(
                {"cny_price_enabled": False, "cny_price_rate": None},
                _cny_pricing_context(_AgentDb(custom_agent), SimpleNamespace(agent_id=7)),
            )

            disabled_agent = Agent(
                id=7,
                status="active",
                online_recharge_enabled=0,
                custom_recharge_rate_enabled=0,
                custom_recharge_rate=Decimal("5"),
            )
            self.assertEqual(
                {"cny_price_enabled": False, "cny_price_rate": None},
                _cny_pricing_context(_AgentDb(disabled_agent), SimpleNamespace(agent_id=7)),
            )


if __name__ == "__main__":
    unittest.main()
