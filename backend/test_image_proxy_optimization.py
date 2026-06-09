import base64
import json
import unittest
from decimal import Decimal
from types import SimpleNamespace

import httpx

from app.core.exceptions import ServiceException
from app.services import proxy_service as proxy_module
from app.services.proxy_service import ProxyService


_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfeA\xe2&\xb3\x00\x00\x00\x00IEND\xaeB`\x82"
)


class _EmptyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _EmptyDb:
    def query(self, *_args, **_kwargs):
        return _EmptyQuery()


class _FixedQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.value


class _FixedDb:
    def __init__(self, value):
        self.value = value

    def query(self, *_args, **_kwargs):
        return _FixedQuery(self.value)


class ImageProxyOptimizationTest(unittest.IsolatedAsyncioTestCase):
    def test_openai_image_parser_filters_invalid_base64(self):
        valid_b64 = base64.b64encode(_PNG_1X1).decode("ascii")
        images, extra_text, invalid_count = ProxyService._parse_openai_image_response({
            "data": [
                {"b64_json": valid_b64, "revised_prompt": "ok"},
                {"b64_json": base64.b64encode(b"not an image").decode("ascii")},
                {"b64_json": "not-base64"},
            ]
        })

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["mime_type"], "image/png")
        self.assertEqual(images[0]["revised_prompt"], "ok")
        self.assertEqual(extra_text, "ok")
        self.assertEqual(invalid_count, 2)

    def test_responses_image_request_requires_tool_model_for_text_model(self):
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._build_image_request_from_responses(
                _EmptyDb(),
                {
                    "model": "gpt-5.4-mini",
                    "input": "画一张图",
                    "tools": [{"type": "image_generation"}],
                },
            )

        self.assertEqual(ctx.exception.error_code, "RESPONSES_IMAGE_MODEL_REQUIRED")

    def test_responses_image_request_uses_tool_model_and_prompt(self):
        image_request = ProxyService._build_image_request_from_responses(
            SimpleNamespace(),
            {
                "model": "gpt-5.4-mini",
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "生成 9:16 竖图"}],
                    }
                ],
                "tools": [{
                    "type": "image_generation",
                    "model": "gpt-image-2",
                    "image_size": "2K",
                    "aspect_ratio": "9:16",
                    "quality": "high",
                    "n": 1,
                }],
            },
        )

        self.assertEqual(image_request["model"], "gpt-image-2")
        self.assertEqual(image_request["prompt"], "生成 9:16 竖图")
        self.assertEqual(image_request["image_size"], "2K")
        self.assertEqual(image_request["aspect_ratio"], "9:16")

    def test_responses_image_request_uses_image_model_directly(self):
        image_model = SimpleNamespace(
            model_name="gpt-image-2",
            model_type="image",
            billing_type="image_credit",
        )

        image_request = ProxyService._build_image_request_from_responses(
            _FixedDb(image_model),
            {
                "model": "responses:gpt-image-2",
                "input": "生成一张 9:16 竖屏 2K 图片",
                "image_size": "2K",
                "aspect_ratio": "9:16",
                "stream": False,
            },
        )

        self.assertEqual(image_request["model"], "gpt-image-2")
        self.assertEqual(image_request["prompt"], "生成一张 9:16 竖屏 2K 图片")
        self.assertEqual(image_request["image_size"], "2K")
        self.assertEqual(image_request["aspect_ratio"], "9:16")

    async def test_openai_image_route_fallback_only_on_404(self):
        calls = []
        original = ProxyService._post_with_retries

        async def fake_post(url, payload, headers, **kwargs):
            calls.append(url)
            request = httpx.Request("POST", url)
            status_code = 404 if len(calls) == 1 else 200
            return httpx.Response(status_code, request=request)

        ProxyService._post_with_retries = staticmethod(fake_post)
        try:
            response, final_url = await ProxyService._post_openai_image_with_route_fallback(
                ["https://example.test/v1/images/generations", "https://example.test/v1/image/created"],
                {"model": "gpt-image-2", "prompt": "x"},
                {},
                request_id="req-test",
                channel=SimpleNamespace(name="test-channel", id=1),
                timeout=httpx.Timeout(1),
                log_label="test image",
            )
        finally:
            ProxyService._post_with_retries = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(final_url, "https://example.test/v1/image/created")
        self.assertEqual(calls, [
            "https://example.test/v1/images/generations",
            "https://example.test/v1/image/created",
        ])

    async def test_openai_image_edit_route_fallback_only_on_404(self):
        calls = []
        original = ProxyService._post_files_with_retries

        async def fake_post_files(url, files, headers, **kwargs):
            calls.append(url)
            request = httpx.Request("POST", url)
            status_code = 404 if len(calls) == 1 else 200
            return httpx.Response(status_code, request=request)

        ProxyService._post_files_with_retries = staticmethod(fake_post_files)
        try:
            response, final_url = await ProxyService._post_openai_image_files_with_route_fallback(
                ["https://example.test/v1/images/edits", "https://example.test/v1/image/edit"],
                [("image", ("image.png", b"png", "image/png"))],
                {},
                request_id="req-test",
                channel=SimpleNamespace(name="test-channel", id=1),
                timeout=httpx.Timeout(1),
                log_label="test image edit",
            )
        finally:
            ProxyService._post_files_with_retries = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(final_url, "https://example.test/v1/image/edit")
        self.assertEqual(calls, [
            "https://example.test/v1/images/edits",
            "https://example.test/v1/image/edit",
        ])

    async def test_openai_image_billing_uses_valid_image_count(self):
        valid_b64 = base64.b64encode(_PNG_1X1).decode("ascii")
        captured = {}
        original_release = proxy_module.release_session_connection
        original_post = ProxyService._post_openai_image_with_route_fallback
        original_headers = ProxyService._build_headers
        original_record_success = ProxyService._record_success
        original_deduct = ProxyService._deduct_image_credits_and_log

        async def fake_post(urls, payload, headers, **kwargs):
            request = httpx.Request("POST", urls[0])
            return (
                httpx.Response(
                    200,
                    json={
                        "data": [
                            {"b64_json": valid_b64, "revised_prompt": "ok"},
                            {"b64_json": base64.b64encode(b"not an image").decode("ascii")},
                        ]
                    },
                    request=request,
                ),
                urls[0],
            )

        def fake_deduct(*_args, **kwargs):
            captured.update(kwargs)

        proxy_module.release_session_connection = lambda _db: None
        ProxyService._post_openai_image_with_route_fallback = staticmethod(fake_post)
        ProxyService._build_headers = staticmethod(lambda *_args, **_kwargs: {})
        ProxyService._record_success = staticmethod(lambda *_args, **_kwargs: None)
        ProxyService._deduct_image_credits_and_log = staticmethod(fake_deduct)
        try:
            response = await ProxyService._non_stream_openai_image_request(
                db=SimpleNamespace(),
                user=SimpleNamespace(id=1),
                api_key_record=SimpleNamespace(id=1),
                channel=SimpleNamespace(
                    id=1,
                    name="openai-image",
                    base_url="https://example.test",
                    protocol_type="openai",
                    provider_variant="openai_image_native_size",
                ),
                unified_model=SimpleNamespace(id=1, model_name="gpt-image-2"),
                request_data={
                    "model": "gpt-image-2",
                    "prompt": "生成图片",
                    "n": 2,
                    "response_format": "b64_json",
                },
                request_id="req-test",
                requested_model="gpt-image-2",
                upstream_model_name="gpt-image-2",
                client_ip="127.0.0.1",
                charged_credits=Decimal("4"),
                requested_image_count=2,
                model_multiplier=Decimal("2"),
                image_size="2K",
            )
        finally:
            proxy_module.release_session_connection = original_release
            ProxyService._post_openai_image_with_route_fallback = original_post
            ProxyService._build_headers = original_headers
            ProxyService._record_success = original_record_success
            ProxyService._deduct_image_credits_and_log = original_deduct

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["usage"]["image_count"], 1)
        self.assertEqual(payload["usage"]["image_credits_charged"], 2.0)
        self.assertEqual(captured["image_count"], 1)
        self.assertEqual(captured["charged_credits"], Decimal("2"))

    async def test_openai_image_all_invalid_does_not_bill(self):
        billed = False
        original_release = proxy_module.release_session_connection
        original_post = ProxyService._post_openai_image_with_route_fallback
        original_headers = ProxyService._build_headers
        original_record_success = ProxyService._record_success
        original_deduct = ProxyService._deduct_image_credits_and_log

        async def fake_post(urls, payload, headers, **kwargs):
            request = httpx.Request("POST", urls[0])
            return (
                httpx.Response(
                    200,
                    json={"data": [{"b64_json": base64.b64encode(b"not an image").decode("ascii")}]},
                    request=request,
                ),
                urls[0],
            )

        def fake_deduct(*_args, **_kwargs):
            nonlocal billed
            billed = True

        proxy_module.release_session_connection = lambda _db: None
        ProxyService._post_openai_image_with_route_fallback = staticmethod(fake_post)
        ProxyService._build_headers = staticmethod(lambda *_args, **_kwargs: {})
        ProxyService._record_success = staticmethod(lambda *_args, **_kwargs: None)
        ProxyService._deduct_image_credits_and_log = staticmethod(fake_deduct)
        try:
            with self.assertRaises(ServiceException) as ctx:
                await ProxyService._non_stream_openai_image_request(
                    db=SimpleNamespace(),
                    user=SimpleNamespace(id=1),
                    api_key_record=SimpleNamespace(id=1),
                    channel=SimpleNamespace(
                        id=1,
                        name="openai-image",
                        base_url="https://example.test",
                        protocol_type="openai",
                        provider_variant="openai_image_native_size",
                    ),
                    unified_model=SimpleNamespace(id=1, model_name="gpt-image-2"),
                    request_data={
                        "model": "gpt-image-2",
                        "prompt": "生成图片",
                        "n": 1,
                        "response_format": "b64_json",
                    },
                    request_id="req-test",
                    requested_model="gpt-image-2",
                    upstream_model_name="gpt-image-2",
                    client_ip="127.0.0.1",
                    charged_credits=Decimal("2"),
                    requested_image_count=1,
                    model_multiplier=Decimal("2"),
                    image_size="2K",
                )
        finally:
            proxy_module.release_session_connection = original_release
            ProxyService._post_openai_image_with_route_fallback = original_post
            ProxyService._build_headers = original_headers
            ProxyService._record_success = original_record_success
            ProxyService._deduct_image_credits_and_log = original_deduct

        self.assertEqual(ctx.exception.error_code, "OPENAI_IMAGE_GENERATION_FAILED")
        self.assertFalse(billed)

    async def test_responses_image_stream_error_sends_done(self):
        original_execute = ProxyService._execute_responses_image_request

        async def fake_execute(*_args, **_kwargs):
            raise ServiceException(400, "上游图片结果无效", "OPENAI_IMAGE_GENERATION_FAILED")

        ProxyService._execute_responses_image_request = staticmethod(fake_execute)
        try:
            response = await ProxyService._handle_responses_image_request(
                db=SimpleNamespace(),
                user=SimpleNamespace(id=1),
                api_key_record=SimpleNamespace(id=1),
                request_data={
                    "model": "gpt-image-2",
                    "input": "生成图片",
                    "stream": True,
                },
                client_ip="127.0.0.1",
            )
            chunks = []
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    chunks.append(chunk.decode("utf-8"))
                else:
                    chunks.append(str(chunk))
        finally:
            ProxyService._execute_responses_image_request = original_execute

        stream_text = "".join(chunks)
        self.assertIn("response.created", stream_text)
        self.assertIn("event: error", stream_text)
        self.assertIn("上游图片结果无效", stream_text)
        self.assertTrue(stream_text.rstrip().endswith("data: [DONE]"))


if __name__ == "__main__":
    unittest.main()
