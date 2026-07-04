"""Tests for billing admission concurrency decisions."""
from __future__ import annotations

import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.responses import StreamingResponse

from app.core.exceptions import ServiceException
from app.services.billing_concurrency_service import BillingAdmissionDecision
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService


class FakeRedis:
    def __init__(self):
        self.zsets: dict[str, dict[str, int]] = {}

    def eval(self, _script, _num_keys, key, member, now, expires_at, limit, _key_ttl):
        bucket = self.zsets.setdefault(key, {})
        now = int(now)
        for existing_member, score in list(bucket.items()):
            if score <= now:
                del bucket[existing_member]
        current = len(bucket)
        if current >= int(limit):
            return [0, current]
        bucket[str(member)] = int(expires_at)
        return [1, current + 1]

    def zrem(self, key, member):
        bucket = self.zsets.setdefault(key, {})
        return 1 if bucket.pop(str(member), None) is not None else 0


class BillingAdmissionDecisionTest(unittest.TestCase):
    def _decision(
        self,
        *,
        balance: Decimal,
        subscription=None,
        quota_metric=None,
        quota_remaining=None,
    ):
        with (
            patch.object(ProxyService, "_get_balance_record", return_value=SimpleNamespace(balance=balance)),
            patch.object(ProxyService, "_billing_low_asset_threshold", return_value=Decimal("2")),
            patch.object(ProxyService, "_billing_low_asset_concurrency_limit", return_value=3),
            patch.object(ProxyService, "_get_subscription_quota_remaining", return_value=(quota_metric, quota_remaining)),
        ):
            return ProxyService._build_billing_admission_decision(
                SimpleNamespace(),
                1001,
                active_subscription=subscription,
            )

    def test_no_subscription_is_limited_even_with_balance(self):
        decision = self._decision(balance=Decimal("100"))
        self.assertTrue(decision.limited)
        self.assertEqual(decision.reason, "no_subscription")
        self.assertEqual(decision.limit, 3)

    def test_cost_quota_above_threshold_is_not_limited(self):
        subscription = SimpleNamespace(id=10)
        decision = self._decision(
            balance=Decimal("0"),
            subscription=subscription,
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_remaining=Decimal("2.50"),
        )
        self.assertFalse(decision.limited)
        self.assertEqual(decision.reason, "quota_sufficient")

    def test_low_cost_quota_with_balance_above_threshold_is_not_limited(self):
        subscription = SimpleNamespace(id=11)
        decision = self._decision(
            balance=Decimal("2.01"),
            subscription=subscription,
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_remaining=Decimal("1.50"),
        )
        self.assertFalse(decision.limited)
        self.assertEqual(decision.reason, "balance_sufficient")

    def test_low_cost_quota_without_balance_is_limited(self):
        subscription = SimpleNamespace(id=12)
        decision = self._decision(
            balance=Decimal("0"),
            subscription=subscription,
            quota_metric=SubscriptionService.QUOTA_METRIC_COST,
            quota_remaining=Decimal("1.50"),
        )
        self.assertTrue(decision.limited)
        self.assertEqual(decision.reason, "low_quota_no_balance")

    def test_low_balance_is_limited(self):
        subscription = SimpleNamespace(id=13)
        decision = self._decision(
            balance=Decimal("1.99"),
            subscription=subscription,
            quota_metric=SubscriptionService.QUOTA_METRIC_TOKENS,
            quota_remaining=Decimal("100000"),
        )
        self.assertTrue(decision.limited)
        self.assertEqual(decision.reason, "low_balance")

    def test_token_quota_is_not_treated_as_two_usd_threshold(self):
        subscription = SimpleNamespace(id=14)
        decision = self._decision(
            balance=Decimal("2.01"),
            subscription=subscription,
            quota_metric=SubscriptionService.QUOTA_METRIC_TOKENS,
            quota_remaining=Decimal("1"),
        )
        self.assertFalse(decision.limited)
        self.assertEqual(decision.reason, "balance_sufficient")


class BillingConcurrencyProxyIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_limited_fourth_request_does_not_call_producer(self):
        fake = FakeRedis()
        decision = BillingAdmissionDecision(user_id=2001, limited=True, limit=3, reason="low_balance")
        key = "billing_concurrency:user:2001"
        fake.zsets[key] = {
            "req-1": 9999999999,
            "req-2": 9999999999,
            "req-3": 9999999999,
        }
        called = False

        async def producer():
            nonlocal called
            called = True
            return SimpleNamespace()

        with (
            patch("app.services.billing_concurrency_service.redis_client.client", fake),
            patch.object(ProxyService, "_billing_concurrency_lease_ttl_seconds", return_value=60),
        ):
            with self.assertRaises(ServiceException) as ctx:
                await ProxyService._run_with_billing_concurrency(
                    SimpleNamespace(),
                    decision,
                    "req-4",
                    producer,
                )
        self.assertEqual(ctx.exception.error_code, "BILLING_CONCURRENCY_LIMITED")
        self.assertFalse(called)

    async def test_streaming_response_releases_lease_after_iteration(self):
        fake = FakeRedis()
        decision = BillingAdmissionDecision(user_id=2002, limited=True, limit=3, reason="low_balance")

        async def body():
            yield b"data: hello\n\n"

        async def producer():
            return StreamingResponse(body(), media_type="text/event-stream")

        with (
            patch("app.services.billing_concurrency_service.redis_client.client", fake),
            patch.object(ProxyService, "_billing_concurrency_lease_ttl_seconds", return_value=60),
        ):
            response = await ProxyService._run_with_billing_concurrency(
                SimpleNamespace(),
                decision,
                "stream-1",
                producer,
            )
            self.assertTrue(fake.zsets["billing_concurrency:user:2002"])
            chunks = [chunk async for chunk in response.body_iterator]

        self.assertEqual(chunks, [b"data: hello\n\n"])
        self.assertEqual(fake.zsets["billing_concurrency:user:2002"], {})


if __name__ == "__main__":
    unittest.main()
