import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.exceptions import ServiceException
from app.services.google_vertex_image_service import GoogleVertexImageService
from app.services.proxy_service import ProxyService


class _MockAsyncClient:
    responses = []
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        type(self).calls += 1
        item = type(self).responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def stream(self, *args, **kwargs):
        type(self).calls += 1
        item = type(self).responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _MockStreamResponse:
    def __init__(self, status_code: int = 200, lines=None, body: bytes = b"", line_error: Exception | None = None):
        self.status_code = status_code
        self._lines = list(lines or [])
        self._body = body
        self._line_error = line_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aread(self):
        return self._body

    async def aiter_lines(self):
        for line in self._lines:
            yield line
            if self._line_error is not None:
                raise self._line_error


def _response(status_code: int, payload: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload or {"ok": True},
        request=httpx.Request("POST", "https://upstream.test/v1"),
    )


class ProxyRetryMechanismTest(unittest.TestCase):
    def setUp(self):
        _MockAsyncClient.responses = []
        _MockAsyncClient.calls = 0
        self.channel = SimpleNamespace(id=11, name="retry-channel")

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_json_post_retries_three_failures_then_succeeds(self, _sleep):
        _MockAsyncClient.responses = [
            _response(503),
            _response(502),
            httpx.ReadTimeout("temporary read timeout"),
            _response(200, {"ok": True}),
        ]

        result = asyncio.run(ProxyService._post_with_retries(
            "https://upstream.test/v1",
            {"model": "x"},
            {},
            request_id="req-1",
            channel=self.channel,
            timeout=httpx.Timeout(1.0),
            log_label="test",
        ))

        self.assertEqual(result.status_code, 200)
        self.assertEqual(_MockAsyncClient.calls, 4)
        self.assertEqual(_sleep.call_count, 3)

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_json_post_does_not_retry_non_retryable_status(self, _sleep):
        _MockAsyncClient.responses = [_response(400)]

        result = asyncio.run(ProxyService._post_with_retries(
            "https://upstream.test/v1",
            {"model": "x"},
            {},
            request_id="req-2",
            channel=self.channel,
            timeout=httpx.Timeout(1.0),
            log_label="test",
        ))

        self.assertEqual(result.status_code, 400)
        self.assertEqual(_MockAsyncClient.calls, 1)
        self.assertEqual(_sleep.call_count, 0)

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_multipart_post_retries_retryable_status(self, _sleep):
        _MockAsyncClient.responses = [_response(500), _response(200, {"ok": True})]

        result = asyncio.run(ProxyService._post_files_with_retries(
            "https://upstream.test/images/edits",
            [("image", ("a.png", b"data", "image/png"))],
            {},
            request_id="req-3",
            channel=self.channel,
            timeout=httpx.Timeout(1.0),
            log_label="test-files",
        ))

        self.assertEqual(result.status_code, 200)
        self.assertEqual(_MockAsyncClient.calls, 2)
        self.assertEqual(_sleep.call_count, 1)

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_stream_retries_before_first_line_then_succeeds(self, _sleep):
        _MockAsyncClient.responses = [
            _MockStreamResponse(503, body=b"temporary"),
            httpx.ConnectError("connect failed"),
            _MockStreamResponse(200, lines=["data: ok", "data: [DONE]"]),
        ]

        async def collect_lines():
            return [
                line async for line in ProxyService._stream_lines_with_retries(
                    "https://upstream.test/stream",
                    {"stream": True},
                    {},
                    request_id="req-stream-1",
                    channel=self.channel,
                    timeout=httpx.Timeout(1.0),
                    log_label="test-stream",
                )
            ]

        lines = asyncio.run(collect_lines())

        self.assertEqual(lines, ["data: ok", "data: [DONE]"])
        self.assertEqual(_MockAsyncClient.calls, 3)
        self.assertEqual(_sleep.call_count, 2)

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_stream_does_not_retry_after_first_line(self, _sleep):
        _MockAsyncClient.responses = [
            _MockStreamResponse(
                200,
                lines=["data: first"],
                line_error=httpx.ReadError("stream interrupted"),
            ),
            _MockStreamResponse(200, lines=["data: should-not-run"]),
        ]

        async def collect_lines():
            lines = []
            with self.assertRaises(httpx.ReadError):
                async for line in ProxyService._stream_lines_with_retries(
                    "https://upstream.test/stream",
                    {"stream": True},
                    {},
                    request_id="req-stream-2",
                    channel=self.channel,
                    timeout=httpx.Timeout(1.0),
                    log_label="test-stream",
                ):
                    lines.append(line)
            return lines

        lines = asyncio.run(collect_lines())

        self.assertEqual(lines, ["data: first"])
        self.assertEqual(_MockAsyncClient.calls, 1)
        self.assertEqual(_sleep.call_count, 0)

    @patch("app.services.proxy_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.services.proxy_service.httpx.AsyncClient", _MockAsyncClient)
    def test_stream_retries_after_ignored_non_payload_line(self, _sleep):
        _MockAsyncClient.responses = [
            _MockStreamResponse(
                200,
                lines=["event: response.created"],
                line_error=httpx.ReadError("stream interrupted before payload"),
            ),
            _MockStreamResponse(200, lines=['data: {"type":"response.completed"}']),
        ]

        async def collect_payload_lines():
            lines = []
            async for line in ProxyService._stream_lines_with_retries(
                "https://upstream.test/responses",
                {"stream": True},
                {},
                request_id="req-stream-3",
                channel=self.channel,
                timeout=httpx.Timeout(1.0),
                log_label="test-stream",
                retry_boundary=ProxyService._is_responses_stream_retry_boundary,
            ):
                if ProxyService._parse_responses_payload_line(line):
                    lines.append(line)
            return lines

        lines = asyncio.run(collect_payload_lines())

        self.assertEqual(lines, ['data: {"type":"response.completed"}'])
        self.assertEqual(_MockAsyncClient.calls, 2)
        self.assertEqual(_sleep.call_count, 1)


