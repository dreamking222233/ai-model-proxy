import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.model import ModelPriceAdjustmentRule, UnifiedModel, UserPriceAdjustmentRule
from app.models.user import SysUser
from app.services.price_adjustment_service import PriceAdjustmentService
from app.services.proxy_service import ProxyService


class UserPriceAdjustmentTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[
                SysUser.__table__,
                UnifiedModel.__table__,
                ModelPriceAdjustmentRule.__table__,
                UserPriceAdjustmentRule.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_user_rule_overrides_global_rule_for_same_series(self):
        db = self.Session()
        try:
            model = UnifiedModel(
                id=1,
                model_name="gpt-test",
                model_series="gpt",
                model_type="chat",
                billing_type="token",
            )
            db.add_all([
                SysUser(id=1, username="zhangsan", email="zhangsan@example.com", password_hash="x"),
                model,
                ModelPriceAdjustmentRule(
                    id=1,
                    name="global gpt",
                    model_series="gpt",
                    model_type="chat",
                    billing_type="token",
                    multiplier=Decimal("2"),
                    enabled=1,
                    priority=10,
                ),
                UserPriceAdjustmentRule(
                    id=2,
                    name="zhangsan gpt",
                    user_id=1,
                    model_series="gpt",
                    model_type="chat",
                    billing_type="token",
                    multiplier=Decimal("1.25"),
                    enabled=1,
                    priority=10,
                ),
            ])
            db.commit()

            resolved_for_user = PriceAdjustmentService.resolve_adjustment(db, model, user_id=1)
            resolved_for_other = PriceAdjustmentService.resolve_adjustment(db, model, user_id=2)

            self.assertEqual(resolved_for_user.source, "user")
            self.assertEqual(resolved_for_user.multiplier, Decimal("1.250000"))
            self.assertEqual(resolved_for_other.source, "global")
            self.assertEqual(resolved_for_other.multiplier, Decimal("2.000000"))
        finally:
            db.close()

    def test_frozen_text_billing_context_keeps_precheck_multiplier(self):
        quota_precheck = {
            "global_price_multiplier_snapshot": Decimal("1"),
            "adjustment_price_multiplier_snapshot": Decimal("1.25"),
            "price_adjustment_source_snapshot": "user",
            "price_adjustment_rule_id_snapshot": 99,
            "fast_price_multiplier_snapshot": Decimal("1"),
            "context_price_multiplier_snapshot": Decimal("1"),
            "context_tokens_snapshot": Decimal("32"),
            "context_token_threshold_snapshot": Decimal(str(ProxyService._LONG_CONTEXT_TOKEN_THRESHOLD)),
        }

        context = ProxyService._build_frozen_text_billing_context(
            ProxyService._build_text_billing_context("openai", {"model": "gpt-test"}),
            quota_precheck,
        )

        self.assertTrue(context["price_adjustment_frozen"])
        self.assertEqual(context["adjustment_price_multiplier_snapshot"], Decimal("1.25"))
        self.assertEqual(context["price_adjustment_source_snapshot"], "user")
        self.assertEqual(context["price_adjustment_rule_id_snapshot"], 99)

    def test_frozen_media_video_route_sanitizes_upstream_urls(self):
        body = {
            "id": "video-1",
            "status": "completed",
            "video_url": "https://upstream.example/video.mp4",
            "url": "https://upstream.example/video.mp4",
            "video": {"url": "https://upstream.example/video.mp4"},
        }

        sanitized = ProxyService._sanitize_video_task_response_body(body, "video-1")

        self.assertEqual(sanitized["content_url"], "/v1/videos/video-1/content")
        self.assertEqual(sanitized["retrieve_url"], "/v1/videos/video-1")
        self.assertNotIn("video_url", sanitized)
        self.assertNotIn("url", sanitized)
        self.assertNotIn("url", sanitized["video"])

    def test_media_credit_adjustment_uses_user_rule_source(self):
        model = UnifiedModel(
            model_name="gpt-image",
            model_series="gpt",
            model_type="image",
            billing_type="image_credit",
        )

        fake_db = object()
        with patch(
            "app.services.proxy_service.PriceAdjustmentService.resolve_multiplier",
            return_value=Decimal("2"),
        ) as resolve_multiplier:
            adjusted = ProxyService._apply_media_credit_price_adjustment(
                fake_db,
                model,
                Decimal("1.500"),
                user_id=123,
            )

        self.assertEqual(adjusted, Decimal("3.000"))
        resolve_multiplier.assert_called_once_with(fake_db, model, user_id=123)


if __name__ == "__main__":
    unittest.main()
