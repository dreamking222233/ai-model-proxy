import unittest
from decimal import Decimal
from unittest.mock import patch

from app.models.model import UnifiedModel
from app.services.model_service import ModelService
from app.services.proxy_service import ProxyService


class FakeDb:
    pass


class LongContextBillingTest(unittest.TestCase):
    def test_context_multiplier_respects_model_switch(self):
        enabled_model = UnifiedModel(model_name="gpt-test", long_context_billing_enabled=1)
        disabled_model = UnifiedModel(model_name="claude-test", long_context_billing_enabled=0)

        over_threshold = ProxyService._LONG_CONTEXT_TOKEN_THRESHOLD + 1

        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(over_threshold, enabled_model),
            Decimal("2"),
        )
        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(over_threshold, disabled_model),
            Decimal("1"),
        )

    def test_gpt_defaults_to_long_context_billing_enabled(self):
        self.assertEqual(
            ModelService._normalize_long_context_billing_enabled(None, "gpt", "gpt-test"),
            1,
        )
        self.assertEqual(
            ModelService._normalize_long_context_billing_enabled(None, "claude", "claude-test"),
            0,
        )

    def test_request_precheck_respects_disabled_model_switch_without_output_limit(self):
        model = UnifiedModel(
            model_name="claude-request",
            model_type="chat",
            model_series="claude",
            billing_type="request",
            request_price=Decimal("0.25"),
            long_context_billing_enabled=0,
        )
        request_data = {
            "model": "claude-request",
            "messages": [{"role": "user", "content": "hello"}],
        }

        with (
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch("app.services.proxy_service.PriceAdjustmentService.resolve_multiplier", return_value=Decimal("1")),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                FakeDb(),
                "openai",
                request_data,
                model,
            )

        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("1"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.25"))

    def test_request_precheck_keeps_conservative_multiplier_when_model_switch_enabled(self):
        model = UnifiedModel(
            model_name="gpt-request",
            model_type="chat",
            model_series="gpt",
            billing_type="request",
            request_price=Decimal("0.25"),
            long_context_billing_enabled=1,
        )
        request_data = {
            "model": "gpt-request",
            "messages": [{"role": "user", "content": "hello"}],
        }

        with (
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch("app.services.proxy_service.PriceAdjustmentService.resolve_multiplier", return_value=Decimal("1")),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                FakeDb(),
                "openai",
                request_data,
                model,
            )

        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.50"))


if __name__ == "__main__":
    unittest.main()
