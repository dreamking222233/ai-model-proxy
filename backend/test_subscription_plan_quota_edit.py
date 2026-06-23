import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.log import ConsumptionRecord, SubscriptionUsageCycle, UserSubscription
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

    def test_cycle_window_uses_subscription_start_time(self):
        subscription = self._record(
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 25, 16, 30, 31),
        )

        cycle_date, cycle_start, cycle_end = SubscriptionService._get_subscription_cycle_window(
            subscription,
            datetime(2026, 6, 24, 23, 59, 59),
        )

        self.assertEqual(cycle_date.isoformat(), "2026-06-24")
        self.assertEqual(cycle_start, datetime(2026, 6, 24, 16, 30, 31))
        self.assertEqual(cycle_end, datetime(2026, 6, 25, 16, 30, 31))

    def test_midnight_does_not_refresh_quota_cycle(self):
        subscription = self._record(
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 25, 16, 30, 31),
        )

        cycle_date, cycle_start, cycle_end = SubscriptionService._get_subscription_cycle_window(
            subscription,
            datetime(2026, 6, 25, 0, 1, 0),
        )

        self.assertEqual(cycle_date.isoformat(), "2026-06-24")
        self.assertEqual(cycle_start, datetime(2026, 6, 24, 16, 30, 31))
        self.assertEqual(cycle_end, datetime(2026, 6, 25, 16, 30, 31))

    def test_cycle_refreshes_after_24_hours_for_multi_day_plan(self):
        subscription = self._record(
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 26, 16, 30, 31),
        )

        cycle_date, cycle_start, cycle_end = SubscriptionService._get_subscription_cycle_window(
            subscription,
            datetime(2026, 6, 25, 16, 30, 31),
        )

        self.assertEqual(cycle_date.isoformat(), "2026-06-25")
        self.assertEqual(cycle_start, datetime(2026, 6, 25, 16, 30, 31))
        self.assertEqual(cycle_end, datetime(2026, 6, 26, 16, 30, 31))

    def test_one_day_card_expiry_boundary_does_not_create_extra_cycle(self):
        subscription = self._record(
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 25, 16, 30, 31),
        )

        cycle_date, cycle_start, cycle_end = SubscriptionService._get_subscription_cycle_window(
            subscription,
            datetime(2026, 6, 25, 16, 30, 31),
        )

        self.assertEqual(cycle_date.isoformat(), "2026-06-24")
        self.assertEqual(cycle_start, datetime(2026, 6, 24, 16, 30, 31))
        self.assertEqual(cycle_end, datetime(2026, 6, 25, 16, 30, 31))

    def test_cycle_sync_rebuilds_legacy_midnight_window(self):
        cycle = SimpleNamespace(
            cycle_start_at=datetime(2026, 6, 24, 0, 0, 0),
            cycle_end_at=datetime(2026, 6, 25, 0, 0, 0),
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_limit=Decimal("50"),
            used_amount=Decimal("0"),
            request_count=0,
            last_request_id=None,
        )
        subscription = self._record(
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 25, 16, 30, 31),
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_value=Decimal("50"),
        )

        with patch.object(
            SubscriptionService,
            "_rebuild_cycle_usage_snapshot",
            return_value={
                "used_amount": Decimal("20"),
                "request_count": 2,
                "last_request_id": "req-last",
            },
        ) as rebuild_mock:
            synced = SubscriptionService._sync_cycle_snapshot(
                SimpleNamespace(),
                subscription,
                cycle,
                datetime(2026, 6, 24, 16, 30, 31),
                datetime(2026, 6, 25, 16, 30, 31),
                SubscriptionService.QUOTA_METRIC_COST,
                Decimal("50"),
            )

        rebuild_mock.assert_called_once()
        self.assertIs(synced, cycle)
        self.assertEqual(cycle.cycle_start_at, datetime(2026, 6, 24, 16, 30, 31))
        self.assertEqual(cycle.cycle_end_at, datetime(2026, 6, 25, 16, 30, 31))
        self.assertEqual(cycle.used_amount, Decimal("20"))
        self.assertEqual(cycle.request_count, 2)
        self.assertEqual(cycle.last_request_id, "req-last")

    def test_new_cycle_initializes_from_existing_consumption_snapshot(self):
        class QueryStub:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                return None

        class SavepointStub:
            def commit(self):
                pass

            def rollback(self):
                pass

        class SessionStub:
            def __init__(self):
                self.added = None
                self.flushed = False

            def query(self, *args, **kwargs):
                return QueryStub()

            def begin_nested(self):
                return SavepointStub()

            def add(self, value):
                self.added = value

            def flush(self):
                self.flushed = True

        subscription = self._record(
            id=90,
            user_id=7,
            start_time=datetime(2026, 6, 24, 16, 30, 31),
            end_time=datetime(2026, 6, 26, 16, 30, 31),
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_value=Decimal("50"),
        )
        db = SessionStub()

        with patch.object(
            SubscriptionService,
            "_rebuild_cycle_usage_snapshot",
            return_value={
                "used_amount": Decimal("18.5"),
                "request_count": 3,
                "last_request_id": "req-3",
            },
        ) as rebuild_mock:
            cycle = SubscriptionService._get_or_create_cycle(
                db,
                subscription,
                datetime(2026, 6, 25, 0, 1, 0),
            )

        rebuild_mock.assert_called_once()
        self.assertTrue(db.flushed)
        self.assertIs(cycle, db.added)
        self.assertEqual(cycle.cycle_date.isoformat(), "2026-06-24")
        self.assertEqual(cycle.cycle_start_at, datetime(2026, 6, 24, 16, 30, 31))
        self.assertEqual(cycle.cycle_end_at, datetime(2026, 6, 25, 16, 30, 31))
        self.assertEqual(cycle.used_amount, Decimal("18.5"))
        self.assertEqual(cycle.request_count, 3)
        self.assertEqual(cycle.last_request_id, "req-3")

    def test_orm_rebuilds_legacy_midnight_cycles_by_rolling_window(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                UserSubscription.__table__,
                SubscriptionUsageCycle.__table__,
                ConsumptionRecord.__table__,
            ],
        )
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            subscription = UserSubscription(
                id=90,
                user_id=7,
                plan_name="两日尊享包",
                plan_type="custom",
                plan_kind_snapshot=SubscriptionService.PLAN_KIND_DAILY_QUOTA,
                quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                quota_value=Decimal("50"),
                reset_period="day",
                reset_timezone="Asia/Shanghai",
                start_time=datetime(2026, 6, 24, 16, 30, 31),
                end_time=datetime(2026, 6, 26, 16, 30, 31),
                status="active",
            )
            db.add(subscription)
            db.add_all(
                [
                    SubscriptionUsageCycle(
                        id=101,
                        subscription_id=subscription.id,
                        user_id=subscription.user_id,
                        cycle_date=datetime(2026, 6, 24).date(),
                        cycle_start_at=datetime(2026, 6, 24, 0, 0, 0),
                        cycle_end_at=datetime(2026, 6, 25, 0, 0, 0),
                        quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                        quota_limit=Decimal("50"),
                        used_amount=Decimal("8"),
                        request_count=1,
                        last_request_id="req-1",
                    ),
                    SubscriptionUsageCycle(
                        id=102,
                        subscription_id=subscription.id,
                        user_id=subscription.user_id,
                        cycle_date=datetime(2026, 6, 25).date(),
                        cycle_start_at=datetime(2026, 6, 25, 0, 0, 0),
                        cycle_end_at=datetime(2026, 6, 26, 0, 0, 0),
                        quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                        quota_limit=Decimal("50"),
                        used_amount=Decimal("9"),
                        request_count=1,
                        last_request_id="req-2",
                    ),
                ]
            )
            db.add_all(
                [
                    ConsumptionRecord(
                        user_id=subscription.user_id,
                        request_id="req-1",
                        model_name="gpt-test",
                        total_cost=Decimal("8"),
                        billing_mode="subscription",
                        subscription_id=subscription.id,
                        subscription_cycle_id=101,
                        quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                        quota_consumed_amount=Decimal("8"),
                        quota_limit_snapshot=Decimal("50"),
                        quota_used_after=Decimal("8"),
                        quota_cycle_date=datetime(2026, 6, 24).date(),
                        created_at=datetime(2026, 6, 24, 17, 0, 0),
                    ),
                    ConsumptionRecord(
                        user_id=subscription.user_id,
                        request_id="req-2",
                        model_name="gpt-test",
                        total_cost=Decimal("9"),
                        billing_mode="subscription",
                        subscription_id=subscription.id,
                        subscription_cycle_id=102,
                        quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                        quota_consumed_amount=Decimal("9"),
                        quota_limit_snapshot=Decimal("50"),
                        quota_used_after=Decimal("9"),
                        quota_cycle_date=datetime(2026, 6, 25).date(),
                        created_at=datetime(2026, 6, 25, 0, 10, 0),
                    ),
                    ConsumptionRecord(
                        user_id=subscription.user_id,
                        request_id="req-3",
                        model_name="gpt-test",
                        total_cost=Decimal("11"),
                        billing_mode="subscription",
                        subscription_id=subscription.id,
                        subscription_cycle_id=102,
                        quota_metric=SubscriptionService.QUOTA_METRIC_COST,
                        quota_consumed_amount=Decimal("11"),
                        quota_limit_snapshot=Decimal("50"),
                        quota_used_after=Decimal("11"),
                        quota_cycle_date=datetime(2026, 6, 25).date(),
                        created_at=datetime(2026, 6, 25, 17, 0, 0),
                    ),
                ]
            )
            db.commit()

            first_cycle = SubscriptionService._get_or_create_cycle(
                db,
                subscription,
                datetime(2026, 6, 25, 0, 20, 0),
            )

            self.assertEqual(first_cycle.id, 101)
            self.assertEqual(first_cycle.cycle_start_at, datetime(2026, 6, 24, 16, 30, 31))
            self.assertEqual(first_cycle.cycle_end_at, datetime(2026, 6, 25, 16, 30, 31))
            self.assertEqual(first_cycle.used_amount, Decimal("17.000000"))
            self.assertEqual(first_cycle.request_count, 2)
            self.assertEqual(first_cycle.last_request_id, "req-2")

            second_cycle = SubscriptionService._get_or_create_cycle(
                db,
                subscription,
                datetime(2026, 6, 25, 16, 31, 0),
            )

            self.assertEqual(second_cycle.id, 102)
            self.assertEqual(second_cycle.cycle_start_at, datetime(2026, 6, 25, 16, 30, 31))
            self.assertEqual(second_cycle.cycle_end_at, datetime(2026, 6, 26, 16, 30, 31))
            self.assertEqual(second_cycle.used_amount, Decimal("11.000000"))
            self.assertEqual(second_cycle.request_count, 1)
            self.assertEqual(second_cycle.last_request_id, "req-3")
        finally:
            db.close()
            engine.dispose()

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

        with patch.object(
            SubscriptionService,
            "_rebuild_cycle_usage_snapshot",
            return_value={
                "used_amount": Decimal("0"),
                "request_count": 0,
                "last_request_id": None,
            },
        ):
            summary = SubscriptionService._get_cycle_for_summary(db, subscription, now)

        self.assertFalse(db.begin_nested_called)
        self.assertFalse(db.flush_called)
        self.assertIsNone(summary["id"])
        self.assertEqual(summary["quota_metric"], SubscriptionService.QUOTA_METRIC_COST)
        self.assertEqual(summary["quota_limit"], 200.0)
        self.assertEqual(summary["used_amount"], 0.0)
        self.assertEqual(summary["remaining_amount"], 200.0)
        self.assertEqual(summary["cycle_start_at"], "2026-06-22T09:00:00+08:00")
        self.assertEqual(summary["cycle_end_at"], "2026-06-23T09:00:00+08:00")
        self.assertEqual(summary["next_refresh_at"], "2026-06-23T09:00:00+08:00")

    def test_plan_sort_update_does_not_default_purchase_fields(self):
        payload = SubscriptionService._validate_plan_payload({"sort_order": 30}, is_update=True)

        self.assertEqual(payload, {"sort_order": 30})


if __name__ == "__main__":
    unittest.main()
