import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
from app.services.model_service import ModelService
from app.services.proxy_service import ProxyService


class ModelImageResolutionRuleValidationTest(unittest.TestCase):
    def test_validate_resolution_rules_rejects_unsupported_google_size(self):
        with self.assertRaises(ServiceException) as ctx:
            ModelService._validate_resolution_rules(
                "gemini-2.5-flash-image",
                "image",
                "google",
                "image_credit",
                [
                    {"resolution_code": "1K", "enabled": 1, "credit_cost": "1", "is_default": 1, "sort_order": 10},
                    {"resolution_code": "4K", "enabled": 1, "credit_cost": "3", "is_default": 0, "sort_order": 20},
                ],
            )

        self.assertEqual(ctx.exception.error_code, "IMAGE_SIZE_NOT_SUPPORTED")

    def test_validate_resolution_rules_accepts_decimal_credit_cost(self):
        rules = ModelService._validate_resolution_rules(
            "gemini-3-pro-image-preview",
            "image",
            "google",
            "image_credit",
            [
                {"resolution_code": "1K", "enabled": 1, "credit_cost": "3", "is_default": 1, "sort_order": 10},
                {"resolution_code": "2K", "enabled": 1, "credit_cost": "4.5", "is_default": 0, "sort_order": 20},
            ],
        )

        self.assertEqual(rules[1]["credit_cost"], Decimal("4.500"))


class ProxyGoogleImageResolutionCompatibilityTest(unittest.TestCase):
    def test_extract_requested_google_image_size_supports_multiple_parameter_names(self):
        self.assertEqual(
            ProxyService._extract_requested_google_image_size({"image_size": "2k"}),
            "2K",
        )
        self.assertEqual(
            ProxyService._extract_requested_google_image_size({"imageSize": "4K"}),
            "4K",
        )
        self.assertEqual(
            ProxyService._extract_requested_google_image_size({"size": "1k"}),
            "1K",
        )

    def test_build_google_image_payload_keeps_legacy_size_as_aspect_ratio(self):
        payload = ProxyService._build_google_image_payload(
            {"prompt": "draw", "size": "1024x1024"},
            image_size=None,
        )

        self.assertEqual(
            payload["generationConfig"]["imageConfig"]["aspectRatio"],
            "1:1",
        )
        self.assertNotIn("imageSize", payload["generationConfig"]["imageConfig"])

    def test_build_google_image_payload_includes_google_image_size(self):
        payload = ProxyService._build_google_image_payload(
            {"prompt": "draw", "aspect_ratio": "1:1"},
            image_size="2K",
        )

        self.assertEqual(
            payload["generationConfig"]["imageConfig"]["imageSize"],
            "2K",
        )

    @patch("app.services.proxy_service.ModelService.get_google_image_resolution_capabilities", return_value=("1K", "2K", "4K"))
    @patch("app.services.proxy_service.ModelService.resolve_image_resolution_rule")
    def test_resolve_image_billing_rule_uses_requested_resolution_rule(
        self,
        mock_resolve_rule,
        _mock_capabilities,
    ):
        def _fake_resolve(_db, _model_id, requested_size=None):
            if requested_size == "2K":
                return {
                    "resolution_code": "2K",
                    "enabled": 1,
                    "credit_cost": 4.5,
                    "is_default": 0,
                    "sort_order": 20,
                }
            if requested_size is None:
                return {
                    "resolution_code": "1K",
                    "enabled": 1,
                    "credit_cost": 3.0,
                    "is_default": 1,
                    "sort_order": 10,
                }
            return None

        mock_resolve_rule.side_effect = _fake_resolve

        image_size, credit_cost = ProxyService._resolve_image_billing_rule(
            MagicMock(),
            SimpleNamespace(id=1, model_name="gemini-3-pro-image-preview", image_credit_multiplier=3),
            {"image_size": "2K"},
        )

        self.assertEqual(image_size, "2K")
        self.assertEqual(credit_cost, Decimal("4.500"))

    @patch("app.services.proxy_service.ModelService.get_google_image_resolution_capabilities", return_value=("1K", "2K", "4K"))
    @patch("app.services.proxy_service.ModelService.resolve_image_resolution_rule", return_value=None)
    def test_resolve_image_billing_rule_rejects_enabled_but_missing_rule(
        self,
        _mock_resolve_rule,
        _mock_capabilities,
    ):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_image_billing_rule(
                MagicMock(),
                SimpleNamespace(id=1, model_name="gemini-3-pro-image-preview", image_credit_multiplier=3),
                {"image_size": "2K"},
            )

        self.assertEqual(ctx.exception.error_code, "IMAGE_SIZE_NOT_ENABLED")

    def test_resolve_image_billing_rule_rejects_invalid_legacy_size(self):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_image_billing_rule(
                MagicMock(),
                SimpleNamespace(id=1, model_name="gemini-3-pro-image-preview", image_credit_multiplier=3),
                {"size": "1200x1200"},
            )

        self.assertEqual(ctx.exception.error_code, "INVALID_IMAGE_SIZE")


if __name__ == "__main__":
    unittest.main()
