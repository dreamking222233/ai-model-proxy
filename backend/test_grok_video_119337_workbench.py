import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.core.exceptions import ServiceException
from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.services.image_credit_service import ImageCreditService
from app.services.model_service import ModelService
from app.services.proxy_service import ProxyService


def image_reference(name="reference.png"):
    return {
        "filename": name,
        "content_type": "image/png",
        "content": b"png-bytes",
    }


class GrokVideo119337WorkbenchTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.channel = Channel(
            id=119337,
            name="119337",
            base_url="https://api.119337.xyz",
            api_key="test-key",
            protocol_type="openai",
            provider_variant="grok-video-119337",
            auth_header_type="authorization",
            enabled=1,
            is_healthy=1,
        )

    def test_url_helpers_accept_root_or_v1_base(self):
        self.assertEqual(
            ProxyService._resolve_grok_video_119337_create_url("https://api.119337.xyz"),
            "https://api.119337.xyz/v1/video/generations",
        )
        self.assertEqual(
            ProxyService._resolve_grok_video_119337_create_url("https://api.119337.xyz/v1"),
            "https://api.119337.xyz/v1/video/generations",
        )
        self.assertEqual(
            ProxyService._resolve_grok_video_119337_retrieve_url(
                "https://api.119337.xyz/v1", "task-1"
            ),
            "https://api.119337.xyz/v1/video/generations/task-1",
        )

    def test_common_model_without_reference_keeps_15_seconds(self):
        options = ProxyService._normalize_grok_video_119337_request_options(
            "grok-image-video",
            {"aspect_ratio": "4:3", "input_references": []},
            seconds=15,
            size="960x720",
            resolution_name="720p",
        )
        self.assertEqual(options["seconds"], 15)
        self.assertEqual(options["aspect_ratio"], "4:3")
        self.assertEqual(options["size"], "960x720")

    def test_common_model_any_reference_caps_at_10_seconds(self):
        options = ProxyService._normalize_grok_video_119337_request_options(
            "grok-image-video",
            {"aspect_ratio": "9:16", "input_references": [image_reference()]},
            seconds=15,
            size="720x1280",
            resolution_name="480p",
        )
        self.assertEqual(options["seconds"], 10)
        self.assertEqual(options["aspect_ratio"], "9:16")
        self.assertEqual(options["resolution_name"], "480p")

    def test_preview_requires_exactly_one_reference_and_allows_15_seconds(self):
        with self.assertRaises(ServiceException):
            ProxyService._normalize_grok_video_119337_request_options(
                "grok-video-1.5",
                {"aspect_ratio": "16:9", "input_references": []},
                seconds=15,
                size="1280x720",
                resolution_name="720p",
            )
        with self.assertRaises(ServiceException):
            ProxyService._normalize_grok_video_119337_request_options(
                "grok-video-1.5",
                {"aspect_ratio": "16:9", "input_references": [image_reference("1.png"), image_reference("2.png")]},
                seconds=15,
                size="1280x720",
                resolution_name="720p",
            )

        options = ProxyService._normalize_grok_video_119337_request_options(
            "grok-video-1.5",
            {"aspect_ratio": "16:9", "input_references": [image_reference()]},
            seconds=15,
            size="1280x720",
            resolution_name="720p",
        )
        self.assertEqual(options["seconds"], 15)
        self.assertEqual(options["reference_count"], 1)

    def test_preview_rejects_unsupported_ratio(self):
        with self.assertRaises(ServiceException):
            ProxyService._normalize_grok_video_119337_request_options(
                "grok-video-1.5",
                {"aspect_ratio": "1:1", "input_references": [image_reference()]},
                seconds=10,
                size="1024x1024",
                resolution_name="720p",
            )

    def test_reference_video_is_rejected_instead_of_sent_as_image_url(self):
        with self.assertRaises(ServiceException):
            ProxyService._video_reference_to_data_url({
                "filename": "reference.mp4",
                "content_type": "video/mp4",
                "content": b"video-bytes",
            })

    def test_failure_progress_100_is_still_failed(self):
        normalized = ProxyService._normalize_grok_video_119337_response({
            "code": "success",
            "data": {
                "task_id": "task-failed",
                "status": "FAILURE",
                "progress": "100%",
                "result_url": "",
                "fail_reason": "image fetch failed",
            },
        })
        self.assertEqual(normalized["status"], "failed")
        self.assertEqual(normalized["error"]["message"], "image fetch failed")

    def test_completed_without_result_url_is_not_reported_completed(self):
        normalized = ProxyService._normalize_grok_video_119337_response({
            "data": {"task_id": "task-empty", "status": "SUCCESS", "progress": "100%"},
        })
        self.assertEqual(normalized["status"], "in_progress")

    def test_video_normalizers_do_not_fabricate_missing_progress(self):
        responses = (
            ProxyService._normalize_grok_video_119337_response({
                "data": {"task_id": "task-119337", "status": "IN_PROGRESS"},
            }),
            ProxyService._normalize_zz1cc_video_response({
                "id": "task-zz1cc", "status": "processing",
            }),
            ProxyService._normalize_cpa_grok_video_response({
                "request_id": "task-cpa", "status": "processing",
            }),
        )
        for response in responses:
            self.assertNotIn("progress", response)

        explicit = ProxyService._normalize_grok_video_119337_response({
            "data": {"task_id": "task-progress", "status": "IN_PROGRESS", "progress": "35%"},
        })
        self.assertEqual(explicit["progress"], "35%")

    async def test_119337_query_error_does_not_fabricate_progress(self):
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
            body = await ProxyService._request_grok_video_119337_status(self.channel, "missing-task")
        finally:
            httpx.AsyncClient = original_client

        self.assertEqual(body["status"], "FAILURE")
        self.assertNotIn("progress", body)

    def test_model_capabilities_are_channel_aware_and_merge_conservatively(self):
        common = ModelService.resolve_video_workbench_capabilities(
            "grok-video",
            provider_variant="grok-video-119337",
            actual_model_name="grok-image-video",
        )
        preview = ModelService.resolve_video_workbench_capabilities(
            "grok-imagine-video-1.5-preview",
            provider_variant="grok-video-119337",
            actual_model_name="grok-video-1.5",
        )
        self.assertEqual(common["seconds_options_without_reference"], [4, 6, 8, 10, 12, 15])
        self.assertEqual(common["seconds_options_with_reference"], [4, 6, 8, 10])
        self.assertFalse(preview["supports_text_to_video"])
        self.assertEqual(preview["reference_max_count"], 1)

        merged = ModelService.merge_video_workbench_capabilities([common, preview])
        self.assertFalse(merged["supports_text_to_video"])
        self.assertTrue(merged["reference_required"])
        self.assertEqual(merged["reference_max_count"], 1)
        self.assertEqual(merged["aspect_ratio_options"], ["16:9", "9:16"])

        default_channel = ModelService.resolve_video_workbench_capabilities(
            "grok-video",
            provider_variant="default",
            actual_model_name="grok-imagine-video",
        )
        cpa_channel = ModelService.resolve_video_workbench_capabilities(
            "grok-video",
            provider_variant="cpa-grok-video",
            actual_model_name="grok-imagine-video",
        )
        self.assertEqual(default_channel["seconds_options_without_reference"], [6, 10, 12, 16, 20])
        self.assertEqual(cpa_channel["seconds_options_without_reference"], list(range(1, 16)))

    async def test_handle_video_calculates_price_from_final_capped_seconds(self):
        unified_model = UnifiedModel(
            id=53,
            model_name="grok-video",
            model_type="video",
            billing_type="image_credit",
            image_credit_multiplier=Decimal("0.500"),
            enabled=1,
        )
        user = SysUser(id=7)
        api_key = UserApiKey(id=9, user_id=7)
        captured = {}

        def resolve_price(_db, _model, seconds, **_kwargs):
            captured["priced_seconds"] = seconds
            return (
                Decimal("0.500"),
                Decimal(str(seconds)) * Decimal("0.500"),
                SimpleNamespace(multiplier=Decimal("1"), source=None, rule_id=None),
            )

        async def run_without_guard(_db, _decision, _request_id, producer):
            return await producer()

        async def fake_upstream(*args, **_kwargs):
            captured["request_data"] = args[5]
            captured["charged_credits"] = args[10]
            return {"ok": True}

        request_data = {
            "model": "grok-video",
            "prompt": "animate",
            "seconds": 15,
            "size": "1280x720",
            "aspect_ratio": "16:9",
            "resolution_name": "720p",
            "input_references": [image_reference()],
        }

        with patch.object(ProxyService, "_resolve_requested_model_or_raise", return_value=unified_model), \
             patch.object(ProxyService, "_maybe_create_security_snapshot", return_value=(None, None)), \
             patch.object(ProxyService, "_maybe_scan_security_request_or_raise", return_value=None), \
             patch.object(ModelService, "get_available_channels", return_value=[(self.channel, "grok-image-video")]), \
             patch.object(ProxyService, "_apply_runtime_retry_config", return_value=None), \
             patch.object(ProxyService, "_resolve_adjusted_video_credit_cost", side_effect=resolve_price), \
             patch.object(ImageCreditService, "check_balance", return_value=None), \
             patch.object(ProxyService, "_run_with_billing_concurrency", new=run_without_guard), \
             patch.object(ProxyService, "_non_stream_grok_video_119337_request", new=fake_upstream):
            result = await ProxyService.handle_video_request(
                object(), user, api_key, request_data, "127.0.0.1"
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["priced_seconds"], 10)
        self.assertEqual(captured["request_data"]["_normalized_video_seconds"], 10)
        self.assertEqual(captured["charged_credits"], Decimal("5.000"))


if __name__ == "__main__":
    unittest.main()
