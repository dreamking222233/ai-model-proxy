import unittest
from decimal import Decimal
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
from app.core.dependencies import verify_api_key_from_headers
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService


class ProxySubscriptionCompatibilityTest(unittest.TestCase):
    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_stale_balance_user_with_active_unlimited_subscription_is_allowed(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        db = MagicMock()
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="unlimited")

        ProxyService._assert_text_request_allowed(db, user)

        mock_refresh.assert_called_once()
        mock_check_quota.assert_not_called()
        db.query.assert_not_called()

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_stale_balance_user_with_active_quota_subscription_checks_quota(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        db = MagicMock()
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="daily_quota")

        ProxyService._assert_text_request_allowed(db, user)

        mock_check_quota.assert_called_once_with(db, user, quota_precheck=None)

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_expired_subscription_without_balance_raises_subscription_expired(self, _mock_refresh):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(
            id=1,
            subscription_type="unlimited",
            subscription_expires_at=datetime.utcnow() - timedelta(days=1),
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(db, user)

        self.assertEqual(ctx.exception.error_code, "SUBSCRIPTION_EXPIRED")

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_balance_user_without_balance_raises_insufficient_balance(self, _mock_refresh):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(db, user)

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")


class SubscriptionStatusCompatibilityTest(unittest.TestCase):
    def test_null_status_future_subscription_is_treated_as_active(self):
        subscription = SimpleNamespace(
            status=None,
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(days=1),
        )

        self.assertEqual(SubscriptionService._normalized_subscription_status(subscription), "active")
        self.assertTrue(SubscriptionService._is_effectively_active(subscription))

    def test_null_status_past_subscription_is_treated_as_expired(self):
        subscription = SimpleNamespace(
            status=None,
            start_time=datetime.utcnow() - timedelta(days=2),
            end_time=datetime.utcnow() - timedelta(minutes=1),
        )

        self.assertEqual(SubscriptionService._normalized_subscription_status(subscription), "expired")
        self.assertFalse(SubscriptionService._is_effectively_active(subscription))


class SubscriptionQuotaGuardTest(unittest.TestCase):
    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_blocks_request_that_would_exceed_remaining_daily_quota(
        self,
        mock_get_or_create_cycle,
        mock_resolve_active_subscription,
    ):
        user = SimpleNamespace(id=1)
        subscription = SimpleNamespace(
            plan_kind_snapshot="daily_quota",
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )
        cycle = SimpleNamespace(used_amount=Decimal("80"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        with self.assertRaises(ServiceException) as ctx:
            SubscriptionService.check_quota_before_request(
                MagicMock(),
                user,
                quota_precheck={"estimated_total_tokens": Decimal("30")},
            )

        self.assertEqual(ctx.exception.error_code, "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED")
        mock_get_or_create_cycle.assert_called_once()

    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_consume_quota_rejects_post_request_overflow(
        self,
        mock_get_or_create_cycle,
    ):
        subscription = SimpleNamespace(
            id=99,
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )
        cycle = SimpleNamespace(
            id=7,
            used_amount=Decimal("95"),
            request_count=1,
            last_request_id="old",
            cycle_date=datetime.utcnow().date(),
        )
        mock_get_or_create_cycle.return_value = cycle

        with self.assertRaises(ServiceException) as ctx:
            SubscriptionService.consume_quota_after_request(
                MagicMock(),
                subscription,
                request_id="new",
                raw_total_tokens=10,
                total_cost=0.0,
            )

        self.assertEqual(ctx.exception.error_code, "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED")
        self.assertEqual(cycle.used_amount, Decimal("95"))
        self.assertEqual(cycle.request_count, 1)


class VerifyApiKeySubscriptionRefreshTest(unittest.TestCase):
    @patch("app.services.subscription_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_expired_cached_subscription_does_not_fail_in_auth_layer_after_refresh(self, mock_refresh):
        api_key_record = SimpleNamespace(
            user_id=1,
            status="active",
            expires_at=None,
        )
        user = SimpleNamespace(
            id=1,
            status=1,
            subscription_type="unlimited",
            subscription_expires_at=datetime.utcnow() - timedelta(days=1),
        )

        api_key_query = MagicMock()
        api_key_query.filter.return_value.first.return_value = api_key_record
        user_query = MagicMock()
        user_query.filter.return_value.first.return_value = user

        db = MagicMock()
        db.query.side_effect = [api_key_query, user_query]

        result_user, result_key = verify_api_key_from_headers(
            db,
            authorization="Bearer sk-test-key",
        )

        self.assertIs(result_user, user)
        self.assertIs(result_key, api_key_record)
        mock_refresh.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(user)


if __name__ == "__main__":
    unittest.main()
