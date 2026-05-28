import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.core.exceptions import ServiceException
from app.services.model_service import ModelService
from app.services.proxy_service import ProxyService


class GrokVideoProxyTest(unittest.TestCase):
    def setUp(self):
        ProxyService._video_task_routes.clear()

    def tearDown(self):
        ProxyService._video_task_routes.clear()

    def test_video_create_url_respects_v1_base_url(self):
        self.assertEqual(
            ProxyService._resolve_openai_video_create_url("https://grok.example/v1"),
            "https://grok.example/v1/videos",
        )
        self.assertEqual(
            ProxyService._resolve_openai_video_create_url("https://grok.example"),
            "https://grok.example/v1/videos",
        )
        self.assertEqual(
            ProxyService._resolve_openai_chat_completions_url("https://grok.example/v1"),
            "https://grok.example/v1/chat/completions",
        )

    def test_video_parameter_validation(self):
        self.assertEqual(ProxyService._normalize_video_seconds("10"), 10)
        self.assertEqual(ProxyService._normalize_video_size("1792x1024"), "1792x1024")
        self.assertEqual(ProxyService._normalize_video_resolution_name("720p"), "720p")
        self.assertEqual(ProxyService._normalize_video_preset("normal"), "normal")
        self.assertEqual(ProxyService._video_size_for_failure_log("1280x720"), "1280x720")
        self.assertIsNone(ProxyService._video_size_for_failure_log("1920x1080"))

        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_seconds("9")
        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_size("1920x1080")

    def test_video_route_storage_enforces_owner(self):
        ProxyService._store_video_task_route(
            "video_test",
            user_id=1,
            channel_id=2,
            requested_model="grok-imagine-video",
            actual_model="grok-imagine-video",
        )

        db = SimpleNamespace()
        with patch.object(ProxyService, "_resolve_video_route_from_request_log", return_value=None):
            with self.assertRaises(ServiceException) as ctx:
                ProxyService._resolve_stored_video_route(db, SimpleNamespace(id=99), "video_test")
        self.assertEqual(ctx.exception.error_code, "VIDEO_TASK_FORBIDDEN")

    def test_model_service_video_capabilities(self):
        self.assertIn(
            "1792x1024",
            ModelService.get_video_size_capabilities("grok-imagine-video"),
        )

    def test_video_credit_cost_uses_per_second_rate(self):
        rate, total = ProxyService._resolve_video_credit_cost(
            SimpleNamespace(image_credit_multiplier=Decimal("0.500")),
            10,
        )

        self.assertEqual(rate, Decimal("0.500"))
        self.assertEqual(total, Decimal("5.000"))

    def test_video_wait_status_helpers(self):
        self.assertTrue(ProxyService._is_video_completed_status("completed"))
        self.assertTrue(ProxyService._is_video_completed_status("SUCCEEDED"))
        self.assertTrue(ProxyService._is_video_failed_status("failed"))
        self.assertTrue(ProxyService._is_video_failed_status("CANCELLED"))
        self.assertEqual(
            ProxyService._video_status_value({"state": "in_progress"}),
            "in_progress",
        )

    def test_video_chat_helpers_extract_prompt_and_config(self):
        request_data = {
            "messages": [
                {"role": "system", "content": "电影感"},
                {"role": "user", "content": [{"type": "text", "text": "霓虹雨夜街头"}]},
            ],
            "video_config": {
                "seconds": 10,
                "size": "1792x1024",
                "resolution_name": "720p",
                "preset": "normal",
            },
        }

        self.assertEqual(
            ProxyService._extract_video_prompt_from_chat_messages(request_data),
            "电影感\n霓虹雨夜街头",
        )
        self.assertEqual(
            ProxyService._video_config_from_chat_request(request_data)["size"],
            "1792x1024",
        )

    def test_extract_video_url_from_text(self):
        self.assertEqual(
            ProxyService._extract_video_url_from_text("done https://cdn.example/video.mp4?x=1"),
            "https://cdn.example/video.mp4?x=1",
        )


class GrokVideoWaitTest(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_video_completion_returns_final_status(self):
        responses = [
            SimpleNamespace(status_code=200, json=lambda: {"status": "in_progress", "progress": 1}),
            SimpleNamespace(status_code=200, json=lambda: {"status": "completed", "progress": 100}),
        ]

        async def fake_request_video_route(*_args, **_kwargs):
            return responses.pop(0)

        with patch.object(
            ProxyService,
            "_resolve_stored_video_route",
            return_value=(SimpleNamespace(base_url="https://grok.example"), "grok-imagine-video", "grok-imagine-video"),
        ), patch.object(
            ProxyService,
            "_request_video_route",
            side_effect=fake_request_video_route,
        ):
            final_status, elapsed = await ProxyService._wait_for_video_completion(
                SimpleNamespace(),
                SimpleNamespace(id=1),
                "video_test",
                poll_interval_seconds=0.1,
                timeout_seconds=2,
            )

        self.assertEqual(final_status["status"], "completed")
        self.assertGreaterEqual(elapsed, 0)

    async def test_wait_for_video_completion_raises_on_failed_status(self):
        async def fake_request_video_route(*_args, **_kwargs):
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"status": "failed", "message": "blocked"},
            )

        with patch.object(
            ProxyService,
            "_resolve_stored_video_route",
            return_value=(SimpleNamespace(base_url="https://grok.example"), "grok-imagine-video", "grok-imagine-video"),
        ), patch.object(
            ProxyService,
            "_request_video_route",
            side_effect=fake_request_video_route,
        ):
            with self.assertRaises(ServiceException) as ctx:
                await ProxyService._wait_for_video_completion(
                    SimpleNamespace(),
                    SimpleNamespace(id=1),
                    "video_test",
                    poll_interval_seconds=0.1,
                    timeout_seconds=2,
                )

        self.assertEqual(ctx.exception.error_code, "VIDEO_GENERATION_FAILED")


if __name__ == "__main__":
    unittest.main()
