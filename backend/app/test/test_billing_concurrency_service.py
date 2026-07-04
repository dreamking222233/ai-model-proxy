"""Tests for low-asset billing concurrency leases."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.exceptions import ServiceException
from app.services.billing_concurrency_service import BillingConcurrencyService


class FakeRedis:
    def __init__(self):
        self.zsets: dict[str, dict[str, int]] = {}
        self.expires: dict[str, int] = {}

    def eval(self, _script, _num_keys, key, member, now, expires_at, limit, key_ttl):
        bucket = self.zsets.setdefault(key, {})
        now = int(now)
        for existing_member, score in list(bucket.items()):
            if score <= now:
                del bucket[existing_member]
        current = len(bucket)
        if current >= int(limit):
            return [0, current]
        bucket[str(member)] = int(expires_at)
        self.expires[key] = int(key_ttl)
        return [1, current + 1]

    def zrem(self, key, member):
        bucket = self.zsets.setdefault(key, {})
        return 1 if bucket.pop(str(member), None) is not None else 0


class BillingConcurrencyServiceTest(unittest.TestCase):
    def test_acquire_limits_fourth_request(self):
        fake = FakeRedis()
        with patch("app.services.billing_concurrency_service.redis_client.client", fake):
            leases = [
                BillingConcurrencyService.acquire(user_id=1, request_id=f"req-{i}", limit=3, ttl_seconds=60)
                for i in range(3)
            ]
            self.assertEqual(len(leases), 3)
            with self.assertRaises(ServiceException) as ctx:
                BillingConcurrencyService.acquire(user_id=1, request_id="req-4", limit=3, ttl_seconds=60)
            self.assertEqual(ctx.exception.error_code, "BILLING_CONCURRENCY_LIMITED")

    def test_release_allows_new_request(self):
        fake = FakeRedis()
        with patch("app.services.billing_concurrency_service.redis_client.client", fake):
            leases = [
                BillingConcurrencyService.acquire(user_id=2, request_id=f"req-{i}", limit=3, ttl_seconds=60)
                for i in range(3)
            ]
            BillingConcurrencyService.release(leases[0])
            lease = BillingConcurrencyService.acquire(user_id=2, request_id="req-new", limit=3, ttl_seconds=60)
            self.assertEqual(lease.request_id, "req-new")

    def test_expired_leases_are_cleaned(self):
        fake = FakeRedis()
        with (
            patch("app.services.billing_concurrency_service.redis_client.client", fake),
            patch("app.services.billing_concurrency_service.time.time", return_value=1000),
        ):
            BillingConcurrencyService.acquire(user_id=3, request_id="old", limit=1, ttl_seconds=30)
        with (
            patch("app.services.billing_concurrency_service.redis_client.client", fake),
            patch("app.services.billing_concurrency_service.time.time", return_value=1031),
        ):
            lease = BillingConcurrencyService.acquire(user_id=3, request_id="new", limit=1, ttl_seconds=30)
            self.assertEqual(lease.request_id, "new")

    def test_redis_unavailable_fails_closed(self):
        with patch("app.services.billing_concurrency_service.redis_client.client", None):
            with self.assertRaises(ServiceException) as ctx:
                BillingConcurrencyService.acquire(user_id=4, request_id="req", limit=3, ttl_seconds=60)
            self.assertEqual(ctx.exception.error_code, "BILLING_CONCURRENCY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
