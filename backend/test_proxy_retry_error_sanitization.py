import json
import unittest
from unittest.mock import patch

from app.core.exceptions import ServiceException
from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.services.proxy_service import ProxyService, ResponsesTurnError


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_text(self, text):
        self.messages.append(text)


class ProxyRetryErrorSanitizationTest(unittest.IsolatedAsyncioTestCase):
    def test_dynamic_retry_count_uses_system_config(self):
        with patch("app.services.proxy_service.get_system_config", return_value=5):
            self.assertEqual(ProxyService._resolve_upstream_retry_attempts(object()), 6)

    def test_dynamic_retry_count_allows_zero(self):
        with patch("app.services.proxy_service.get_system_config", return_value=0):
            self.assertEqual(ProxyService._resolve_upstream_retry_attempts(object()), 1)

    def test_dynamic_retry_count_is_capped(self):
        with patch("app.services.proxy_service.get_system_config", return_value=99):
            self.assertEqual(ProxyService._resolve_upstream_retry_attempts(object()), 11)

    def test_runtime_retry_count_falls_back_to_channel_config(self):
        channel = Channel(id=1, name="test")
        setattr(channel, "_runtime_upstream_retry_attempts", 4)
        self.assertEqual(ProxyService._resolve_runtime_retry_attempts(channel, None), 4)

    def test_upstream_request_error_is_sanitized_but_keeps_log_detail(self):
        exc = ProxyService._map_upstream_request_error(
            Exception(
                'Upstream returned HTTP 400: {"error":{"message":"providers=codex 上游中文错误"}}'
            )
        )
        self.assertIsNotNone(exc)
        self.assertEqual(exc.status_code, 400)
        self.assertEqual(exc.detail, "请求参数不符合上游渠道要求，请检查后重试")
        self.assertIn("providers=codex 上游中文错误", ProxyService._request_error_log_detail(exc))

    def test_upstream_context_error_uses_compress_message(self):
        exc = ProxyService._map_upstream_request_error(
            Exception("Upstream returned HTTP 400: context length exceeded providers=codex 上游错误")
        )
        self.assertIsNotNone(exc)
        self.assertEqual(exc.error_code, "CONTENT_TOO_LONG")
        self.assertEqual(exc.detail, "请求超出最大上下文,请压缩对话")

    def test_transient_upstream_http_errors_are_channel_failures_and_visible_generic(self):
        samples = [
            'Upstream returned HTTP 502: {"error":{"message":"Upstream service temporarily unavailable"}}',
            'Upstream returned HTTP 429: {"error":{"message":"Upstream rate limit exceeded"}}',
            'Upstream returned HTTP 503: {"error":{"message":"auth_unavailable: no auth available (providers=codex)"}}',
            'Upstream returned HTTP 403: {"error":{"message":"Chat upstream returned 403"}}',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertIsNone(ProxyService._map_upstream_request_error(Exception(sample)))
                self.assertEqual(
                    ProxyService._sanitize_visible_model_text(sample, "requested-model", "actual-model"),
                    "调用失败，渠道异常，请稍后重试",
                )

    def test_failure_log_detail_keeps_upstream_detail_for_sanitized_exception(self):
        raw_detail = '上游服务返回异常（HTTP 503）：{"error":{"message":"providers=codex 上游中文错误"}}'
        exc = ProxyService._build_user_visible_upstream_request_error(
            "UPSTREAM_INVALID_REQUEST",
            upstream_detail=raw_detail,
            status_code=503,
        )
        self.assertEqual(exc.detail, "调用失败，渠道异常，请稍后重试")
        self.assertEqual(ProxyService._failure_error_log_detail(exc), raw_detail)

    def test_raw_upstream_error_detection_is_heuristic_not_example_based(self):
        samples = [
            '上游返回（HTTP 503）：{"error":{"code":"model_not_found","message":"任意渠道中文错误 (request id: req-1)","type":"new_api_error"}}',
            'Gateway failed (HTTP 502): {"error":{"message":"temporary unavailable","code":"server_error"}}',
            '{"error":{"message":"上游中文错误 (request_id=req-2)","type":"provider_error"}}',
            "HTTP 429: rate limit exceeded by provider beta request_id=req-3",
            "auth_unavailable: no auth available (providers=alpha, model=internal-name)",
        ]

        for raw_detail in samples:
            with self.subTest(raw_detail=raw_detail):
                self.assertTrue(ProxyService._looks_like_raw_upstream_error(raw_detail))
                self.assertEqual(
                    ProxyService._localize_user_visible_error_text(raw_detail),
                    "调用失败，渠道异常，请稍后重试",
                )
                self.assertEqual(
                    ProxyService._failure_error_log_detail(Exception(raw_detail), "requested-model", None),
                    raw_detail,
                )

    def test_local_user_friendly_errors_are_not_treated_as_raw_upstream(self):
        samples = [
            "当前模型暂无可用渠道，请稍后重试",
            "模型不存在",
            "websocket 请求缺少 input 字段",
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertFalse(ProxyService._looks_like_raw_upstream_error(sample))

    def test_video_upstream_error_builder_is_generic_but_keeps_log_detail(self):
        raw_detail = 'Grok 视频文生任务失败（HTTP 503）：{"error":{"message":"providers=codex 上游不可用"}}'
        exc = ProxyService._build_user_visible_upstream_request_error(
            "OPENAI_VIDEO_GENERATION_FAILED",
            upstream_detail=raw_detail,
            status_code=503,
        )
        self.assertEqual(exc.status_code, 503)
        self.assertEqual(exc.detail, "调用失败，渠道异常，请稍后重试")
        self.assertEqual(ProxyService._request_error_log_detail(exc), raw_detail)

    def test_image_upstream_error_keeps_raw_body_for_admin_log(self):
        raw_detail = (
            'OpenAI 图片生成失败（HTTP 429）：'
            '{"error":{"message":"rate limit providers=codex 上游中文原文"}}'
        )
        exc = ProxyService._build_user_visible_upstream_request_error(
            "OPENAI_IMAGE_GENERATION_FAILED",
            upstream_detail=raw_detail,
            status_code=429,
        )

        self.assertEqual(exc.status_code, 503)
        self.assertEqual(exc.detail, "调用失败，渠道异常，请稍后重试")
        self.assertNotIn("providers=codex", exc.detail)
        self.assertIn("providers=codex 上游中文原文", ProxyService._request_error_log_detail(exc))

    def test_second_pass_sanitization_keeps_existing_upstream_detail(self):
        raw_detail = (
            'OpenAI 图片生成失败（HTTP 400）：'
            '{"error":{"message":"providers=codex 原始上游body"}}'
        )
        exc = ProxyService._build_user_visible_upstream_request_error(
            "OPENAI_IMAGE_GENERATION_FAILED",
            upstream_detail=raw_detail,
            status_code=400,
        )

        sanitized = ProxyService._sanitize_upstream_service_exception_for_user(exc)

        self.assertEqual(sanitized.status_code, 400)
        self.assertEqual(sanitized.detail, "请求参数不符合上游渠道要求，请检查后重试")
        self.assertEqual(ProxyService._request_error_log_detail(sanitized), raw_detail)

    def test_localized_upstream_http_error_is_generic(self):
        text = '上游服务返回异常（HTTP 503）：{"error":{"message":"providers=codex 上游中文错误"}}'
        self.assertEqual(
            ProxyService._localize_user_visible_error_text(text),
            "调用失败，渠道异常，请稍后重试",
        )
        self.assertEqual(
            ProxyService._localize_user_visible_error_text(
                'Grok 视频文生任务失败（HTTP 503）：{"error":{"message":"上游不可用"}}'
            ),
            "调用失败，渠道异常，请稍后重试",
        )

    def test_all_channels_error_is_generic(self):
        exc = ProxyService._build_all_channels_failed_exception()
        self.assertEqual(exc.status_code, 503)
        self.assertEqual(exc.detail, "调用失败，渠道异常，请稍后重试")
        self.assertEqual(exc.error_code, "ALL_CHANNELS_FAILED")

    def test_256k_model_context_precheck_does_not_block_estimated_tokens(self):
        request_data = {
            "messages": [
                {"role": "user", "content": "a" * 625003},
            ]
        }
        model = UnifiedModel(model_name="test-256k", max_tokens=256000)
        with patch("app.services.proxy_service.get_system_config") as mocked_config:
            mocked_config.side_effect = lambda _db, key, default=None: {
                "max_message_length": 1000000,
                "max_context_tokens": 300000,
            }.get(key, default)
            ProxyService._validate_request_length(object(), request_data, model)

    def test_256k_responses_context_precheck_does_not_block_estimated_tokens(self):
        request_data = {
            "input": "a" * 625003,
        }
        model = UnifiedModel(model_name="test-256k", max_tokens=256000)
        with patch("app.services.proxy_service.get_system_config") as mocked_config:
            mocked_config.side_effect = lambda _db, key, default=None: {
                "max_message_length": 1000000,
                "max_context_tokens": 300000,
            }.get(key, default)
            ProxyService._validate_request_length(
                object(),
                request_data,
                model,
                protocol="responses",
            )

    async def test_responses_websocket_upstream_error_before_output_is_not_sent(self):
        async def fake_iter(*_args, **_kwargs):
            yield {
                "type": "error",
                "error": {"message": "providers=codex 上游中文错误"},
            }

        websocket = FakeWebSocket()
        channel = Channel(id=1, name="test")
        with patch.object(ProxyService, "_iter_responses_upstream_payloads", fake_iter):
            with self.assertRaises(ResponsesTurnError) as ctx:
                await ProxyService._forward_responses_websocket_turn(
                    websocket,
                    channel,
                    {"model": "actual-model"},
                    "requested-model",
                )

        self.assertTrue(ctx.exception.can_retry)
        self.assertEqual(websocket.messages, [])
        self.assertIn("providers=codex", str(ctx.exception))

    async def test_responses_websocket_upstream_error_after_output_is_sanitized(self):
        async def fake_iter(*_args, **_kwargs):
            yield {"type": "response.output_text.delta", "delta": "hello"}
            yield {
                "type": "error",
                "error": {"message": "providers=codex 上游中文错误"},
            }

        websocket = FakeWebSocket()
        channel = Channel(id=1, name="test")
        with patch.object(ProxyService, "_iter_responses_upstream_payloads", fake_iter):
            with self.assertRaises(ResponsesTurnError) as ctx:
                await ProxyService._forward_responses_websocket_turn(
                    websocket,
                    channel,
                    {"model": "actual-model"},
                    "requested-model",
                )

        self.assertFalse(ctx.exception.can_retry)
        self.assertEqual(len(websocket.messages), 2)
        error_payload = json.loads(websocket.messages[1])
        self.assertEqual(error_payload["error"]["message"], "调用失败，渠道异常，请稍后重试")
        self.assertNotIn("providers=codex", websocket.messages[1])
        self.assertIn("providers=codex", getattr(ctx.exception, "_upstream_detail"))


if __name__ == "__main__":
    unittest.main()
