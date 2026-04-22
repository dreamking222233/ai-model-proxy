import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.health_service import _resolve_health_target
from app.services.proxy_service import ProxyService


class OpenAIImagePromptAdaptationTest(unittest.TestCase):
    def test_build_openai_image_prompt_appends_size_and_ratio_hints(self):
        prompt = ProxyService._build_openai_image_prompt(
            "一只漂浮在太空里的猫",
            image_size="2K",
            aspect_ratio="1:1",
        )

        self.assertIn("一只漂浮在太空里的猫", prompt)
        self.assertIn("1:1", prompt)
        self.assertIn("2K", prompt)
        self.assertIn("保持原始提示词", prompt)

    def test_build_openai_image_prompt_without_hints_returns_original_prompt(self):
        prompt = ProxyService._build_openai_image_prompt("一只漂浮在太空里的猫")
        self.assertEqual(prompt, "一只漂浮在太空里的猫")

    def test_resolve_openai_image_generation_url_supports_root_and_v1_base(self):
        self.assertEqual(
            ProxyService._resolve_openai_image_generation_url("http://43.156.153.12:3000"),
            "http://43.156.153.12:3000/v1/images/generations",
        )
        self.assertEqual(
            ProxyService._resolve_openai_image_generation_url("http://43.156.153.12:3000/v1"),
            "http://43.156.153.12:3000/v1/images/generations",
        )


class OpenAIImageBillingCompatibilityTest(unittest.TestCase):
    @patch("app.services.proxy_service.ModelService.resolve_image_resolution_rule", return_value=None)
    def test_resolve_image_billing_rule_accepts_prompt_adapted_openai_image_size(
        self,
        _mock_resolve_rule,
    ):
        image_size, credit_cost = ProxyService._resolve_image_billing_rule(
            MagicMock(),
            SimpleNamespace(id=1, model_name="gpt-image-2", image_credit_multiplier=Decimal("1.500")),
            {"image_size": "2K"},
        )

        self.assertEqual(image_size, "2K")
        self.assertEqual(credit_cost, Decimal("1.500"))


class OpenAIImageRoutingTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "app.services.proxy_service.ProxyService._non_stream_openai_image_request",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.proxy_service.ProxyService._non_stream_google_image_request",
        new_callable=AsyncMock,
    )
    async def test_non_stream_image_request_routes_openai_image_channel(
        self,
        mock_google_request,
        mock_openai_request,
    ):
        mock_openai_request.return_value = "openai-image-response"
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-compatible",
        )

        result = await ProxyService._non_stream_image_request(
            SimpleNamespace(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw"},
            "req-1",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("1.000"),
            image_size="1K",
        )

        self.assertEqual(result, "openai-image-response")
        mock_openai_request.assert_awaited_once()
        mock_google_request.assert_not_awaited()


class OpenAIImageHealthTargetTest(unittest.TestCase):
    def test_resolve_health_target_for_openai_image_channel(self):
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-compatible",
        )
        model_name, upstream_api = _resolve_health_target(channel, "gpt-image-2")
        self.assertEqual(model_name, "gpt-image-2")
        self.assertEqual(upstream_api, "openai_image_generation")


if __name__ == "__main__":
    unittest.main()
