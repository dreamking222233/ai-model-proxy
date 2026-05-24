import json
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.channel_service import ChannelService
from app.services.health_service import _resolve_health_target, _resolve_openai_image_health_url
from app.core.exceptions import ServiceException
from app.services.proxy_service import ProxyService


class _DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _DummyAsyncClient:
    def __init__(self, response, captured=None):
        self._response = response
        self._captured = captured if captured is not None else {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        self._captured["args"] = args
        self._captured["kwargs"] = kwargs
        return self._response


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

    def test_resolve_openai_image_generation_url_supports_modelinvoke_variant(self):
        self.assertEqual(
            ProxyService._resolve_openai_image_generation_url(
                "http://43.156.153.12:3000",
                "openai-image-modelinvoke",
            ),
            "http://43.156.153.12:3000/v1/image/created",
        )

    def test_resolve_openai_image_edit_url_supports_root_and_v1_base(self):
        self.assertEqual(
            ProxyService._resolve_openai_image_edit_url("http://43.156.153.12:3000"),
            "http://43.156.153.12:3000/v1/images/edits",
        )
        self.assertEqual(
            ProxyService._resolve_openai_image_edit_url("http://43.156.153.12:3000/v1"),
            "http://43.156.153.12:3000/v1/images/edits",
        )

    def test_resolve_openai_image_edit_url_supports_modelinvoke_variant(self):
        self.assertEqual(
            ProxyService._resolve_openai_image_edit_url(
                "http://43.156.153.12:3000",
                "openai-image-modelinvoke",
            ),
            "http://43.156.153.12:3000/v1/image/edit",
        )

    def test_localize_openai_image_error_body_translates_stream_disconnect(self):
        self.assertEqual(
            ProxyService._localize_openai_image_error_body(
                '{"error":{"message":"stream disconnected before completion","type":"server_error"}}'
            ),
            "上游连接在图片结果返回完成前中断，请稍后重试",
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

    def test_validate_single_image_count_rejects_invalid_string(self):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._validate_single_image_count({"n": "abc"})

        self.assertEqual(ctx.exception.error_code, "IMAGE_COUNT_NOT_SUPPORTED")

    def test_resolve_image_billing_rule_classifies_pixel_size_to_4k(self):
        image_size, credit_cost = ProxyService._resolve_image_billing_rule(
            MagicMock(),
            SimpleNamespace(id=1, model_name="gpt-image-2", image_credit_multiplier=Decimal("2.000")),
            {"size": "3840x2160"},
        )

        self.assertEqual(image_size, "4K")
        self.assertEqual(credit_cost, Decimal("2.000"))

    def test_resolve_requested_aspect_ratio_infers_ratio_from_pixel_size(self):
        self.assertEqual(
            ProxyService._resolve_requested_aspect_ratio({"size": "3840x2160"}),
            "16:9",
        )

    def test_resolve_image_billing_rule_rejects_conflicting_image_size_and_size(self):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_image_billing_rule(
                MagicMock(),
                SimpleNamespace(id=1, model_name="gpt-image-2", image_credit_multiplier=Decimal("1.500")),
                {"image_size": "1K", "size": "3840x2160"},
            )

        self.assertEqual(ctx.exception.error_code, "INVALID_IMAGE_SIZE")

    def test_resolve_requested_image_count_rejects_zero(self):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_requested_image_count({"n": 0})

        self.assertEqual(ctx.exception.error_code, "IMAGE_COUNT_NOT_SUPPORTED")


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

    @patch(
        "app.services.proxy_service.ProxyService._non_stream_openai_image_request",
        new_callable=AsyncMock,
    )
    async def test_non_stream_image_request_routes_modelinvoke_openai_image_channel(
        self,
        mock_openai_request,
    ):
        mock_openai_request.return_value = "modelinvoke-response"
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-modelinvoke",
        )

        result = await ProxyService._non_stream_image_request(
            SimpleNamespace(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw"},
            "req-modelinvoke-1",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("1.000"),
            image_size="1K",
        )

        self.assertEqual(result, "modelinvoke-response")
        mock_openai_request.assert_awaited_once()

    def test_filter_channels_by_image_size_skips_1k_only_compatible_channel(self):
        unified_model = SimpleNamespace(model_name="gpt-image-2")
        channels = [
            (
                SimpleNamespace(protocol_type="openai", provider_variant="openai-image-compatible"),
                "gpt-image-2",
            ),
            (
                SimpleNamespace(protocol_type="openai", provider_variant="openai-image-native-size"),
                "gpt-image-2",
            ),
        ]

        filtered = ProxyService._filter_channels_by_image_size(channels, unified_model, "4K")

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0][0].provider_variant, "openai-image-native-size")

    @patch(
        "app.services.proxy_service.ProxyService._non_stream_openai_image_edit_request",
        new_callable=AsyncMock,
    )
    async def test_non_stream_image_edit_request_routes_openai_image_channel(
        self,
        mock_openai_edit_request,
    ):
        mock_openai_edit_request.return_value = "openai-image-edit-response"
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-compatible",
        )

        result = await ProxyService._non_stream_image_edit_request(
            SimpleNamespace(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "edit", "image": {"content": b"123"}},
            "req-2",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("0.500"),
            image_size="1K",
        )

        self.assertEqual(result, "openai-image-edit-response")
        mock_openai_edit_request.assert_awaited_once()

    @patch("app.services.proxy_service.ProxyService._deduct_image_credits_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    @patch("app.services.proxy_service.ProxyService._post_with_retries", new_callable=AsyncMock)
    @patch("app.services.proxy_service.ProxyService._build_headers", return_value={})
    async def test_non_stream_openai_image_request_forwards_n_and_returns_multi_images(
        self,
        _mock_headers,
        mock_post_with_retries,
        mock_record_success,
        mock_deduct_and_log,
    ):
        mock_post_with_retries.return_value = _DummyResponse(
            status_code=200,
            payload={
                "data": [
                    {"b64_json": "img-1", "revised_prompt": "prompt-1"},
                    {"b64_json": "img-2", "revised_prompt": "prompt-2"},
                ]
            },
        )
        channel = SimpleNamespace(
            id=10,
            name="chatgpt-image",
            protocol_type="openai",
            base_url="http://43.156.153.12:3000",
        )

        response = await ProxyService._non_stream_openai_image_request(
            MagicMock(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw", "n": 2},
            "req-3",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("1.000"),
            requested_image_count=2,
            model_multiplier=Decimal("0.500"),
            image_size="1K",
        )

        payload = mock_post_with_retries.await_args.args[1]
        self.assertEqual(payload["n"], 2)
        mock_record_success.assert_called_once()
        mock_deduct_and_log.assert_called_once()
        self.assertEqual(mock_deduct_and_log.call_args.kwargs["charged_credits"], Decimal("1.000"))
        self.assertEqual(mock_deduct_and_log.call_args.kwargs["model_multiplier"], Decimal("0.500"))
        self.assertEqual(mock_deduct_and_log.call_args.kwargs["image_count"], 2)

        response_body = json.loads(response.body.decode("utf-8"))
        self.assertEqual(len(response_body["data"]), 2)
        self.assertEqual(response_body["usage"]["image_count"], 2)
        self.assertEqual(response_body["usage"]["image_credits_charged"], 1.0)
        self.assertEqual(response_body["usage"]["model_multiplier"], 0.5)

    async def test_non_stream_openai_image_request_rejects_n_greater_than_four(self):
        with self.assertRaises(ServiceException) as ctx:
            await ProxyService._non_stream_openai_image_request(
                MagicMock(),
                SimpleNamespace(id=1),
                SimpleNamespace(id=2),
                SimpleNamespace(
                    id=10,
                    name="chatgpt-image",
                    protocol_type="openai",
                    base_url="http://43.156.153.12:3000",
                ),
                SimpleNamespace(id=3),
                {"prompt": "draw", "n": 5},
                "req-4",
                "gpt-image-2",
                "gpt-image-2",
                "127.0.0.1",
                Decimal("2.500"),
                requested_image_count=5,
                model_multiplier=Decimal("0.500"),
                image_size="1K",
            )

        self.assertEqual(ctx.exception.error_code, "IMAGE_COUNT_NOT_SUPPORTED")

    @patch("app.services.proxy_service.ProxyService._deduct_image_credits_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    @patch("app.services.proxy_service.ProxyService._post_with_retries", new_callable=AsyncMock)
    @patch("app.services.proxy_service.ProxyService._build_headers", return_value={})
    async def test_non_stream_openai_image_request_native_size_forwards_size_and_quality(
        self,
        _mock_headers,
        mock_post_with_retries,
        mock_record_success,
        mock_deduct_and_log,
    ):
        mock_post_with_retries.return_value = _DummyResponse(
            status_code=200,
            payload={"data": [{"b64_json": "img-1"}]},
        )
        channel = SimpleNamespace(
            id=10,
            name="chatgpt-image-native",
            protocol_type="openai",
            provider_variant="openai-image-native-size",
            base_url="http://43.156.153.12:3000",
        )

        await ProxyService._non_stream_openai_image_request(
            MagicMock(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {"prompt": "draw", "size": "3840x2160", "quality": "high"},
            "req-native-1",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("2.000"),
            requested_image_count=1,
            model_multiplier=Decimal("2.000"),
            image_size="4K",
        )

        payload = mock_post_with_retries.await_args.args[1]
        self.assertEqual(payload["prompt"], "draw")
        self.assertEqual(payload["size"], "3840x2160")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["response_format"], "b64_json")
        mock_record_success.assert_called_once()
        mock_deduct_and_log.assert_called_once()

    @patch("app.services.proxy_service.ProxyService._deduct_image_credits_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    @patch("app.services.proxy_service.ProxyService._build_headers", return_value={})
    @patch("app.services.proxy_service.httpx.AsyncClient")
    async def test_non_stream_openai_image_edit_request_native_size_forwards_size_and_quality(
        self,
        mock_async_client,
        _mock_headers,
        mock_record_success,
        mock_deduct_and_log,
    ):
        captured = {}
        mock_async_client.return_value = _DummyAsyncClient(
            _DummyResponse(status_code=200, payload={"data": [{"b64_json": "img-1"}]}),
            captured=captured,
        )
        channel = SimpleNamespace(
            id=10,
            name="chatgpt-image-native",
            protocol_type="openai",
            provider_variant="openai-image-native-size",
            base_url="http://43.156.153.12:3000",
        )

        response = await ProxyService._non_stream_openai_image_edit_request(
            MagicMock(),
            SimpleNamespace(id=1),
            SimpleNamespace(id=2),
            channel,
            SimpleNamespace(id=3),
            {
                "prompt": "edit",
                "size": "3840x2160",
                "quality": "high",
                "image": {
                    "filename": "input.png",
                    "content_type": "image/png",
                    "content": b"123",
                },
            },
            "req-native-edit-1",
            "gpt-image-2",
            "gpt-image-2",
            "127.0.0.1",
            Decimal("2.000"),
            image_size="4K",
        )

        files = captured["kwargs"]["files"]
        self.assertIn(("size", (None, "3840x2160")), files)
        self.assertIn(("quality", (None, "high")), files)
        self.assertIn(("response_format", (None, "b64_json")), files)
        mock_record_success.assert_called_once()
        mock_deduct_and_log.assert_called_once()

        response_body = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response_body["usage"]["image_size"], "4K")
        self.assertEqual(response_body["usage"]["image_credits_charged"], 2.0)

    def test_openai_image_modelinvoke_variant_supports_edit(self):
        self.assertTrue(
            ChannelService.supports_openai_image_edit(
                ChannelService.PROVIDER_VARIANT_OPENAI_IMAGE_MODELINVOKE
            )
        )


class OpenAIImageHealthTargetTest(unittest.TestCase):
    def test_resolve_health_target_for_openai_image_channel(self):
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-compatible",
        )
        model_name, upstream_api = _resolve_health_target(channel, "gpt-image-2")
        self.assertEqual(model_name, "gpt-image-2")
        self.assertEqual(upstream_api, "openai_image_generation")

    def test_resolve_health_target_for_modelinvoke_image_channel(self):
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-modelinvoke",
        )
        model_name, upstream_api = _resolve_health_target(channel, "gpt-image-2")
        self.assertEqual(model_name, "gpt-image-2")
        self.assertEqual(upstream_api, "openai_image_generation")

    def test_resolve_openai_image_health_url_for_modelinvoke_variant(self):
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-modelinvoke",
            base_url="http://43.156.153.12:3000",
        )
        self.assertEqual(
            _resolve_openai_image_health_url(channel),
            "http://43.156.153.12:3000/v1/image/created",
        )

    def test_resolve_health_target_for_openai_native_size_channel(self):
        channel = SimpleNamespace(
            protocol_type="openai",
            provider_variant="openai-image-native-size",
        )
        model_name, upstream_api = _resolve_health_target(channel, "gpt-image-2")
        self.assertEqual(model_name, "gpt-image-2")
        self.assertEqual(upstream_api, "openai_image_generation")


if __name__ == "__main__":
    unittest.main()
