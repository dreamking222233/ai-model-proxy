import unittest
from contextlib import nullcontext
from decimal import Decimal
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
from app.core.dependencies import verify_api_key_from_headers
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService


def _build_cache_log_fields() -> dict:
    return {
        "cache_status": "BYPASS",
        "cache_hit_segments": 0,
        "cache_miss_segments": 0,
        "cache_bypass_segments": 0,
        "cache_reused_tokens": 0,
        "cache_new_tokens": 0,
        "cache_reused_chars": 0,
        "cache_new_chars": 0,
        "logical_input_tokens": 0,
        "upstream_input_tokens": 0,
        "upstream_cache_read_input_tokens": 0,
        "upstream_cache_creation_input_tokens": 0,
        "upstream_cache_creation_5m_input_tokens": 0,
        "upstream_cache_creation_1h_input_tokens": 0,
        "upstream_prompt_cache_status": "BYPASS",
        "conversation_session_id": None,
        "conversation_match_status": None,
        "compression_mode": None,
        "compression_status": None,
        "original_estimated_input_tokens": 0,
        "compressed_estimated_input_tokens": 0,
        "compression_saved_estimated_tokens": 0,
        "compression_ratio": 1,
        "compression_fallback_reason": None,
        "upstream_session_mode": None,
        "upstream_session_id": None,
    }


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

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_quota_subscription_precheck_falls_back_to_balance_when_balance_is_sufficient(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("5"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="daily_quota")
        mock_check_quota.side_effect = ServiceException(
            403,
            "本次请求预计会超出当日套餐剩余额度，请缩短上下文或降低输出上限后重试",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

        ProxyService._assert_text_request_allowed(
            db,
            user,
            quota_precheck={"estimated_total_cost": Decimal("1.5")},
        )

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_quota_subscription_precheck_still_blocks_when_balance_is_insufficient(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.5"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="daily_quota")
        mock_check_quota.side_effect = ServiceException(
            403,
            "本次请求预计会超出当日套餐剩余额度，请缩短上下文或降低输出上限后重试",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(
                db,
                user,
                quota_precheck={"estimated_total_cost": Decimal("1.5")},
            )

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

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

    @patch("app.services.proxy_service.get_system_config", side_effect=lambda _db, _key, default=None: default)
    @patch("app.services.proxy_service.RequestCacheSummaryService.persist_request_cache_summary")
    @patch("app.services.proxy_service.RequestCacheSummaryService.build_request_log_fields", return_value=_build_cache_log_fields())
    @patch("app.services.proxy_service.ConversationSessionService.commit_success_state", return_value=None)
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_quota_overflow_falls_back_to_balance_billing(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_after_request,
        _mock_commit_success_state,
        _mock_build_request_log_fields,
        _mock_persist_request_cache_summary,
        _mock_get_system_config,
    ):
        fresh_user = SimpleNamespace(id=1, agent_id=None, subscription_type="unlimited")
        balance = SimpleNamespace(balance=Decimal("10"), total_consumed=Decimal("0"))

        sys_user_query = MagicMock()
        sys_user_query.filter.return_value = sys_user_query
        sys_user_query.first.return_value = fresh_user
        balance_query = MagicMock()
        balance_query.filter.return_value = balance_query
        balance_query.with_for_update.return_value = balance_query
        balance_query.first.return_value = balance

        query_iter = iter([sys_user_query, balance_query])
        write_db = MagicMock()
        write_db.query.side_effect = lambda *_args, **_kwargs: next(query_iter)
        mock_session_scope.return_value = nullcontext(write_db)

        mock_resolve_active_subscription.return_value = SimpleNamespace(
            id=99,
            plan_kind_snapshot="daily_quota",
        )
        mock_consume_quota_after_request.side_effect = ServiceException(
            403,
            "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

        ProxyService._deduct_balance_and_log(
            db=MagicMock(),
            user=SimpleNamespace(id=1),
            api_key_record=None,
            unified_model=SimpleNamespace(model_name="gpt-4o", input_price_per_million=1, output_price_per_million=1),
            request_id="req-quota-fallback-1",
            requested_model="gpt-4o",
            input_tokens=1000,
            output_tokens=1000,
            channel=SimpleNamespace(id=1, name="channel-a", protocol_type="openai"),
            client_ip="127.0.0.1",
            response_time_ms=100,
            is_stream=False,
            actual_model="gpt-4o",
            request_type="chat",
        )

        self.assertLess(balance.balance, Decimal("10"))
        consumption_record = write_db.add.call_args_list[0].args[0]
        self.assertEqual(consumption_record.billing_mode, "balance")
        self.assertIsNone(consumption_record.subscription_id)


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
