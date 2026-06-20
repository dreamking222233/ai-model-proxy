import unittest
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.proxy.image_proxy import _parse_image_edit_form
from app.api.proxy.video_proxy import _parse_video_form
from app.core.exceptions import ServiceException
from app.models.channel import Channel
from app.models.log import RequestLog
from app.services.media_workbench_service import MediaWorkbenchService
from app.services.proxy_service import ProxyService


class _ScalarQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows


class _RuleDb:
    def __init__(self, rules):
        self.rules = rules

    def query(self, *_args, **_kwargs):
        return _ScalarQuery(self.rules)


class _FakeUpload:
    def __init__(self, filename, content_type, content):
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self):
        return self._content


class _FakeForm:
    def __init__(self, values=None, lists=None):
        self.values = values or {}
        self.lists = lists or {}

    def get(self, key):
        return self.values.get(key)

    def getlist(self, key):
        return self.lists.get(key, [])


class _FakeRequest:
    def __init__(self, form):
        self._form = form

    async def form(self):
        return self._form


class MediaWorkbenchTest(unittest.TestCase):
    def test_1k_prefers_compatible_without_moving_other_channels(self):
        other = Channel(id=1, name="other", protocol_type="openai", provider_variant="default")
        native = Channel(id=2, name="native", protocol_type="openai", provider_variant="openai-image-native-size")
        compatible = Channel(id=3, name="compatible", protocol_type="openai", provider_variant="openai-image-compatible")
        google = Channel(id=4, name="google", protocol_type="google", provider_variant="google-vertex-image")

        result = ProxyService._prefer_openai_compatible_for_1k_image(
            [(other, "m"), (native, "m"), (google, "m"), (compatible, "m")],
            "1K",
        )

        self.assertEqual([item[0].id for item in result], [1, 3, 4, 2])

    def test_non_1k_keeps_channel_order(self):
        native = Channel(id=2, name="native", protocol_type="openai", provider_variant="openai-image-native-size")
        compatible = Channel(id=3, name="compatible", protocol_type="openai", provider_variant="openai-image-compatible")

        result = ProxyService._prefer_openai_compatible_for_1k_image(
            [(native, "m"), (compatible, "m")],
            "2K",
        )

        self.assertEqual([item[0].id for item in result], [2, 3])

    def test_image_size_filter_excludes_compatible_for_2k(self):
        native = Channel(id=2, name="native", protocol_type="openai", provider_variant="openai-image-native-size")
        compatible = Channel(id=3, name="compatible", protocol_type="openai", provider_variant="openai-image-compatible")
        model = SimpleNamespace(model_name="gpt-image-2")

        result = ProxyService._filter_channels_by_image_size(
            [(compatible, "m"), (native, "m")],
            model,
            "2K",
        )

        self.assertEqual([item[0].id for item in result], [2])

    def test_health_level_thresholds(self):
        self.assertEqual(MediaWorkbenchService._health_level(0, 0), "unknown")
        self.assertEqual(MediaWorkbenchService._health_level(1, 95), "good")
        self.assertEqual(MediaWorkbenchService._health_level(1, 80), "warning")
        self.assertEqual(MediaWorkbenchService._health_level(1, 79.9), "bad")

    def test_empty_summary_is_stable(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        summary = MediaWorkbenchService._empty_summary(
            "image_gpt_image_2",
            "生图 gpt-image-2",
            "gpt-image-2",
            ("image_generation", "image_edit"),
            now - timedelta(hours=24),
            now,
        )

        self.assertEqual(summary["request_count"], 0)
        self.assertEqual(summary["health_level"], "unknown")
        self.assertNotIn("channel_id", summary)
        self.assertNotIn("channel_name", summary)

    def test_local_error_markers_are_declared(self):
        self.assertIn("INSUFFICIENT_IMAGE_CREDITS", MediaWorkbenchService.LOCAL_ERROR_MARKERS)
        self.assertIn("INVALID_IMAGE_SIZE", MediaWorkbenchService.LOCAL_ERROR_MARKERS)

    def test_health_summary_counts_visible_results_and_excludes_local_errors(self):
        engine = create_engine("sqlite:///:memory:")
        RequestLog.__table__.create(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.add_all([
                RequestLog(
                    request_id="req-success",
                    requested_model="gpt-image-2",
                    request_type="image_generation",
                    status="success",
                    response_time_ms=1200,
                    created_at=now,
                ),
                RequestLog(
                    request_id="req-upstream-fail",
                    requested_model="gpt-image-2",
                    request_type="image_generation",
                    status="error",
                    channel_id=1,
                    error_message="调用失败，渠道异常，请稍后重试",
                    response_time_ms=2000,
                    created_at=now,
                ),
                RequestLog(
                    request_id="req-local-fail",
                    requested_model="gpt-image-2",
                    request_type="image_generation",
                    status="error",
                    channel_id=None,
                    error_message="INSUFFICIENT_IMAGE_CREDITS",
                    response_time_ms=10,
                    created_at=now,
                ),
                RequestLog(
                    request_id="req-unknown-fail",
                    requested_model="gpt-image-2",
                    request_type="image_generation",
                    status="error",
                    channel_id=None,
                    error_message=None,
                    response_time_ms=3000,
                    created_at=now,
                ),
            ])
            db.commit()

            result = MediaWorkbenchService.get_media_health(db, 24)
            image = result["items"]["image_gpt_image_2"]

            self.assertEqual(image["request_count"], 3)
            self.assertEqual(image["success_count"], 1)
            self.assertEqual(image["failed_count"], 2)
            self.assertEqual(image["success_rate"], 33.3)
            self.assertEqual(image["health_level"], "bad")
            self.assertNotIn("channel_id", image)
            self.assertNotIn("error_message", image)
        finally:
            db.close()

    def test_video_health_counts_generation_wait_failures_logged_as_generation(self):
        engine = create_engine("sqlite:///:memory:")
        RequestLog.__table__.create(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            db.add_all([
                RequestLog(
                    request_id="video-success",
                    requested_model="grok-imagine-video",
                    request_type="video_generation",
                    status="success",
                    response_time_ms=120000,
                    created_at=now,
                ),
                RequestLog(
                    request_id="video-wait-fail",
                    requested_model="grok-imagine-video",
                    request_type="video_generation",
                    status="error",
                    channel_id=1,
                    error_message="VIDEO_WAIT_TIMEOUT",
                    image_credits_charged=0,
                    response_time_ms=1200000,
                    created_at=now,
                ),
            ])
            db.commit()

            result = MediaWorkbenchService.get_media_health(db, 24)
            video = result["items"]["video_grok"]

            self.assertEqual(video["request_count"], 2)
            self.assertEqual(video["success_count"], 1)
            self.assertEqual(video["failed_count"], 1)
            self.assertEqual(video["success_rate"], 50.0)
            self.assertEqual(video["health_level"], "bad")
        finally:
            db.close()

    def test_image_edit_form_preserves_multiple_reference_images(self):
        form = _FakeForm(
            values={
                "model": "gpt-image-2",
                "prompt": "test prompt",
                "image_size": "1K",
                "aspect_ratio": "1:1",
            },
            lists={
                "image": [
                    _FakeUpload("first.png", "image/png", b"first"),
                    _FakeUpload("second.jpg", "image/jpeg", b"second"),
                ]
            },
        )

        parsed = asyncio.run(_parse_image_edit_form(_FakeRequest(form)))

        self.assertEqual(len(parsed["images"]), 2)
        self.assertEqual(parsed["image"]["filename"], "first.png")
        self.assertEqual(parsed["images"][1]["filename"], "second.jpg")
        self.assertEqual(parsed["images"][1]["content"], b"second")

    def test_image_edit_form_rejects_more_than_seven_reference_images(self):
        form = _FakeForm(
            lists={
                "image": [
                    _FakeUpload(f"ref-{index}.png", "image/png", b"content")
                    for index in range(8)
                ]
            },
        )

        with self.assertRaises(ServiceException) as context:
            asyncio.run(_parse_image_edit_form(_FakeRequest(form)))

        self.assertEqual(context.exception.error_code, "TOO_MANY_IMAGE_REFERENCES")

    def test_video_form_preserves_multiple_reference_images(self):
        form = _FakeForm(
            values={
                "model": "grok-imagine-video",
                "prompt": "test prompt",
                "seconds": "10",
            },
            lists={
                "input_reference[]": [
                    _FakeUpload("first.png", "image/png", b"first"),
                    _FakeUpload("second.jpg", "image/jpeg", b"second"),
                ],
                "input_reference": [
                    _FakeUpload("legacy.webp", "image/webp", b"legacy"),
                ],
            },
        )

        parsed = asyncio.run(_parse_video_form(_FakeRequest(form)))

        self.assertEqual(len(parsed["input_references"]), 3)
        self.assertEqual(
            [item["filename"] for item in parsed["input_references"]],
            ["first.png", "second.jpg", "legacy.webp"],
        )


if __name__ == "__main__":
    unittest.main()
