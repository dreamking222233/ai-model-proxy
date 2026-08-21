import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.core.exceptions import ServiceException
from app.schemas.payment import UserRechargeOrderCreateRequest
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService


class UserSubscriptionPurchaseTest(unittest.TestCase):
    def test_subscription_order_requires_plan_id_and_ignores_amount(self):
        payload = UserRechargeOrderCreateRequest(
            recharge_type="subscription",
            subscription_plan_id=12,
            amount_cny=Decimal("0.01"),
        )

        self.assertEqual(payload.recharge_type, "subscription")
        self.assertEqual(payload.subscription_plan_id, 12)

        with self.assertRaises(ValidationError):
            UserRechargeOrderCreateRequest(recharge_type="subscription")

    def test_balance_order_requires_amount(self):
        with self.assertRaises(ValidationError):
            UserRechargeOrderCreateRequest(recharge_type="balance")

        with self.assertRaises(ValidationError):
            UserRechargeOrderCreateRequest(recharge_type="image_credit", amount_cny=Decimal("0.50"))

    def test_online_sale_plan_price_validation(self):
        payload = SubscriptionService._validate_plan_payload({
            "plan_code": "monthly-vip",
            "plan_name": "至尊包月",
            "plan_kind": SubscriptionService.PLAN_KIND_UNLIMITED,
            "duration_days": 30,
            "sale_price_cny": Decimal("450"),
            "agent_cost_price_cny": Decimal("360"),
            "online_sale_enabled": 1,
        })

        self.assertEqual(payload["sale_price_cny"], Decimal("450"))
        self.assertEqual(payload["agent_cost_price_cny"], Decimal("360"))
        self.assertEqual(payload["online_sale_enabled"], 1)

    def test_online_sale_requires_valid_price(self):
        with self.assertRaises(ServiceException):
            SubscriptionService._validate_plan_payload({
                "plan_code": "bad-price",
                "plan_name": "错误售价",
                "plan_kind": SubscriptionService.PLAN_KIND_UNLIMITED,
                "duration_days": 30,
                "sale_price_cny": Decimal("0"),
                "agent_cost_price_cny": Decimal("0"),
                "online_sale_enabled": 1,
            })

        with self.assertRaises(ServiceException):
            SubscriptionService._validate_plan_payload({
                "plan_code": "bad-agent-cost",
                "plan_name": "错误拿货价",
                "plan_kind": SubscriptionService.PLAN_KIND_UNLIMITED,
                "duration_days": 30,
                "sale_price_cny": Decimal("100"),
                "agent_cost_price_cny": Decimal("120"),
                "online_sale_enabled": 1,
            })

    def test_subscription_asset_credit_routes_to_subscription_activation(self):
        order = SimpleNamespace(recharge_type="subscription")

        with (
            patch.object(PaymentService, "_activate_subscription_order") as activate_mock,
            patch.object(PaymentService, "_credit_user_balance") as balance_mock,
            patch.object(PaymentService, "_credit_user_image_credits") as image_mock,
        ):
            PaymentService._credit_user_order_asset(SimpleNamespace(), order)

        activate_mock.assert_called_once()
        balance_mock.assert_not_called()
        image_mock.assert_not_called()

    def test_subscription_activation_uses_append_and_creates_agent_sale_record(self):
        order = SimpleNamespace(
            user_id=10,
            agent_id=20,
            subscription_plan_id=30,
            subscription_id=None,
        )

        with (
            patch(
                "app.services.payment_service.SubscriptionService.activate_plan_subscription",
                return_value={"id": 88},
            ) as activate_mock,
            patch(
                "app.services.agent_subscription_sale_service.AgentSubscriptionSaleService.create_from_paid_order",
            ) as sale_mock,
        ):
            PaymentService._activate_subscription_order(SimpleNamespace(), order)

        activate_mock.assert_called_once()
        kwargs = activate_mock.call_args.kwargs
        self.assertEqual(kwargs["user_id"], 10)
        self.assertEqual(kwargs["plan_id"], 30)
        self.assertIsNone(kwargs["operator_id"])
        self.assertEqual(kwargs["activation_mode"], "append")
        self.assertFalse(kwargs["auto_commit"])
        self.assertEqual(kwargs["agent_id"], 20)
        self.assertEqual(order.subscription_id, 88)
        sale_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
