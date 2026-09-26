import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ServiceException
from app.database import Base
from app.models.channel import Channel
from app.models.model import ModelChannelMapping, ModelGroup, UnifiedModel
from app.models.user import UserApiKey
from app.services.model_group_routing_service import (
    GROUP_MODE_SPECIAL,
    GROUP_MODE_UNIFIED,
    ModelGroupRoutingService,
)
from app.services.price_adjustment_service import PriceAdjustmentResolution
from app.services.proxy_service import ProxyService


class ModelGroupRoutingTest(unittest.TestCase):
    """Database-level coverage for API-key group routing and group-aware billing."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            cls.engine,
            tables=[
                Channel.__table__,
                UnifiedModel.__table__,
                ModelGroup.__table__,
                ModelChannelMapping.__table__,
                UserApiKey.__table__,
            ],
        )

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(
            cls.engine,
            tables=[
                Channel.__table__,
                UnifiedModel.__table__,
                ModelGroup.__table__,
                ModelChannelMapping.__table__,
                UserApiKey.__table__,
            ],
        )
        cls.engine.dispose()

    def setUp(self):
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.rollback()
        self.db.query(ModelChannelMapping).delete()
        self.db.query(UserApiKey).delete()
        self.db.query(Channel).delete()
        self.db.query(ModelGroup).delete()
        self.db.query(UnifiedModel).delete()
        self.db.commit()
        self.db.close()

    def _model(self, model_id, name, series):
        model = UnifiedModel(
            id=model_id,
            model_name=name,
            model_series=series,
            model_type="chat",
            protocol_type="openai",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("0"),
            enabled=1,
        )
        self.db.add(model)
        return model

    def _group(self, group_id, series, code, *, default=False, enabled=True, multiplier="1"):
        group = ModelGroup(
            id=group_id,
            model_series=series,
            code=code,
            name=code,
            multiplier=Decimal(multiplier),
            enabled=1 if enabled else 0,
            is_default=1 if default else 0,
            sort_order=group_id,
        )
        self.db.add(group)
        return group

    def _channel(self, channel_id, name, *, healthy=True, enabled=True, priority=10):
        channel = Channel(
            id=channel_id,
            name=name,
            base_url="https://upstream.invalid",
            api_key="fixture-token",
            protocol_type="openai",
            provider_variant="default",
            enabled=1 if enabled else 0,
            is_healthy=1 if healthy else 0,
            priority=priority,
        )
        self.db.add(channel)
        return channel

    def _mapping(self, mapping_id, model_id, group_id, channel_id, *, enabled=True):
        self.db.add(
            ModelChannelMapping(
                id=mapping_id,
                unified_model_id=model_id,
                group_id=group_id,
                channel_id=channel_id,
                actual_model_name="upstream-model",
                enabled=1 if enabled else 0,
            )
        )

    def _key(self, key_id, *, mode=GROUP_MODE_UNIFIED, series=None, group_id=None):
        key = UserApiKey(
            id=key_id,
            user_id=1,
            name=f"key-{key_id}",
            key_prefix="sk-fixture",
            key_hash=f"hash-{key_id}",
            status="active",
            group_mode=mode,
            group_model_series=series,
            group_id=group_id,
        )
        self.db.add(key)
        return key

    def test_unified_key_follows_current_default_group(self):
        model = self._model(1, "gpt-5", "gpt")
        cheap = self._group(11, "gpt", "cheap", default=True, multiplier="0.8")
        normal = self._group(12, "gpt", "normal", multiplier="1.5")
        cheap_channel = self._channel(21, "cheap-upstream")
        normal_channel = self._channel(22, "normal-upstream")
        self._mapping(31, model.id, cheap.id, cheap_channel.id)
        self._mapping(32, model.id, normal.id, normal_channel.id)
        key = self._key(41)
        self.db.commit()

        context, channels = ModelGroupRoutingService.get_available_channels(self.db, key, model)
        self.assertEqual(context.group_id, cheap.id)
        self.assertEqual(context.group_name, cheap.name)
        self.assertEqual(context.group_multiplier, Decimal("0.800000"))
        self.assertEqual([channel.id for channel, _ in channels], [cheap_channel.id])

        # A legacy/unified key resolves the newly selected default without changing the key.
        normal.is_default = 1
        cheap.is_default = 0
        self.db.commit()
        context, channels = ModelGroupRoutingService.get_available_channels(self.db, key, model)
        self.assertEqual(context.group_id, normal.id)
        self.assertEqual([channel.id for channel, _ in channels], [normal_channel.id])

    def test_special_key_is_limited_to_one_series_and_group(self):
        gpt = self._model(1, "gpt-5", "gpt")
        claude = self._model(2, "claude-4", "claude")
        gpt_group = self._group(11, "gpt", "cheap", default=True)
        claude_group = self._group(12, "claude", "cheap", default=True)
        gpt_channel = self._channel(21, "gpt-upstream")
        claude_channel = self._channel(22, "claude-upstream")
        self._mapping(31, gpt.id, gpt_group.id, gpt_channel.id)
        self._mapping(32, claude.id, claude_group.id, claude_channel.id)
        key = self._key(
            41,
            mode=GROUP_MODE_SPECIAL,
            series="gpt",
            group_id=gpt_group.id,
        )
        self.db.commit()

        context, channels = ModelGroupRoutingService.get_available_channels(self.db, key, gpt)
        self.assertEqual(context.group_id, gpt_group.id)
        self.assertEqual([channel.id for channel, _ in channels], [gpt_channel.id])

        with self.assertRaises(ServiceException) as raised:
            ModelGroupRoutingService.resolve_context(self.db, key, claude)
        self.assertEqual(raised.exception.error_code, "API_KEY_MODEL_GROUP_MISMATCH")

    def test_group_failure_does_not_fallback_to_another_group(self):
        model = self._model(1, "gpt-5", "gpt")
        cheap = self._group(11, "gpt", "cheap", default=True)
        normal = self._group(12, "gpt", "normal")
        unavailable = self._channel(21, "cheap-down", healthy=False)
        fallback = self._channel(22, "normal-up")
        self._mapping(31, model.id, cheap.id, unavailable.id)
        self._mapping(32, model.id, normal.id, fallback.id)
        key = self._key(41)
        self.db.commit()

        with self.assertRaises(ServiceException) as raised:
            ModelGroupRoutingService.get_available_channels(self.db, key, model)
        self.assertEqual(raised.exception.error_code, "MODEL_GROUP_NO_AVAILABLE_CHANNEL")
        self.assertIn("当前分组暂无可用渠道", raised.exception.detail)

    def test_disabled_special_group_is_rejected(self):
        model = self._model(1, "gpt-5", "gpt")
        group = self._group(11, "gpt", "cheap", enabled=False)
        key = self._key(41, mode=GROUP_MODE_SPECIAL, series="gpt", group_id=group.id)
        self.db.commit()

        with self.assertRaises(ServiceException) as raised:
            ModelGroupRoutingService.resolve_context(self.db, key, model)
        self.assertEqual(raised.exception.error_code, "MODEL_GROUP_UNAVAILABLE")

    def test_special_model_listing_filters_to_bound_series_and_live_group_mapping(self):
        gpt = self._model(1, "gpt-5", "gpt")
        gpt_without_mapping = self._model(2, "gpt-6", "gpt")
        claude = self._model(3, "claude-4", "claude")
        gpt_group = self._group(11, "gpt", "cheap", default=True)
        claude_group = self._group(12, "claude", "default", default=True)
        gpt_channel = self._channel(21, "gpt-upstream")
        claude_channel = self._channel(22, "claude-upstream")
        self._mapping(31, gpt.id, gpt_group.id, gpt_channel.id)
        self._mapping(32, claude.id, claude_group.id, claude_channel.id)
        key = self._key(41, mode=GROUP_MODE_SPECIAL, series="gpt", group_id=gpt_group.id)
        self.db.commit()

        models = ModelGroupRoutingService.list_available_models(self.db, key)
        self.assertEqual([model.model_name for model, _context in models], ["gpt-5"])
        self.assertEqual(models[0][1].group_id, gpt_group.id)

        unified_models = ModelGroupRoutingService.list_available_models(self.db, self._key(42))
        self.db.commit()
        self.assertEqual(
            {model.model_name for model, _context in unified_models},
            {"gpt-5", "claude-4"},
        )
        self.assertNotIn(gpt_without_mapping.model_name, {model.model_name for model, _ in unified_models})

    def test_token_billing_multiplies_user_rule_group_fast_and_long_context(self):
        model = UnifiedModel(
            id=1,
            model_name="gpt-priced",
            model_series="gpt",
            model_type="chat",
            protocol_type="openai",
            billing_type="token",
            input_price_per_million=Decimal("1"),
            output_price_per_million=Decimal("0"),
            long_context_billing_enabled=1,
            long_context_token_threshold=100,
            enabled=1,
        )
        self.db.add(model)
        self.db.commit()

        with (
            patch("app.services.proxy_service.get_system_config", return_value=1),
            patch(
                "app.services.proxy_service.PriceAdjustmentService.resolve_adjustment",
                return_value=PriceAdjustmentResolution(multiplier=Decimal("1.2"), source="user"),
            ),
            patch("app.services.proxy_service.ProxyService.estimate_responses_input_tokens", return_value=100),
        ):
            precheck = ProxyService._build_text_quota_precheck(
                self.db,
                "responses",
                {"input": "fixture", "max_output_tokens": 1, "service_tier": "priority"},
                model,
                user_id=7,
                billing_context={
                    "group_id": 11,
                    "group_name": "cheap",
                    "group_multiplier": Decimal("0.8"),
                },
            )

        # 1.2 (user rule) * 0.8 (group) * 2 (fast) * 2 (long context).
        self.assertEqual(precheck["group_multiplier_snapshot"], Decimal("0.800000"))
        self.assertEqual(precheck["fast_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(precheck["context_price_multiplier_snapshot"], Decimal("2"))
        self.assertEqual(precheck["effective_price_multiplier_snapshot"], Decimal("3.840000"))
        self.assertEqual(precheck["estimated_total_cost"], Decimal("0.000384000"))


if __name__ == "__main__":
    unittest.main()
