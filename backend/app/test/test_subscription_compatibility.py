import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
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

        mock_check_quota.assert_called_once_with(db, user)

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


if __name__ == "__main__":
    unittest.main()
