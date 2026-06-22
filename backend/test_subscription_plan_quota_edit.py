import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.subscription_service import SubscriptionService


class SubscriptionPlanQuotaEditTest(unittest.TestCase):
    def _record(self, **overrides):
        data = {
            "plan_code": "daily-10m-token",
            "plan_code_snapshot": "daily-10m-token",
            "plan_name": "日度畅享包",
            "plan_kind": SubscriptionService.PLAN_KIND_DAILY_QUOTA,
            "plan_kind_snapshot": SubscriptionService.PLAN_KIND_DAILY_QUOTA,
            "quota_metric": SubscriptionService.QUOTA_METRIC_TOKENS,
            "quota_value": Decimal("10000000"),
            "created_at": datetime(2026, 6, 18, 15, 0, 0),
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    def test_builtin_enjoy_default_quota_keeps_cost_compatibility(self):
        strategy = SubscriptionService._resolve_plan_quota_strategy(self._record())

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_builtin_default_plan_snapshot_preserves_raw_quota(self):
        snapshot = SubscriptionService._get_plan_subscription_quota_snapshot(self._record())

        self.assertEqual(snapshot["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(snapshot["quota_limit"], Decimal("10000000"))

    def test_edited_token_quota_uses_saved_plan_value(self):
        strategy = SubscriptionService._resolve_plan_quota_strategy(
            self._record(quota_value=Decimal("20000000"))
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(strategy["quota_limit"], Decimal("20000000"))
        self.assertFalse(strategy["use_official_cost"])

    def test_edited_cost_quota_uses_saved_plan_value(self):
        strategy = SubscriptionService._resolve_plan_quota_strategy(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("80"),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("80"))
        self.assertFalse(strategy["use_official_cost"])

    def test_edited_cost_quota_50_snapshot_uses_saved_value(self):
        snapshot = SubscriptionService._get_plan_subscription_quota_snapshot(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
            )
        )
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                quota_metric=snapshot["quota_metric"],
                quota_value=snapshot["quota_limit"],
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_edited_cost_quota_60_snapshot_uses_saved_value(self):
        snapshot = SubscriptionService._get_plan_subscription_quota_snapshot(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("60"),
            )
        )
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                quota_metric=snapshot["quota_metric"],
                quota_value=snapshot["quota_limit"],
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("60"))
        self.assertFalse(strategy["use_official_cost"])

    def test_custom_template_named_enjoy_uses_saved_token_value(self):
        strategy = SubscriptionService._resolve_plan_quota_strategy(
            self._record(
                plan_code="vip-enjoy-token",
                plan_code_snapshot="vip-enjoy-token",
                plan_name="VIP畅享包",
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(strategy["quota_limit"], Decimal("10000000"))
        self.assertFalse(strategy["use_official_cost"])

    def test_custom_subscription_named_enjoy_uses_saved_token_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                plan_code="vip-enjoy-token",
                plan_code_snapshot="vip-enjoy-token",
                plan_name="VIP畅享包",
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(strategy["quota_limit"], Decimal("10000000"))
        self.assertFalse(strategy["use_official_cost"])

    def test_custom_subscription_named_enjoy_cost_50_uses_saved_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                plan_code="vip-enjoy-token",
                plan_code_snapshot="vip-enjoy-token",
                plan_name="VIP畅享包",
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_custom_subscription_without_code_named_enjoy_uses_saved_token_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                plan_code="",
                plan_code_snapshot=None,
                plan_name="VIP畅享包",
                created_at=datetime(2026, 6, 17, 23, 59, 59),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(strategy["quota_limit"], Decimal("10000000"))
        self.assertFalse(strategy["use_official_cost"])

    def test_custom_subscription_without_code_named_enjoy_cost_50_uses_saved_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                plan_code="",
                plan_code_snapshot=None,
                plan_name="VIP畅享包",
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
                created_at=datetime(2026, 6, 17, 23, 59, 59),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_edited_subscription_snapshot_uses_saved_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(quota_value=Decimal("20000000"))
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_TOKENS)
        self.assertEqual(strategy["quota_limit"], Decimal("20000000"))

    def test_legacy_cost_subscription_snapshot_uses_billable_cost(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
                created_at=datetime(2026, 6, 18, 13, 59, 59),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_legacy_cost_60_subscription_snapshot_uses_billable_cost(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("60"),
                created_at=datetime(2026, 6, 18, 13, 59, 59),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("60"))
        self.assertFalse(strategy["use_official_cost"])

    def test_cost_snapshot_at_cutover_uses_saved_value(self):
        strategy = SubscriptionService._resolve_subscription_quota_strategy(
            self._record(
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
                created_at=datetime(2026, 6, 18, 14, 0, 0),
            )
        )

        self.assertEqual(strategy["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(strategy["quota_limit"], Decimal("50"))
        self.assertFalse(strategy["use_official_cost"])

    def test_cost_quota_consumes_billable_total_cost_not_official_cost(self):
        subscription = self._record(
            plan_code="monthly-unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_kind=SubscriptionService.PLAN_KIND_UNLIMITED,
            plan_kind_snapshot=SubscriptionService.PLAN_KIND_UNLIMITED,
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_value=Decimal("100"),
        )

        consumed = SubscriptionService._get_quota_consumed_amount(
            subscription,
            raw_total_tokens=1000,
            total_cost=0.20,
            quota_cost=0.10,
        )

        self.assertEqual(consumed, Decimal("0.2"))

    def test_cost_quota_precheck_uses_billable_estimated_cost(self):
        subscription = self._record(
            plan_code="monthly-unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_kind=SubscriptionService.PLAN_KIND_UNLIMITED,
            plan_kind_snapshot=SubscriptionService.PLAN_KIND_UNLIMITED,
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_value=Decimal("100"),
        )

        consumed = SubscriptionService._get_estimated_quota_consumption(
            subscription,
            {
                "estimated_total_cost": Decimal("0.20"),
                "estimated_quota_cost": Decimal("0.10"),
            },
        )

        self.assertEqual(consumed, Decimal("0.20"))

    def test_summary_cycle_does_not_create_missing_cycle(self):
        class QueryStub:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return None

        class SessionStub:
            def __init__(self):
                self.begin_nested_called = False
                self.flush_called = False

            def query(self, *args, **kwargs):
                return QueryStub()

            def begin_nested(self):
                self.begin_nested_called = True
                raise AssertionError("summary should not create usage cycles")

            def flush(self):
                self.flush_called = True
                raise AssertionError("summary should not flush writes")

        db = SessionStub()
        now = datetime(2026, 6, 22, 10, 0, 0)
        subscription = self._record(
            id=19,
            user_id=2,
            status="active",
            start_time=datetime(2026, 6, 22, 9, 0, 0),
            end_time=datetime(2026, 6, 29, 9, 0, 0),
            reset_timezone="Asia/Shanghai",
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_value=Decimal("200"),
        )

        summary = SubscriptionService._get_cycle_for_summary(db, subscription, now)

        self.assertFalse(db.begin_nested_called)
        self.assertFalse(db.flush_called)
        self.assertIsNone(summary["id"])
        self.assertEqual(summary["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(summary["quota_limit"], 200.0)
        self.assertEqual(summary["used_amount"], 0.0)
        self.assertEqual(summary["remaining_amount"], 200.0)

    def test_plan_sort_update_does_not_default_purchase_fields(self):
        payload = SubscriptionService._validate_plan_payload({"sort_order": 30}, is_update=True)

        self.assertEqual(payload, {"sort_order": 30})


if __name__ == "__main__":
    unittest.main()
