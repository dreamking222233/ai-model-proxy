import unittest
from collections import defaultdict
from contextlib import nullcontext
from decimal import Decimal
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.core.exceptions import ServiceException
from app.core.dependencies import verify_api_key_from_headers
from app.models.log import UserSubscription
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.channel_service import ChannelService
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
    def test_stale_balance_user_with_active_unlimited_subscription_checks_quota(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        db = MagicMock()
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="unlimited")

        ProxyService._assert_text_request_allowed(db, user)

        mock_refresh.assert_called_once()
        mock_check_quota.assert_called_once_with(db, user, quota_precheck=None)
        db.query.assert_not_called()

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_unlimited_subscription_precheck_requires_balance_for_fallback(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = None

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="unlimited", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="unlimited")
        mock_check_quota.side_effect = ServiceException(
            403,
            "已超出实际使用额度，每日最多可使用 300,000,000 Token，请明天再试",
            SubscriptionService.UNLIMITED_DAILY_LIMIT_ERROR_CODE,
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(db, user)

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

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
    def test_active_quota_subscription_precheck_falls_back_to_balance_when_balance_covers_estimate(
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

        ProxyService._assert_text_request_allowed(
            db,
            user,
            quota_precheck={"estimated_total_cost": Decimal("0.4")},
        )

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_quota_subscription_precheck_blocks_when_balance_does_not_cover_estimate(
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
                quota_precheck={"estimated_total_cost": Decimal("999")},
            )

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_quota_subscription_precheck_blocks_when_balance_is_at_threshold(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.1"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="daily_quota")
        mock_check_quota.side_effect = ServiceException(
            403,
            "当日套餐额度已用尽，请明天再试或联系管理员升级套餐",
            "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(db, user)

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

    @patch("app.services.proxy_service.SubscriptionService.check_quota_before_request")
    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state")
    def test_active_unlimited_subscription_precheck_falls_back_to_balance_when_balance_covers_estimate(
        self,
        mock_refresh,
        mock_check_quota,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.5"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="unlimited", subscription_expires_at=None)
        mock_refresh.return_value = SimpleNamespace(plan_kind_snapshot="unlimited")
        mock_check_quota.side_effect = ServiceException(
            403,
            "本次请求预计会超出实际使用额度，每日最多可使用 $120.00，请缩短上下文或降低输出上限后重试",
            SubscriptionService.UNLIMITED_DAILY_LIMIT_ERROR_CODE,
        )

        ProxyService._assert_text_request_allowed(
            db,
            user,
            quota_precheck={"estimated_total_cost": Decimal("0.4")},
        )

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
    def test_expired_subscription_requires_balance_to_cover_estimate(
        self,
        _mock_refresh,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.5"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(
            id=1,
            subscription_type="unlimited",
            subscription_expires_at=datetime.utcnow() - timedelta(days=1),
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(
                db,
                user,
                quota_precheck={"estimated_total_cost": Decimal("1.5")},
            )

        self.assertEqual(ctx.exception.error_code, "SUBSCRIPTION_EXPIRED")

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_expired_subscription_with_balance_at_threshold_raises_subscription_expired(
        self,
        _mock_refresh,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.1"))

        db = MagicMock()
        db.query.return_value = balance_query
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

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_balance_user_blocks_when_estimate_is_higher_than_balance(
        self,
        _mock_refresh,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.5"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(
                db,
                user,
                quota_precheck={"estimated_total_cost": Decimal("1.5")},
            )

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_balance_user_with_balance_at_threshold_raises_before_request(
        self,
        _mock_refresh,
    ):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("0.1"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._assert_text_request_allowed(db, user)

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")

    @patch("app.services.proxy_service.SubscriptionService.refresh_user_subscription_state", return_value=None)
    def test_balance_user_with_sufficient_balance_for_estimate_is_allowed(self, _mock_refresh):
        balance_query = MagicMock()
        balance_query.filter.return_value.first.return_value = SimpleNamespace(balance=Decimal("2.0"))

        db = MagicMock()
        db.query.return_value = balance_query
        user = SimpleNamespace(id=1, subscription_type="balance", subscription_expires_at=None)

        ProxyService._assert_text_request_allowed(
            db,
            user,
            quota_precheck={"estimated_total_cost": Decimal("1.5")},
        )


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


class SubscriptionQuotaPolicyResolutionTest(unittest.TestCase):
    def test_legacy_monthly_unlimited_uses_120_usd_daily_limit(self):
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 9, 23, 59, 59),
        )

        self.assertEqual(
            SubscriptionService._get_effective_quota_metric(subscription),
            SubscriptionService.QUOTA_METRIC_COST,
        )
        self.assertEqual(
            SubscriptionService._get_effective_quota_limit(subscription),
            Decimal("120"),
        )

    def test_new_monthly_unlimited_uses_100_usd_daily_limit(self):
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 10, 0, 0, 0),
        )

        self.assertEqual(
            SubscriptionService._get_effective_quota_metric(subscription),
            SubscriptionService.QUOTA_METRIC_COST,
        )
        self.assertEqual(
            SubscriptionService._get_effective_quota_limit(subscription),
            Decimal("100"),
        )


class ResponsesFastBillingTest(unittest.TestCase):
    @patch("app.services.proxy_service.ModelService.get_available_channels")
    @patch("app.services.proxy_service.ProxyService._assert_text_request_allowed")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    def test_responses_context_rejects_image_credit_model_before_text_billing(
        self,
        mock_resolve_model,
        mock_assert_text_request_allowed,
        mock_get_available_channels,
    ):
        mock_resolve_model.return_value = SimpleNamespace(
            model_name="gpt-image-2",
            model_type="image",
            billing_type="image_credit",
        )

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._prepare_responses_request_context(
                MagicMock(),
                SimpleNamespace(id=1),
                "gpt-image-2",
                {"model": "gpt-image-2", "input": "draw a cat"},
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES")
        mock_assert_text_request_allowed.assert_not_called()
        mock_get_available_channels.assert_not_called()

    @patch("app.services.proxy_service.ModelService.get_available_channels")
    @patch("app.services.proxy_service.ProxyService._assert_text_request_allowed")
    @patch("app.services.proxy_service.get_system_config", return_value=1.0)
    @patch("app.services.proxy_service.ModelService.resolve_model")
    def test_responses_context_strips_image_generation_tool_without_blocking_text(
        self,
        mock_resolve_model,
        mock_get_system_config,
        mock_assert_text_request_allowed,
        mock_get_available_channels,
    ):
        mock_resolve_model.return_value = SimpleNamespace(
            id=10,
            model_name="gpt-5",
            model_type="chat",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("1"),
        )
        channel = SimpleNamespace(
            id=20,
            name="openai-text-channel",
            protocol_type="openai",
            provider_variant="default",
            priority=1,
        )
        mock_get_available_channels.return_value = [(channel, "gpt-5.5")]
        request_data = {
            "model": "gpt-5",
            "input": "draw a cat",
            "tools": [
                {"type": "image_generation"},
                {"type": "function", "name": "read_file"},
            ],
        }

        unified_model, channels = ProxyService._prepare_responses_request_context(
            MagicMock(),
            SimpleNamespace(id=1),
            "gpt-5",
            request_data,
        )

        self.assertEqual(unified_model, mock_resolve_model.return_value)
        self.assertEqual(channels, [(channel, "gpt-5.5")])
        self.assertEqual(request_data["tools"], [{"type": "function", "name": "read_file"}])
        mock_assert_text_request_allowed.assert_called_once()
        mock_get_available_channels.assert_called_once()

    def test_remove_responses_image_generation_tool_clears_forced_tool_choice(self):
        request_data = {
            "tools": [{"type": "image_generation"}],
            "tool_choice": {"type": "image_generation"},
        }

        removed = ProxyService._remove_responses_image_generation_tool(request_data)

        self.assertTrue(removed)
        self.assertNotIn("tools", request_data)
        self.assertNotIn("tool_choice", request_data)

    def test_remove_responses_image_generation_tool_clears_tool_choice_without_tools(self):
        request_data = {
            "input": "draw a cat",
            "tool_choice": {"type": "image_generation"},
        }

        removed = ProxyService._remove_responses_image_generation_tool(request_data)

        self.assertTrue(removed)
        self.assertNotIn("tool_choice", request_data)

    def test_remove_responses_image_generation_tool_filters_allowed_tool_choice(self):
        request_data = {
            "tools": [
                {"type": "IMAGE_GENERATION"},
                {"type": "function", "name": "read_file"},
            ],
            "tool_choice": {
                "type": "allowed_tools",
                "tools": [
                    {"type": "image_generation"},
                    {"type": "function", "name": "read_file"},
                ],
            },
        }

        removed = ProxyService._remove_responses_image_generation_tool(request_data)

        self.assertTrue(removed)
        self.assertEqual(request_data["tools"], [{"type": "function", "name": "read_file"}])
        self.assertEqual(
            request_data["tool_choice"]["tools"],
            [{"type": "function", "name": "read_file"}],
        )

    @patch("app.services.proxy_service.ProxyService._assert_text_request_allowed")
    @patch("app.services.proxy_service.ModelService.get_available_channels")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    def test_responses_context_rejects_mapping_to_image_upstream_model(
        self,
        mock_resolve_model,
        mock_get_available_channels,
        mock_assert_text_request_allowed,
    ):
        mock_resolve_model.return_value = SimpleNamespace(
            id=10,
            model_name="codex-text-alias",
            model_type="chat",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("1"),
        )
        mock_get_available_channels.return_value = [(
            SimpleNamespace(
                id=20,
                name="openai-text-channel",
                protocol_type="openai",
                provider_variant="default",
                priority=1,
            ),
            "gpt-image-2",
        )]

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._prepare_responses_request_context(
                MagicMock(),
                SimpleNamespace(id=1),
                "codex-text-alias",
                None,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES")
        mock_assert_text_request_allowed.assert_called_once()
        mock_get_available_channels.assert_called_once()

    @patch("app.services.proxy_service.ProxyService._assert_text_request_allowed")
    @patch("app.services.proxy_service.ModelService.get_available_channels")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    def test_responses_context_rejects_mapping_to_unregistered_image_named_model(
        self,
        mock_resolve_model,
        mock_get_available_channels,
        mock_assert_text_request_allowed,
    ):
        mock_resolve_model.return_value = SimpleNamespace(
            id=10,
            model_name="codex-text-alias",
            model_type="chat",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("1"),
        )
        mock_get_available_channels.return_value = [(
            SimpleNamespace(
                id=20,
                name="openai-text-channel",
                protocol_type="openai",
                provider_variant="default",
                priority=1,
            ),
            "future-image-model-preview",
        )]

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._prepare_responses_request_context(
                MagicMock(),
                SimpleNamespace(id=1),
                "codex-text-alias",
                None,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.error_code, "IMAGE_MODEL_NOT_SUPPORTED_FOR_RESPONSES")
        mock_assert_text_request_allowed.assert_called_once()
        mock_get_available_channels.assert_called_once()

    def test_filter_responses_text_channels_rejects_image_provider_variants(self):
        channels = [
            (
                SimpleNamespace(
                    id=1,
                    name="openai-image-compatible",
                    protocol_type="openai",
                    provider_variant=ChannelService.PROVIDER_VARIANT_OPENAI_IMAGE_COMPATIBLE,
                ),
                "text-looking-model",
            ),
            (
                SimpleNamespace(
                    id=2,
                    name="openai-image-native",
                    protocol_type="openai",
                    provider_variant=ChannelService.PROVIDER_VARIANT_OPENAI_IMAGE_NATIVE_SIZE,
                ),
                "text-looking-model",
            ),
            (
                SimpleNamespace(
                    id=3,
                    name="openai-image-modelinvoke",
                    protocol_type="openai",
                    provider_variant=ChannelService.PROVIDER_VARIANT_OPENAI_IMAGE_MODELINVOKE,
                ),
                "text-looking-model",
            ),
            (
                SimpleNamespace(
                    id=4,
                    name="vertex-image",
                    protocol_type="google",
                    provider_variant=ChannelService.PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE,
                ),
                "text-looking-model",
            ),
        ]

        filtered = ProxyService._filter_responses_text_channels(MagicMock(), channels)

        self.assertEqual(filtered, [])

    def test_responses_image_upstream_detection_uses_registered_image_model_metadata(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            model_name="paint-v1",
            model_type="image",
            billing_type="image_credit",
        )
        channel = SimpleNamespace(
            id=20,
            name="openai-text-channel",
            protocol_type="openai",
            provider_variant="default",
        )

        result = ProxyService._is_responses_image_upstream_candidate(
            db,
            channel,
            "paint-v1",
        )

        self.assertTrue(result)

    def test_filter_responses_text_channels_keeps_text_candidate_when_mixed(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        image_channel = SimpleNamespace(
            id=20,
            name="openai-text-channel-image",
            protocol_type="openai",
            provider_variant="default",
        )
        text_channel = SimpleNamespace(
            id=21,
            name="openai-text-channel",
            protocol_type="openai",
            provider_variant="default",
        )

        filtered = ProxyService._filter_responses_text_channels(
            db,
            [
                (image_channel, "gpt-image-2"),
                (text_channel, "gpt-5.5"),
            ],
        )

        self.assertEqual(filtered, [(text_channel, "gpt-5.5")])

    def test_build_text_billing_context_marks_priority_service_tier_as_fast(self):
        context = ProxyService._build_text_billing_context(
            "responses",
            {
                "service_tier": "priority",
            },
        )

        self.assertEqual(context["service_tier"], "priority")
        self.assertTrue(context["fast_mode_enabled"])
        self.assertEqual(context["fast_price_multiplier"], Decimal("2"))

    def test_context_price_multiplier_uses_strict_256k_boundary(self):
        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(262144),
            Decimal("1"),
        )
        self.assertEqual(
            ProxyService._get_context_price_multiplier_decimal(262145),
            Decimal("2"),
        )

    @patch("app.services.proxy_service.get_system_config")
    def test_responses_quota_precheck_applies_fast_multiplier_to_estimated_costs(
        self,
        mock_get_system_config,
    ):
        mock_get_system_config.return_value = 1.0

        unified_model = SimpleNamespace(
            input_price_per_million=Decimal("10"),
            output_price_per_million=Decimal("20"),
        )
        request_data = {
            "service_tier": "priority",
            "input": "hello",
            "max_output_tokens": 100,
        }

        with patch.object(ProxyService, "estimate_responses_input_tokens", return_value=200):
            result = ProxyService._build_text_quota_precheck(
                MagicMock(),
                "responses",
                request_data,
                unified_model,
            )

        self.assertEqual(result["fast_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(result["service_tier"], "priority")
        self.assertEqual(result["estimated_total_cost"], Decimal("0.008"))
        self.assertEqual(result["estimated_quota_cost"], Decimal("0.008"))
        self.assertEqual(result["context_price_multiplier_snapshot"], Decimal("1"))

    @patch("app.services.proxy_service.get_system_config")
    def test_quota_precheck_applies_long_context_without_price_multiplier_to_quota_cost(
        self,
        mock_get_system_config,
    ):
        def _side_effect(_db, key, default=None):
            if key == "price_multiplier":
                return 3
            return default

        mock_get_system_config.side_effect = _side_effect
        unified_model = SimpleNamespace(
            input_price_per_million=Decimal("10"),
            output_price_per_million=Decimal("20"),
        )
        request_data = {
            "service_tier": "priority",
            "input": "hello",
            "max_output_tokens": 200000,
        }

        with patch.object(ProxyService, "estimate_responses_input_tokens", return_value=70000):
            result = ProxyService._build_text_quota_precheck(
                MagicMock(),
                "responses",
                request_data,
                unified_model,
            )

        self.assertEqual(result["context_tokens_snapshot"], Decimal("270000"))
        self.assertEqual(result["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(result["fast_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(result["effective_price_multiplier_snapshot"], Decimal("12"))
        self.assertEqual(result["estimated_quota_cost"], Decimal("18.8"))
        self.assertEqual(result["estimated_total_cost"], Decimal("56.4"))

    @patch("app.services.proxy_service.get_system_config")
    def test_quota_precheck_prices_long_input_without_output_limit(
        self,
        mock_get_system_config,
    ):
        mock_get_system_config.return_value = 1.0
        unified_model = SimpleNamespace(
            input_price_per_million=Decimal("10"),
            output_price_per_million=Decimal("20"),
        )
        request_data = {
            "input": "hello",
        }

        with patch.object(ProxyService, "estimate_responses_input_tokens", return_value=270000):
            result = ProxyService._build_text_quota_precheck(
                MagicMock(),
                "responses",
                request_data,
                unified_model,
            )

        self.assertEqual(result["context_tokens_snapshot"], Decimal("270000"))
        self.assertEqual(result["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(result["estimated_total_cost"], Decimal("5.4"))
        self.assertEqual(result["estimated_quota_cost"], Decimal("5.4"))

    def test_legacy_enjoy_quota_uses_60_usd_daily_limit(self):
        subscription = SimpleNamespace(
            plan_kind_snapshot="daily_quota",
            plan_code_snapshot="weekly-10m-token",
            plan_name="周度畅享包",
            plan_type="custom",
            created_at=datetime(2026, 5, 9, 12, 0, 0),
            quota_metric="total_tokens",
            quota_value=Decimal("50000000"),
        )

        self.assertEqual(
            SubscriptionService._get_effective_quota_metric(subscription),
            SubscriptionService.QUOTA_METRIC_COST,
        )
        self.assertEqual(
            SubscriptionService._get_effective_quota_limit(subscription),
            Decimal("60"),
        )

    def test_new_enjoy_quota_uses_50_usd_daily_limit(self):
        subscription = SimpleNamespace(
            plan_kind_snapshot="daily_quota",
            plan_code_snapshot="daily-10m-token",
            plan_name="日度畅享包",
            plan_type="day",
            created_at=datetime(2026, 5, 10, 0, 0, 1),
            quota_metric="total_tokens",
            quota_value=Decimal("50000000"),
        )

        self.assertEqual(
            SubscriptionService._get_effective_quota_metric(subscription),
            SubscriptionService.QUOTA_METRIC_COST,
        )
        self.assertEqual(
            SubscriptionService._get_effective_quota_limit(subscription),
            Decimal("50"),
        )


class SubscriptionQuotaGuardTest(unittest.TestCase):
    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_allows_token_quota_request_when_cycle_is_not_exhausted(
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
        cycle = SimpleNamespace(used_amount=Decimal("70"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        SubscriptionService.check_quota_before_request(
            MagicMock(),
            user,
            quota_precheck={"estimated_total_tokens": Decimal("30")},
        )

        mock_get_or_create_cycle.assert_called_once()
        self.assertEqual(len(mock_get_or_create_cycle.call_args.args), 3)

    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_blocks_token_quota_when_estimate_exceeds_remaining(
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

    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_allows_unlimited_token_request_when_cycle_is_not_exhausted(
        self,
        mock_get_or_create_cycle,
        mock_resolve_active_subscription,
    ):
        user = SimpleNamespace(id=1)
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            quota_metric=None,
            quota_value=Decimal("0"),
        )
        cycle = SimpleNamespace(used_amount=Decimal("299999998"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        SubscriptionService.check_quota_before_request(
            MagicMock(),
            user,
            quota_precheck={"estimated_total_tokens": Decimal("2")},
        )

        mock_get_or_create_cycle.assert_called_once()
        self.assertEqual(len(mock_get_or_create_cycle.call_args.args), 3)

    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_allows_cost_quota_when_remaining_is_above_threshold(
        self,
        mock_get_or_create_cycle,
        mock_resolve_active_subscription,
    ):
        user = SimpleNamespace(id=1)
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 9, 23, 0, 0),
        )
        cycle = SimpleNamespace(used_amount=Decimal("117"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        SubscriptionService.check_quota_before_request(
            MagicMock(),
            user,
            quota_precheck={
                "estimated_total_cost": Decimal("999"),
                "estimated_quota_cost": Decimal("2"),
            },
        )

    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_blocks_cost_quota_when_estimate_exceeds_remaining(
        self,
        mock_get_or_create_cycle,
        mock_resolve_active_subscription,
    ):
        user = SimpleNamespace(id=1)
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 9, 23, 0, 0),
        )
        cycle = SimpleNamespace(used_amount=Decimal("119"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        with self.assertRaises(ServiceException) as ctx:
            SubscriptionService.check_quota_before_request(
                MagicMock(),
                user,
                quota_precheck={
                    "estimated_total_cost": Decimal("999"),
                    "estimated_quota_cost": Decimal("2"),
                },
            )

        self.assertEqual(ctx.exception.error_code, SubscriptionService.UNLIMITED_DAILY_LIMIT_ERROR_CODE)
        mock_get_or_create_cycle.assert_called_once()

    @patch("app.services.subscription_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_precheck_blocks_cost_quota_when_remaining_is_zero(
        self,
        mock_get_or_create_cycle,
        mock_resolve_active_subscription,
    ):
        user = SimpleNamespace(id=1)
        subscription = SimpleNamespace(
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 9, 23, 0, 0),
        )
        cycle = SimpleNamespace(used_amount=Decimal("120"))
        mock_resolve_active_subscription.return_value = subscription
        mock_get_or_create_cycle.return_value = cycle

        with self.assertRaises(ServiceException) as ctx:
            SubscriptionService.check_quota_before_request(MagicMock(), user)

        self.assertEqual(ctx.exception.error_code, SubscriptionService.UNLIMITED_DAILY_LIMIT_ERROR_CODE)

    def test_serialize_cycle_keeps_negative_remaining_amount(self):
        cycle = SimpleNamespace(
            id=7,
            cycle_date=None,
            cycle_start_at=None,
            cycle_end_at=None,
            quota_metric="cost_usd",
            quota_limit=Decimal("120"),
            used_amount=Decimal("125.5"),
            request_count=2,
            last_request_id="req-negative",
        )

        result = SubscriptionService._serialize_cycle(cycle, Decimal("120"))

        self.assertEqual(result["remaining_amount"], -5.5)

    @patch("app.services.subscription_service.SubscriptionService._load_cycle_by_id")
    @patch("app.services.subscription_service.SubscriptionService._apply_cycle_consumption_update")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_consume_unlimited_quota_records_daily_token_usage(
        self,
        mock_get_or_create_cycle,
        mock_apply_cycle_update,
        mock_load_cycle_by_id,
    ):
        subscription = SimpleNamespace(
            id=99,
            plan_kind_snapshot="unlimited",
            quota_metric=None,
            quota_value=Decimal("0"),
        )
        cycle = SimpleNamespace(
            id=7,
            used_amount=Decimal("299999990"),
            request_count=1,
            last_request_id="old",
            cycle_date=datetime.utcnow().date(),
        )
        mock_get_or_create_cycle.return_value = cycle
        mock_apply_cycle_update.return_value = True
        mock_load_cycle_by_id.return_value = SimpleNamespace(
            id=7,
            used_amount=Decimal("300000000"),
            cycle_date=cycle.cycle_date,
        )

        result = SubscriptionService.consume_quota_after_request(
            MagicMock(),
            subscription,
            request_id="new",
            raw_total_tokens=10,
            total_cost=0.0,
        )

        self.assertEqual(result["quota_metric"], "total_tokens")
        self.assertEqual(result["quota_limit_snapshot"], Decimal("300000000"))
        self.assertEqual(result["quota_used_after"], Decimal("300000000"))
        mock_apply_cycle_update.assert_called_once()

    @patch("app.services.subscription_service.SubscriptionService._load_cycle_by_id")
    @patch("app.services.subscription_service.SubscriptionService._apply_cycle_consumption_update")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_consume_new_monthly_unlimited_quota_uses_official_usd_cost(
        self,
        mock_get_or_create_cycle,
        mock_apply_cycle_update,
        mock_load_cycle_by_id,
    ):
        subscription = SimpleNamespace(
            id=99,
            plan_kind_snapshot="unlimited",
            plan_code_snapshot="monthly-unlimited",
            plan_name="月度无限包",
            plan_type="month",
            created_at=datetime(2026, 5, 10, 0, 0, 1),
        )
        cycle = SimpleNamespace(
            id=7,
            used_amount=Decimal("98.5"),
            request_count=1,
            last_request_id="old",
            cycle_date=datetime.utcnow().date(),
        )
        mock_get_or_create_cycle.return_value = cycle
        mock_apply_cycle_update.return_value = True
        mock_load_cycle_by_id.return_value = SimpleNamespace(
            id=7,
            used_amount=Decimal("100.0"),
            cycle_date=cycle.cycle_date,
        )

        result = SubscriptionService.consume_quota_after_request(
            MagicMock(),
            subscription,
            request_id="new",
            raw_total_tokens=99999999,
            total_cost=999.0,
            quota_cost=1.5,
        )

        self.assertEqual(result["quota_metric"], "cost_usd")
        self.assertEqual(result["quota_consumed_amount"], Decimal("1.5"))
        self.assertEqual(result["quota_limit_snapshot"], Decimal("100"))
        self.assertEqual(result["quota_used_after"], Decimal("100.0"))
        mock_apply_cycle_update.assert_called_once()

    @patch("app.services.subscription_service.SubscriptionService._load_cycle_by_id")
    @patch("app.services.subscription_service.SubscriptionService._apply_cycle_consumption_update")
    @patch("app.services.subscription_service.SubscriptionService._get_or_create_cycle")
    def test_consume_quota_blocks_post_request_overflow(
        self,
        mock_get_or_create_cycle,
        mock_apply_cycle_update,
        mock_load_cycle_by_id,
    ):
        subscription = SimpleNamespace(
            id=99,
            plan_kind_snapshot="daily_quota",
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
        mock_apply_cycle_update.return_value = False

        with self.assertRaises(ServiceException) as ctx:
            SubscriptionService.consume_quota_after_request(
                MagicMock(),
                subscription,
                request_id="new",
                raw_total_tokens=10,
                total_cost=0.0,
            )

        self.assertEqual(ctx.exception.error_code, "SUBSCRIPTION_QUOTA_UPDATE_FAILED")
        self.assertIn("套餐额度记账失败", ctx.exception.detail)
        self.assertEqual(mock_apply_cycle_update.call_count, 2)
        mock_load_cycle_by_id.assert_not_called()

    def test_rebuild_cycle_usage_snapshot_uses_quota_consumed_amount_for_mixed_records(self):
        aggregate = SimpleNamespace(
            request_count=1,
            total_cost=Decimal("2"),
            raw_total_tokens=Decimal("2000"),
            total_tokens=Decimal("2000"),
            quota_cost_used_amount=Decimal("0.2"),
            quota_token_used_amount=Decimal("200"),
        )
        latest_record = SimpleNamespace(request_id="req-mixed-1")

        aggregate_query = MagicMock()
        aggregate_query.filter.return_value.first.return_value = aggregate
        latest_query = MagicMock()
        latest_query.filter.return_value.order_by.return_value.first.return_value = latest_record
        db = MagicMock()
        db.query.side_effect = [aggregate_query, latest_query]

        subscription = SimpleNamespace(id=99, user_id=1, start_time=datetime.utcnow(), end_time=datetime.utcnow())

        cost_snapshot = SubscriptionService._rebuild_cycle_usage_snapshot(
            db,
            subscription,
            datetime.utcnow() - timedelta(hours=1),
            datetime.utcnow() + timedelta(hours=1),
            SubscriptionService.QUOTA_METRIC_COST,
        )

        self.assertEqual(cost_snapshot["used_amount"], Decimal("0.2"))

        db.query.side_effect = [aggregate_query, latest_query]
        token_snapshot = SubscriptionService._rebuild_cycle_usage_snapshot(
            db,
            subscription,
            datetime.utcnow() - timedelta(hours=1),
            datetime.utcnow() + timedelta(hours=1),
            SubscriptionService.QUOTA_METRIC_TOKENS,
        )

        self.assertEqual(token_snapshot["used_amount"], Decimal("200"))

    @patch("app.services.proxy_service.get_system_config")
    def test_text_quota_precheck_includes_official_quota_cost_without_price_multiplier(
        self,
        mock_get_system_config,
    ):
        def _side_effect(_db, key, default=None):
            if key == "price_multiplier":
                return 3
            return default

        mock_get_system_config.side_effect = _side_effect

        result = ProxyService._build_text_quota_precheck(
            db=MagicMock(),
            protocol="openai",
            request_data={"messages": [{"role": "user", "content": "hello"}], "max_tokens": 2000},
            unified_model=SimpleNamespace(input_price_per_million=2, output_price_per_million=4),
        )

        self.assertIn("estimated_total_cost", result)
        self.assertIn("estimated_quota_cost", result)
        self.assertGreater(result["estimated_total_cost"], result["estimated_quota_cost"])
        self.assertEqual(result["context_price_multiplier_snapshot"], Decimal("1"))

    @patch("app.services.proxy_service.get_system_config", side_effect=lambda _db, _key, default=None: default)
    @patch("app.services.proxy_service.RequestCacheSummaryService.persist_request_cache_summary")
    @patch("app.services.proxy_service.RequestCacheSummaryService.build_request_log_fields", return_value=_build_cache_log_fields())
    @patch("app.services.proxy_service.SubscriptionService._get_or_create_cycle")
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_amount_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_quota_falls_back_to_balance_when_daily_limit_is_insufficient(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_amount_after_request,
        mock_get_or_create_cycle,
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
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )
        mock_get_or_create_cycle.return_value = SimpleNamespace(used_amount=Decimal("99"))
        mock_consume_quota_amount_after_request.return_value = {
            "subscription_cycle_id": 7,
            "quota_metric": "total_tokens",
            "quota_consumed_amount": Decimal("1"),
            "quota_limit_snapshot": Decimal("100"),
            "quota_used_after": Decimal("100"),
            "quota_cycle_date": datetime.utcnow().date(),
        }

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

        consumption_record = write_db.add.call_args_list[0].args[0]
        self.assertEqual(consumption_record.billing_mode, "mixed")
        self.assertEqual(consumption_record.subscription_id, 99)
        self.assertEqual(consumption_record.quota_consumed_amount, Decimal("1"))
        self.assertEqual(balance.balance, Decimal("9.9980010"))
        mock_consume_quota_amount_after_request.assert_called_once()

    @patch("app.services.proxy_service.get_system_config", side_effect=lambda _db, _key, default=None: default)
    @patch("app.services.proxy_service.RequestCacheSummaryService.persist_request_cache_summary")
    @patch("app.services.proxy_service.RequestCacheSummaryService.build_request_log_fields", return_value=_build_cache_log_fields())
    @patch("app.services.proxy_service.SubscriptionService._load_cycle_by_id")
    @patch("app.services.proxy_service.SubscriptionService._get_or_create_cycle")
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_amount_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_quota_reloads_cycle_after_concurrent_update(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_amount_after_request,
        mock_get_or_create_cycle,
        mock_load_cycle_by_id,
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
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )
        mock_get_or_create_cycle.return_value = SimpleNamespace(id=7, used_amount=Decimal("99"))
        mock_load_cycle_by_id.return_value = SimpleNamespace(id=7, used_amount=Decimal("99.5"))
        mock_consume_quota_amount_after_request.side_effect = [
            ServiceException(500, "套餐额度记账失败，请稍后重试", "SUBSCRIPTION_QUOTA_UPDATE_FAILED"),
            {
                "subscription_cycle_id": 7,
                "quota_metric": "total_tokens",
                "quota_consumed_amount": Decimal("0.5"),
                "quota_limit_snapshot": Decimal("100"),
                "quota_used_after": Decimal("100"),
                "quota_cycle_date": datetime.utcnow().date(),
            },
        ]

        ProxyService._deduct_balance_and_log(
            db=MagicMock(),
            user=SimpleNamespace(id=1),
            api_key_record=None,
            unified_model=SimpleNamespace(model_name="gpt-4o", input_price_per_million=1, output_price_per_million=1),
            request_id="req-quota-concurrent-1",
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

        consumption_record = write_db.add.call_args_list[0].args[0]
        self.assertEqual(consumption_record.billing_mode, "mixed")
        self.assertEqual(consumption_record.quota_consumed_amount, Decimal("0.5"))
        self.assertEqual(balance.balance, Decimal("9.998000500"))
        mock_load_cycle_by_id.assert_called_once_with(write_db, 7)
        self.assertEqual(mock_consume_quota_amount_after_request.call_count, 2)

    @patch("app.services.proxy_service.get_system_config", side_effect=lambda _db, _key, default=None: default)
    @patch("app.services.proxy_service.RequestCacheSummaryService.persist_request_cache_summary")
    @patch("app.services.proxy_service.RequestCacheSummaryService.build_request_log_fields", return_value=_build_cache_log_fields())
    @patch("app.services.proxy_service.SubscriptionService._get_or_create_cycle")
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_amount_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_quota_blocks_when_daily_limit_and_balance_are_insufficient(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_amount_after_request,
        mock_get_or_create_cycle,
        _mock_build_request_log_fields,
        _mock_persist_request_cache_summary,
        _mock_get_system_config,
    ):
        fresh_user = SimpleNamespace(id=1, agent_id=None, subscription_type="unlimited")
        balance = SimpleNamespace(balance=Decimal("0.001"), total_consumed=Decimal("0"))

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
            quota_metric="total_tokens",
            quota_value=Decimal("100"),
        )
        mock_get_or_create_cycle.return_value = SimpleNamespace(used_amount=Decimal("99"))

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._deduct_balance_and_log(
                db=MagicMock(),
                user=SimpleNamespace(id=1),
                api_key_record=None,
                unified_model=SimpleNamespace(model_name="gpt-4o", input_price_per_million=1, output_price_per_million=1),
                request_id="req-quota-balance-block-1",
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

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_BALANCE")
        self.assertIn("当日套餐额度不足", ctx.exception.detail)
        self.assertEqual(balance.balance, Decimal("0.001"))
        mock_consume_quota_amount_after_request.assert_not_called()

    @patch("app.services.proxy_service.get_system_config")
    @patch("app.services.proxy_service.RequestCacheSummaryService.persist_request_cache_summary")
    @patch("app.services.proxy_service.RequestCacheSummaryService.build_request_log_fields")
    @patch("app.services.proxy_service.SubscriptionService._get_or_create_cycle")
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_amount_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_billing_applies_fast_and_long_context_multiplier(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_amount_after_request,
        mock_get_or_create_cycle,
        mock_build_request_log_fields,
        _mock_persist_request_cache_summary,
        mock_get_system_config,
    ):
        def _config_side_effect(_db, key, default=None):
            if key == "price_multiplier":
                return 3
            return default

        mock_get_system_config.side_effect = _config_side_effect
        cache_fields = _build_cache_log_fields()
        cache_fields["upstream_cache_read_input_tokens"] = 62145
        mock_build_request_log_fields.return_value = cache_fields

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
            quota_metric="cost_usd",
            quota_value=Decimal("100"),
        )
        mock_get_or_create_cycle.return_value = SimpleNamespace(used_amount=Decimal("0"))
        mock_consume_quota_amount_after_request.return_value = {
            "subscription_cycle_id": 7,
            "quota_metric": "cost_usd",
            "quota_consumed_amount": Decimal("12.24858"),
            "quota_limit_snapshot": Decimal("100"),
            "quota_used_after": Decimal("12.24858"),
            "quota_cycle_date": datetime.utcnow().date(),
        }

        ProxyService._deduct_balance_and_log(
            db=MagicMock(),
            user=SimpleNamespace(id=1),
            api_key_record=None,
            unified_model=SimpleNamespace(model_name="gpt-5.5", input_price_per_million=10, output_price_per_million=20),
            request_id="req-fast-long-context-1",
            requested_model="gpt-5.5",
            input_tokens=100000,
            output_tokens=100000,
            channel=SimpleNamespace(id=1, name="channel-a", protocol_type="responses"),
            client_ip="127.0.0.1",
            response_time_ms=100,
            is_stream=False,
            actual_model="gpt-5.4-mini",
            request_type="chat",
            cache_info={"cache_status": "HIT"},
            billing_context={
                "service_tier": "priority",
                "fast_price_multiplier": Decimal("2"),
            },
        )

        consumption_record = write_db.add.call_args_list[0].args[0]
        request_log = write_db.add.call_args_list[1].args[0]
        self.assertEqual(consumption_record.context_tokens_snapshot, 262145)
        self.assertEqual(consumption_record.context_price_multiplier_snapshot, Decimal("2"))
        self.assertEqual(consumption_record.fast_price_multiplier_snapshot, Decimal("2"))
        self.assertEqual(consumption_record.price_multiplier_snapshot, Decimal("3"))
        self.assertEqual(consumption_record.total_cost, Decimal("36.74574"))
        self.assertEqual(request_log.context_tokens_snapshot, 262145)
        self.assertEqual(request_log.context_price_multiplier_snapshot, Decimal("2"))
        self.assertEqual(request_log.fast_price_multiplier_snapshot, Decimal("2"))
        self.assertEqual(request_log.price_multiplier_snapshot, Decimal("3"))
        mock_consume_quota_amount_after_request.assert_called_once()
        self.assertEqual(
            mock_consume_quota_amount_after_request.call_args.kwargs["consumed_amount"],
            Decimal("36.74574"),
        )

    @patch("app.services.proxy_service.get_system_config", side_effect=lambda _db, _key, default=None: default)
    @patch("app.services.proxy_service.SubscriptionService._get_or_create_cycle")
    @patch("app.services.proxy_service.SubscriptionService.consume_quota_amount_after_request")
    @patch("app.services.proxy_service.SubscriptionService.resolve_active_subscription")
    @patch("app.services.proxy_service.session_scope")
    def test_post_request_unlimited_quota_remains_subscription_billing_when_limit_can_cover_usage(
        self,
        mock_session_scope,
        mock_resolve_active_subscription,
        mock_consume_quota_amount_after_request,
        mock_get_or_create_cycle,
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
            plan_kind_snapshot="unlimited",
        )
        mock_get_or_create_cycle.return_value = SimpleNamespace(used_amount=Decimal("0"))
        mock_consume_quota_amount_after_request.return_value = {
            "subscription_cycle_id": 8,
            "quota_metric": "total_tokens",
            "quota_consumed_amount": Decimal("10"),
            "quota_limit_snapshot": Decimal("300000000"),
            "quota_used_after": Decimal("10"),
            "quota_cycle_date": datetime.utcnow().date(),
        }

        ProxyService._deduct_balance_and_log(
            db=MagicMock(),
            user=SimpleNamespace(id=1),
            api_key_record=None,
            unified_model=SimpleNamespace(model_name="gpt-4o", input_price_per_million=1, output_price_per_million=1),
            request_id="req-unlimited-overflow-1",
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

        consumption_record = write_db.add.call_args_list[0].args[0]
        self.assertEqual(consumption_record.billing_mode, "subscription")
        self.assertEqual(consumption_record.subscription_id, 99)
        self.assertEqual(consumption_record.quota_used_after, Decimal("10"))


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


class AdminUserSubscriptionDisplayTest(unittest.TestCase):
    def _build_user_list_db(self, user, balance=Decimal("0")):
        main_query = MagicMock()
        main_query.outerjoin.return_value = main_query
        main_query.order_by.return_value = main_query
        main_query.count.return_value = 1
        main_query.offset.return_value = main_query
        main_query.limit.return_value = main_query
        main_query.all.return_value = [(user, balance)]

        image_query = MagicMock()
        image_query.filter.return_value.first.return_value = None

        db = MagicMock()
        db.query.side_effect = [main_query, image_query]
        return db

    @patch("app.services.subscription_service.SubscriptionService.get_current_subscription_summary")
    @patch("app.services.subscription_service.SubscriptionService.refresh_user_subscription_state")
    def test_list_users_displays_balance_when_cancelled_subscription_cache_is_stale(
        self,
        mock_refresh,
        mock_summary,
    ):
        user = SimpleNamespace(
            id=157,
            username="liujixin",
            email="liujixin@wearehackerone.com",
            role="user",
            status=1,
            avatar=None,
            agent_id=None,
            source_domain=None,
            last_login_at=None,
            created_at=None,
            subscription_type="unlimited",
            subscription_expires_at=datetime.utcnow() + timedelta(days=2),
        )
        db = self._build_user_list_db(user, Decimal("100"))
        mock_refresh.return_value = None
        mock_summary.return_value = {"subscription_type": "balance"}

        items, total = AuthService.list_users(db)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["subscription_type"], "balance")
        self.assertIsNone(items[0]["subscription_expires_at"])

    @patch("app.services.subscription_service.SubscriptionService.get_current_subscription_summary")
    @patch("app.services.subscription_service.SubscriptionService.refresh_user_subscription_state")
    def test_list_users_displays_quota_from_current_subscription_summary(
        self,
        mock_refresh,
        mock_summary,
    ):
        expires_at = datetime.utcnow() + timedelta(days=5)
        user = SimpleNamespace(
            id=1,
            username="quota-user",
            email="quota@example.com",
            role="user",
            status=1,
            avatar=None,
            agent_id=None,
            source_domain=None,
            last_login_at=None,
            created_at=None,
            subscription_type="unlimited",
            subscription_expires_at=expires_at,
        )
        db = self._build_user_list_db(user, Decimal("2"))
        mock_refresh.return_value = SimpleNamespace(end_time=expires_at)
        mock_summary.return_value = {"subscription_type": "quota"}

        items, _total = AuthService.list_users(db)

        self.assertEqual(items[0]["subscription_type"], "quota")
        self.assertEqual(items[0]["subscription_expires_at"], expires_at.isoformat())


class AdminSubscriptionRecordSearchTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()
        self._id_counters = defaultdict(int)
        event.listen(self.db, "before_flush", self._assign_sqlite_bigint_ids)

    def tearDown(self):
        event.remove(self.db, "before_flush", self._assign_sqlite_bigint_ids)
        self.db.close()
        self.engine.dispose()

    def _assign_sqlite_bigint_ids(self, session, _flush_context, _instances):
        for obj in session.new:
            if not hasattr(obj, "id") or getattr(obj, "id", None) is not None:
                continue
            self._id_counters[obj.__class__] += 1
            setattr(obj, "id", self._id_counters[obj.__class__])

    def _create_user_with_subscription(
        self,
        user_id: int,
        username: str,
        email: str,
        status: str = "active",
        start_delta_days: int = -1,
        end_delta_days: int = 29,
    ):
        now = SubscriptionService.get_current_time()
        user = self.db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            self.db.add(
                SysUser(
                    id=user_id,
                    username=username,
                    email=email,
                    password_hash="hash",
                    role="user",
                    status=1,
                )
            )
            self.db.flush()
        self.db.add(
            UserSubscription(
                user_id=user_id,
                plan_name="月度无限包",
                plan_type="monthly",
                plan_kind_snapshot="unlimited",
                duration_days_snapshot=30,
                quota_metric="cost_usd",
                quota_value=Decimal("100"),
                reset_period="day",
                reset_timezone="Asia/Shanghai",
                activation_mode="append",
                start_time=now + timedelta(days=start_delta_days),
                end_time=now + timedelta(days=end_delta_days),
                status=status,
                activated_at=now,
            )
        )

    def test_list_all_subscriptions_filters_by_username(self):
        self._create_user_with_subscription(157, "liujixin", "liujixin@example.com")
        self._create_user_with_subscription(158, "other-user", "other@example.com")
        self.db.commit()

        items, total = SubscriptionService.list_all_subscriptions(
            self.db,
            keyword="liujixin",
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)
        self.assertEqual(items[0]["username"], "liujixin")

    def test_list_all_subscriptions_filters_by_user_id(self):
        self._create_user_with_subscription(157, "liujixin", "liujixin@example.com")
        self._create_user_with_subscription(158, "other-user", "other@example.com")
        self.db.commit()

        items, total = SubscriptionService.list_all_subscriptions(
            self.db,
            keyword="157",
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)

    def test_list_all_subscriptions_filters_by_email(self):
        self._create_user_with_subscription(157, "liujixin", "liujixin@example.com")
        self._create_user_with_subscription(158, "other-user", "other@example.com")
        self.db.commit()

        items, total = SubscriptionService.list_all_subscriptions(
            self.db,
            keyword="liujixin@example.com",
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)

    def test_list_all_subscriptions_combines_keyword_and_status(self):
        self._create_user_with_subscription(157, "liujixin", "liujixin@example.com", status="cancelled")
        self._create_user_with_subscription(158, "liujixin-other", "other@example.com", status="active")
        self.db.commit()

        items, total = SubscriptionService.list_all_subscriptions(
            self.db,
            status="cancelled",
            keyword="liujixin",
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)
        self.assertEqual(items[0]["status"], "cancelled")

    def test_list_active_subscription_users_sorts_by_remaining_time(self):
        self._create_user_with_subscription(157, "soon-user", "soon@example.com", end_delta_days=2)
        self._create_user_with_subscription(158, "later-user", "later@example.com", end_delta_days=10)
        self.db.commit()

        asc_items, asc_total = SubscriptionService.list_active_subscription_users(
            self.db,
            sort_order="asc",
        )
        desc_items, desc_total = SubscriptionService.list_active_subscription_users(
            self.db,
            sort_order="desc",
        )

        self.assertEqual(asc_total, 2)
        self.assertEqual(desc_total, 2)
        self.assertEqual([item["user_id"] for item in asc_items], [157, 158])
        self.assertEqual([item["user_id"] for item in desc_items], [158, 157])
        self.assertLessEqual(asc_items[0]["remaining_days"], asc_items[1]["remaining_days"])

    def test_list_active_subscription_users_filters_expiring_soon(self):
        self._create_user_with_subscription(157, "soon-user", "soon@example.com", end_delta_days=2)
        self._create_user_with_subscription(158, "later-user", "later@example.com", end_delta_days=10)
        self.db.commit()

        items, total = SubscriptionService.list_active_subscription_users(
            self.db,
            expires_within_days=7,
        )

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)

    def test_list_active_subscription_users_excludes_inactive_records(self):
        self._create_user_with_subscription(157, "active-user", "active@example.com", end_delta_days=2)
        self._create_user_with_subscription(158, "cancelled-user", "cancelled@example.com", status="cancelled", end_delta_days=2)
        self._create_user_with_subscription(159, "expired-user", "expired@example.com", end_delta_days=-1)
        self._create_user_with_subscription(160, "future-user", "future@example.com", start_delta_days=1, end_delta_days=10)
        self.db.commit()

        items, total = SubscriptionService.list_active_subscription_users(self.db)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)

    def test_list_active_subscription_users_returns_one_current_record_per_user(self):
        self._create_user_with_subscription(157, "overlap-user", "overlap@example.com", end_delta_days=2)
        self._create_user_with_subscription(157, "overlap-user", "overlap@example.com", end_delta_days=10)
        self.db.commit()

        items, total = SubscriptionService.list_active_subscription_users(self.db)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["user_id"], 157)
        self.assertGreaterEqual(items[0]["remaining_days"], 9)


if __name__ == "__main__":
    unittest.main()
