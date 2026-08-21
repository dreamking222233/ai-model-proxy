import unittest
from decimal import Decimal

import httpx

from app.core.exceptions import ServiceException
from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.services.channel_service import ChannelService
from app.services.proxy_service import ProxyService


class Zz1ccVideoChannelTest(unittest.IsolatedAsyncioTestCase):
    def test_channel_variant_is_allowed_and_health_check_disabled(self):
        self.assertEqual(
            ChannelService._normalize_provider_variant("openai", "zz1cc-video"),
            "zz1cc-video",
        )
        self.assertEqual(
            ChannelService._resolve_default_health_check_enabled("openai", "zz1cc-video"),
            0,
        )
        self.assertEqual(ChannelService.get_openai_image_channel_capabilities("zz1cc-video"), ())

    def test_zz1cc_seconds_default_to_15_and_only_accept_15(self):
        channel = Channel(protocol_type="openai", provider_variant="zz1cc-video")

        self.assertEqual(ProxyService._normalize_video_seconds(None, channel), 15)
        self.assertEqual(ProxyService._normalize_video_seconds("", channel), 15)
        self.assertEqual(ProxyService._normalize_video_seconds(15, channel), 15)
        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_seconds(10, channel)

    def test_zz1cc_size_and_aspect_ratio_mapping(self):
        channel = Channel(protocol_type="openai", provider_variant="zz1cc-video")

        self.assertEqual(ProxyService._normalize_video_size("720x1280", channel), "720x1280")
        self.assertEqual(ProxyService._normalize_video_size("1920x1080", channel), "1920x1080")
        self.assertEqual(ProxyService._zz1cc_video_aspect_ratio("720x1280"), "9:16")
        self.assertEqual(ProxyService._zz1cc_video_aspect_ratio("1024x1792"), "9:16")
        self.assertEqual(ProxyService._zz1cc_video_aspect_ratio("1024x1024"), "1:1")
        self.assertEqual(ProxyService._zz1cc_video_aspect_ratio("1920x1080"), "16:9")

    def test_zz1cc_url_helpers_accept_root_or_v1_base_url(self):
        self.assertEqual(
            ProxyService._resolve_zz1cc_video_create_url("https://zz1cc.cc.cd"),
            "https://zz1cc.cc.cd/v1/videos",
        )
        self.assertEqual(
            ProxyService._resolve_zz1cc_video_create_url("https://zz1cc.cc.cd/v1"),
            "https://zz1cc.cc.cd/v1/videos",
        )
        self.assertEqual(
            ProxyService._resolve_zz1cc_video_content_url("https://zz1cc.cc.cd/v1", "task-1"),
            "https://zz1cc.cc.cd/v1/videos/task-1/content",
        )

    def test_zz1cc_response_normalizes_task_id_and_status(self):
        normalized = ProxyService._normalize_zz1cc_video_response(
            {
                "task_id": "task-123",
                "request_id": "upstream-request",
                "status": "done",
                "progress": 100,
                "aspect_ratio": "9:16",
            },
            model="video-ds-2.0-fast",
            prompt="test prompt",
            seconds=15,
            size="720x1280",
        )

        self.assertEqual(normalized["id"], "task-123")
        self.assertEqual(normalized["task_id"], "task-123")
        self.assertEqual(normalized["upstream_request_id"], "upstream-request")
        self.assertEqual(normalized["status"], "completed")
        self.assertEqual(normalized["seconds"], "15")
        self.assertEqual(normalized["aspect_ratio"], "9:16")

    def test_zz1cc_error_response_is_normalized_to_failed(self):
        normalized = ProxyService._normalize_zz1cc_video_response(
            {
                "id": "task-err",
                "status": "expired",
                "error": {"message": "failed"},
            }
        )

        self.assertEqual(normalized["id"], "task-err")
        self.assertEqual(normalized["status"], "failed")
        self.assertIn("error", normalized)

    def test_video_reference_requires_image_mime_type(self):
        data_url = ProxyService._video_reference_to_data_url({
            "content": b"abc",
            "content_type": "image/png",
        })
        self.assertTrue(data_url.startswith("data:image/png;base64,"))

        with self.assertRaises(ServiceException):
            ProxyService._video_reference_to_data_url({
                "content": b"abc",
                "content_type": "video/mp4",
            })

    async def test_zz1cc_route_content_validation_uses_content_url(self):
        channel = Channel(
            name="zz1cc",
            base_url="https://zz1cc.cc.cd/v1",
            api_key="sk-test",
            protocol_type="openai",
            provider_variant="zz1cc-video",
            auth_header_type="authorization",
        )
        captured = {}
        original = ProxyService._validate_video_url_content_or_raise

        async def fake_validate(_channel, video_url, *, request_headers=None):
            captured["video_url"] = video_url

        ProxyService._validate_video_url_content_or_raise = staticmethod(fake_validate)
        try:
            await ProxyService._validate_video_route_content_or_raise(channel, "task-123")
        finally:
            ProxyService._validate_video_url_content_or_raise = original

        self.assertEqual(captured["video_url"], "https://zz1cc.cc.cd/v1/videos/task-123/content")

    async def test_zz1cc_query_error_body_forces_failed_status(self):
        channel = Channel(
            name="zz1cc",
            base_url="https://zz1cc.cc.cd/v1",
            api_key="sk-test",
            protocol_type="openai",
            provider_variant="zz1cc-video",
            auth_header_type="authorization",
        )
        original_client = httpx.AsyncClient

        class FakeResponse:
            status_code = 422
            text = '{"status":"invalid_task","message":"not found"}'

            def json(self):
                return {"status": "invalid_task", "message": "not found"}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None):
                return FakeResponse()

        httpx.AsyncClient = FakeClient
        try:
            body = await ProxyService._request_zz1cc_video_status(channel, "missing-task")
        finally:
            httpx.AsyncClient = original_client

        self.assertEqual(body["status"], "failed")
        self.assertNotIn("progress", body)

    async def test_zz1cc_query_network_error_is_wrapped(self):
        channel = Channel(
            name="zz1cc",
            base_url="https://zz1cc.cc.cd/v1",
            api_key="sk-test",
            protocol_type="openai",
            provider_variant="zz1cc-video",
            auth_header_type="authorization",
        )
        original_client = httpx.AsyncClient

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None):
                raise httpx.ConnectError("connect failed")

        httpx.AsyncClient = FakeClient
        try:
            with self.assertRaises(ServiceException) as ctx:
                await ProxyService._request_zz1cc_video_status(channel, "task-123")
        finally:
            httpx.AsyncClient = original_client

        self.assertEqual(ctx.exception.error_code, "OPENAI_VIDEO_RETRIEVE_FAILED")

    async def test_zz1cc_video_create_uses_multipart_input_reference(self):
        channel = Channel(
            id=45,
            name="zz1cc",
            base_url="https://zz1cc.cc.cd/v1",
            api_key="sk-test",
            protocol_type="openai",
            provider_variant="zz1cc-video",
            auth_header_type="authorization",
        )
        user = SysUser(id=1, agent_id=None)
        api_key_record = UserApiKey(id=2, user_id=1)
        model = UnifiedModel(
            id=3,
            model_name="video-ds-2.0-fast",
            model_type="video",
            billing_type="free",
        )
        request_data = {
            "prompt": "test prompt",
            "_normalized_video_seconds": 15,
            "_normalized_video_size": "1280x720",
            "input_references": [
                {
                    "filename": "reference.png",
                    "content": b"fake-image",
                    "content_type": "image/png",
                }
            ],
        }
        captured = {}
        original_post_files = ProxyService._post_files_with_retries
        original_post_json = ProxyService._post_with_retries
        original_record_success = ProxyService._record_success
        original_store_route = ProxyService._store_video_task_route

        class FakeResponse:
            status_code = 200
            text = '{"task_id":"task-123","status":"queued"}'

            def json(self):
                return {"task_id": "task-123", "status": "queued"}

        async def fake_post_files(url, files, headers, **kwargs):
            captured["url"] = url
            captured["files"] = files
            captured["headers"] = headers
            return FakeResponse()

        async def fake_post_json(*args, **kwargs):
            raise AssertionError("zz1cc reference image create must use multipart")

        ProxyService._post_files_with_retries = staticmethod(fake_post_files)
        ProxyService._post_with_retries = staticmethod(fake_post_json)
        ProxyService._record_success = staticmethod(lambda *args, **kwargs: None)
        ProxyService._store_video_task_route = staticmethod(lambda *args, **kwargs: None)
        try:
            response = await ProxyService._non_stream_zz1cc_video_request(
                db=None,
                user=user,
                api_key_record=api_key_record,
                channel=channel,
                unified_model=model,
                request_data=request_data,
                request_id="request-123",
                requested_model="video-ds-2.0-fast",
                upstream_model_name="video-ds-2.0-fast",
                client_ip="127.0.0.1",
                charged_credits=Decimal("0"),
                model_multiplier=Decimal("0"),
            )
        finally:
            ProxyService._post_files_with_retries = original_post_files
            ProxyService._post_with_retries = original_post_json
            ProxyService._record_success = original_record_success
            ProxyService._store_video_task_route = original_store_route

        field_names = [item[0] for item in captured["files"]]
        self.assertEqual(captured["url"], "https://zz1cc.cc.cd/v1/videos")
        self.assertIn("input_reference", field_names)
        self.assertNotIn("input_reference[]", field_names)
        self.assertNotIn("images", field_names)
        self.assertNotIn("Content-Type", captured["headers"])
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
