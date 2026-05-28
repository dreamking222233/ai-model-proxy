import unittest
from types import SimpleNamespace

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

        db = SimpleNamespace(query=lambda *_args, **_kwargs: None)
        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_stored_video_route(db, SimpleNamespace(id=99), "video_test")
        self.assertEqual(ctx.exception.error_code, "VIDEO_TASK_FORBIDDEN")

    def test_model_service_video_capabilities(self):
        self.assertIn(
            "1792x1024",
            ModelService.get_video_size_capabilities("grok-imagine-video"),
        )


if __name__ == "__main__":
    unittest.main()
