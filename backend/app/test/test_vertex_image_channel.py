import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.channel_service import ChannelService
from app.services.google_vertex_image_service import GoogleVertexImageService
from app.services.proxy_service import ProxyService


class ChannelProviderVariantTest(unittest.TestCase):
    def test_google_channel_defaults_to_official_variant(self):
        self.assertEqual(
            ChannelService._normalize_provider_variant("google", None),
            ChannelService.PROVIDER_VARIANT_GOOGLE_OFFICIAL,
        )

    def test_non_google_channel_defaults_to_default_variant(self):
        self.assertEqual(
            ChannelService._normalize_provider_variant("openai", None),
            ChannelService.PROVIDER_VARIANT_DEFAULT,
        )


class GoogleVertexImageHelperTest(unittest.TestCase):
    def test_parse_model_candidates_supports_fallback_list(self):
        self.assertEqual(
            GoogleVertexImageService.parse_model_candidates(
                "imagen-3.0-fast-generate-001|imagen-3.0-generate-001|imagen-3.0-generate-002"
            ),
            [
                "imagen-3.0-fast-generate-001",
                "imagen-3.0-generate-001",
                "imagen-3.0-generate-002",
            ],
        )

    def test_looks_like_image_model_supports_imagen(self):
        self.assertTrue(
            GoogleVertexImageService.looks_like_image_model("imagen-3.0-fast-generate-001")
        )
        self.assertTrue(
            GoogleVertexImageService.looks_like_image_model("gemini-3.1-flash-image-preview")
        )
        self.assertFalse(
            GoogleVertexImageService.looks_like_image_model("gemini-2.5-flash")
        )

    def test_build_gemini_config_uses_aspect_ratio_only(self):
        captured = {}

        class _ImageConfig:
            def __init__(self, **kwargs):
                captured["image_config_kwargs"] = kwargs
                self.kwargs = kwargs

        class _GenerateContentConfig:
            def __init__(self, **kwargs):
                captured["generate_content_kwargs"] = kwargs

        fake_types = SimpleNamespace(
            ImageConfig=_ImageConfig,
            GenerateContentConfig=_GenerateContentConfig,
        )

        GoogleVertexImageService._build_gemini_config(fake_types, "1:1", "1K")

        self.assertEqual(captured["image_config_kwargs"], {"aspectRatio": "1:1"})
        self.assertIn("imageConfig", captured["generate_content_kwargs"])


class ProxyVertexDispatchTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "app.services.proxy_service.ProxyService._non_stream_google_image_request",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.proxy_service.ProxyService._non_stream_vertex_image_request",
        new_callable=AsyncMock,
    )
    async def test_non_stream_image_request_routes_vertex_channel(
        self,
        mock_vertex_request,
        mock_google_request,
    ):
        mock_vertex_request.return_value = "vertex-response"
        channel = SimpleNamespace(
            protocol_type="google",
            provider_variant="google-vertex-image",
        )

        result = await ProxyService._non_stream_image_request(
            SimpleNamespace(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw"},
            "req-1",
            "gemini-2.5-flash-image",
            "imagen-3.0-fast-generate-001|imagen-3.0-generate-001",
            "127.0.0.1",
            Decimal("1.000"),
            image_size="1K",
        )

        self.assertEqual(result, "vertex-response")
        mock_vertex_request.assert_awaited_once()
        mock_google_request.assert_not_awaited()

    @patch(
        "app.services.proxy_service.ProxyService._non_stream_google_image_request",
        new_callable=AsyncMock,
    )
    @patch(
        "app.services.proxy_service.ProxyService._non_stream_vertex_image_request",
        new_callable=AsyncMock,
    )
    async def test_non_stream_image_request_routes_google_official_channel(
        self,
        mock_vertex_request,
        mock_google_request,
    ):
        mock_google_request.return_value = "google-response"
        channel = SimpleNamespace(
            protocol_type="google",
            provider_variant="google-official",
        )

        result = await ProxyService._non_stream_image_request(
            SimpleNamespace(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw"},
            "req-2",
            "gemini-3-pro-image-preview",
            "gemini-3-pro-image-preview",
            "127.0.0.1",
            Decimal("3.000"),
            image_size="1K",
            request_headers={"user-agent": "test"},
        )

        self.assertEqual(result, "google-response")
        mock_google_request.assert_awaited_once()
        mock_vertex_request.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
