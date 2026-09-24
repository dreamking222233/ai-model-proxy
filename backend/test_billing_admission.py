import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.services.log_service import LogService
from app.services.proxy_service import ProxyService


class BillingAdmissionTest(unittest.TestCase):
    def _balance(self, amount):
        return SimpleNamespace(balance=Decimal(str(amount)), total_consumed=Decimal("0"))

    def test_positive_balance_is_admitted_without_estimate_based_rejection(self):
        with patch.object(
            ProxyService,
            "_get_balance_record",
            return_value=self._balance("25.97"),
        ):
            self.assertTrue(
                ProxyService._can_balance_cover_text_precheck(
                    object(),
                    2653,
                    {"estimated_total_cost": Decimal("300")},
                )
            )
            self.assertTrue(
                ProxyService._can_fallback_to_balance_for_quota_precheck(
                    object(),
                    2653,
                    {"estimated_total_cost": Decimal("300")},
                )
            )

    def test_empty_balance_is_rejected_at_admission(self):
        with patch.object(
            ProxyService,
            "_get_balance_record",
            return_value=self._balance("0"),
        ):
            self.assertFalse(
                ProxyService._can_balance_cover_text_precheck(
                    object(),
                    2653,
                    {"estimated_total_cost": Decimal("0.01")},
                )
            )

    def test_zero_cost_request_does_not_require_balance(self):
        with patch.object(
            ProxyService,
            "_get_balance_record",
            return_value=self._balance("0"),
        ):
            self.assertTrue(
                ProxyService._can_balance_cover_text_precheck(
                    object(),
                    2653,
                    {"estimated_total_cost": Decimal("0")},
                )
            )
            self.assertTrue(
                ProxyService._can_fallback_to_balance_for_quota_precheck(
                    object(),
                    2653,
                    {"estimated_total_cost": Decimal("0")},
                )
            )

    def test_low_asset_threshold_is_three_and_exact_threshold_is_not_limited(self):
        with patch("app.services.proxy_service.get_system_config", return_value=3):
            self.assertEqual(
                ProxyService._billing_low_asset_threshold(object()),
                Decimal("3"),
            )
            with patch.object(
                ProxyService,
                "_get_balance_record",
                return_value=self._balance("3"),
            ):
                decision = ProxyService._build_billing_admission_decision(
                    object(),
                    2653,
                    active_subscription=None,
                )
            self.assertFalse(decision.limited)
            self.assertEqual(decision.reason, "balance_sufficient")

    def test_completed_request_is_charged_into_debt_then_new_request_is_rejected(self):
        balance = self._balance("0.003771")
        before, after = ProxyService._charge_balance_after_request(balance, Decimal("0.260319"))
        self.assertEqual(before, 0.003771)
        self.assertEqual(after, -0.256548)
        self.assertEqual(balance.total_consumed, Decimal("0.260319"))
        with patch.object(ProxyService, "_get_balance_record", return_value=balance):
            self.assertFalse(
                ProxyService._can_balance_cover_text_precheck(
                    object(), 2598, {"estimated_total_cost": Decimal("0.01")}
                )
            )

    def test_historical_accounting_failure_displays_cache_in_total(self):
        log = SimpleNamespace(
            status="error",
            error_message="本地计费或记账失败：[INSUFFICIENT_BALANCE] 余额不足",
            input_tokens=1779,
            output_tokens=245,
            total_tokens=2024,
            raw_input_tokens=1779,
            raw_output_tokens=245,
            raw_total_tokens=2024,
            upstream_cache_read_input_tokens=141056,
        )
        accounting_failed = LogService._is_accounting_failure_after_success(
            log.status, log.error_message, log.total_tokens
        )
        self.assertTrue(accounting_failed)
        self.assertEqual(LogService._visible_token_totals(log, accounting_failed), (143080, 143080))


if __name__ == "__main__":
    unittest.main()
