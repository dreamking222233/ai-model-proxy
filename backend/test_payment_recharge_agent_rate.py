"""Regression tests for online recharge agent settlement rates."""
from decimal import Decimal
import unittest

from app.config import settings
from app.services.payment_service import PaymentService


class PaymentRechargeAgentRateTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
