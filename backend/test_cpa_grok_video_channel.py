import unittest

from app.core.exceptions import ServiceException
from app.models.channel import Channel
from app.services.proxy_service import ProxyService


class CpaGrokVideoChannelTest(unittest.IsolatedAsyncioTestCase):
    def test_cpa_seconds_are_clamped_to_actual_billable_seconds(self):
        channel = Channel(protocol_type="openai", provider_variant="cpa-grok-video")

        self.assertEqual(ProxyService._normalize_video_seconds(None, channel), 4)
        self.assertEqual(ProxyService._normalize_video_seconds(0, channel), 1)
        self.assertEqual(ProxyService._normalize_video_seconds(30, channel), 15)
        self.assertEqual(ProxyService._normalize_video_seconds(12, channel), 12)

    def test_default_video_channel_keeps_legacy_seconds_validation(self):
        channel = Channel(protocol_type="openai", provider_variant="default")

        self.assertEqual(ProxyService._normalize_video_seconds(10, channel), 10)
        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_seconds(15, channel)

    def test_wait_billing_normalization_uses_cpa_channel_rules(self):
        channel = Channel(protocol_type="openai", provider_variant="cpa-grok-video")

        self.assertEqual(ProxyService._normalize_video_seconds(15, channel), 15)
        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_seconds(15)

    def test_cpa_video_size_maps_legacy_frontend_values(self):
        self.assertEqual(ProxyService._cpa_grok_video_size("1280x720"), "1280x720")
        self.assertEqual(ProxyService._cpa_grok_video_size("1792x1024"), "1920x1080")
        self.assertEqual(ProxyService._cpa_grok_video_size("1024x1024"), "1280x720")
        self.assertEqual(ProxyService._cpa_grok_video_size("720x1280"), "1280x720")

    def test_cpa_video_size_validation_accepts_cpa_native_sizes(self):
        cpa_channel = Channel(protocol_type="openai", provider_variant="cpa-grok-video")
        default_channel = Channel(protocol_type="openai", provider_variant="default")

        self.assertEqual(ProxyService._normalize_video_size("848x480", cpa_channel), "848x480")
        self.assertEqual(ProxyService._normalize_video_size("1696x960", cpa_channel), "1696x960")
        self.assertEqual(ProxyService._normalize_video_size("1920x1080", cpa_channel), "1920x1080")
        with self.assertRaises(ServiceException):
            ProxyService._normalize_video_size("1696x960", default_channel)

    def test_cpa_response_is_normalized_to_existing_video_shape(self):
        normalized = ProxyService._normalize_cpa_grok_video_response(
            {
                "request_id": "video-123",
                "status": "done",
                "progress": 100,
                "video": {
                    "url": "https://example.com/result.mp4",
                    "duration": 15,
                },
            },
            model="grok-imagine-video",
            prompt="test prompt",
            seconds=15,
            size="1280x720",
        )

        self.assertEqual(normalized["id"], "video-123")
        self.assertEqual(normalized["status"], "completed")
        self.assertEqual(normalized["video_url"], "https://example.com/result.mp4")
        self.assertEqual(normalized["seconds"], "15")
        self.assertEqual(normalized["size"], "1280x720")

    async def test_cpa_download_url_requires_completed_video_url(self):
        channel = Channel(
            name="CPA Grok",
            base_url="http://127.0.0.1:8317",
            api_key="sk-test",
            protocol_type="openai",
            provider_variant="cpa-grok-video",
            auth_header_type="authorization",
        )

        original = ProxyService._request_cpa_grok_video_status

        async def fake_status(_channel, _video_id, *, request_headers=None):
            return {"status": "done", "progress": 100}

        ProxyService._request_cpa_grok_video_status = staticmethod(fake_status)
        try:
            with self.assertRaises(ServiceException):
                await ProxyService._resolve_cpa_grok_video_download_url(channel, "video-123")
        finally:
            ProxyService._request_cpa_grok_video_status = original


if __name__ == "__main__":
    unittest.main()