class ImageRetryClassificationTest(unittest.TestCase):
    @patch("app.services.proxy_service.ProxyService._log_failed_request")
    @patch("app.services.proxy_service.ProxyService._record_channel_failure")
    @patch("app.services.proxy_service.ProxyService._non_stream_image_request")
    @patch("app.services.proxy_service.ProxyService._filter_channels_by_image_size")
    @patch("app.services.proxy_service.ModelService.get_available_channels")
    @patch("app.services.proxy_service.ProxyService._calculate_total_image_credits")
    @patch("app.services.proxy_service.ProxyService._resolve_image_billing_rule")
    @patch("app.services.proxy_service.ImageCreditService.check_balance")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    def test_image_generation_5xx_after_retries_records_channel_failure(
        self,
        mock_resolve_model,
        _check_balance,
        mock_resolve_billing_rule,
        mock_calculate_credits,
        mock_get_channels,
        mock_filter_channels,
        mock_non_stream_image_request,
        mock_record_channel_failure,
        _log_failed_request,
    ):
        channel = SimpleNamespace(id=21, name="image-channel")
        mock_resolve_model.return_value = SimpleNamespace(
            id=31,
            model_type="image",
            billing_type="image_credit",
        )
        mock_resolve_billing_rule.return_value = ("1024x1024", Decimal("1"))
        mock_calculate_credits.return_value = Decimal("1")
        mock_get_channels.return_value = [(channel, "upstream-image")]
        mock_filter_channels.return_value = [(channel, "upstream-image")]
        mock_non_stream_image_request.side_effect = ServiceException(
            503,
            "OpenAI 图片生成失败（HTTP 503）：temporary",
            "OPENAI_IMAGE_GENERATION_FAILED",
        )

        with self.assertRaises(ServiceException) as ctx:
            asyncio.run(ProxyService.handle_image_request(
                db=MagicMock(),
                user=SimpleNamespace(id=41),
                api_key_record=SimpleNamespace(id=51),
                request_data={
                    "model": "image-model",
                    "prompt": "draw",
                    "response_format": "b64_json",
                },
                client_ip="127.0.0.1",
            ))

        self.assertEqual(ctx.exception.error_code, "ALL_CHANNELS_FAILED")
        self.assertEqual(mock_record_channel_failure.call_count, 1)


class VertexImageRetryMechanismTest(unittest.TestCase):
    @patch("app.services.google_vertex_image_service.GoogleVertexImageService._sleep_before_retry_sync")
    @patch("app.services.google_vertex_image_service.GoogleVertexImageService._parse_gemini_response")
    @patch("app.services.google_vertex_image_service.GoogleVertexImageService._load_google_genai_modules")
    def test_vertex_candidate_retries_three_failures_then_succeeds(
        self,
        mock_load_modules,
        mock_parse_response,
        mock_sleep,
    ):
        client = MagicMock()
        client.models.generate_content.side_effect = [
            RuntimeError("temporary 1"),
            RuntimeError("temporary 2"),
            RuntimeError("temporary 3"),
            SimpleNamespace(candidates=[]),
        ]
        genai = SimpleNamespace(Client=MagicMock(return_value=client))
        types_module = SimpleNamespace(GenerateContentConfig=MagicMock())
        mock_load_modules.return_value = (genai, types_module)
        mock_parse_response.return_value = ([{"b64_json": "abc", "mime_type": "image/png"}], None)

        images, _extra_text, used_model = GoogleVertexImageService._generate_images_sync(
            "key",
            ["gemini-image"],
            "prompt",
            None,
            None,
        )

        self.assertEqual(used_model, "gemini-image")
        self.assertEqual(len(images), 1)
        self.assertEqual(client.models.generate_content.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)

    @patch("app.services.google_vertex_image_service.GoogleVertexImageService._sleep_before_retry_sync")
    @patch("app.services.google_vertex_image_service.GoogleVertexImageService._load_google_genai_modules")
    def test_vertex_candidate_does_not_retry_non_retryable_service_exception(
        self,
        mock_load_modules,
        mock_sleep,
    ):
        client = MagicMock()
        client.models.generate_content.side_effect = ServiceException(
            400,
            "bad request",
            "BAD_REQUEST",
        )
        genai = SimpleNamespace(Client=MagicMock(return_value=client))
        types_module = SimpleNamespace(GenerateContentConfig=MagicMock())
        mock_load_modules.return_value = (genai, types_module)

        with self.assertRaises(ServiceException):
            GoogleVertexImageService._generate_images_sync(
                "key",
                ["gemini-image"],
                "prompt",
                None,
                None,
            )

        self.assertEqual(client.models.generate_content.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)


if __name__ == "__main__":
    unittest.main()
