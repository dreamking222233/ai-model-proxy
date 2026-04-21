import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self._response


class ProxyImageBillingHelperTest(unittest.TestCase):
    def test_record_success_swallows_commit_failure_for_legacy_callers(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db unavailable")
        channel = SimpleNamespace(
            failure_count=3,
            last_success_at=None,
            is_healthy=0,
            circuit_breaker_until="later",
            health_score=88,
        )

        ProxyService._record_success(db, channel)

        self.assertEqual(channel.failure_count, 0)
        self.assertEqual(channel.is_healthy, 1)
        self.assertIsNone(channel.circuit_breaker_until)
        self.assertEqual(channel.health_score, 93)
        db.rollback.assert_called_once()

    @patch("app.services.proxy_service.ImageCreditService.deduct_for_request")
    def test_deduct_image_credits_and_log_propagates_errors(self, mock_deduct):
        mock_deduct.side_effect = ServiceException(
            402,
            "图片积分不足，请联系管理员充值",
            "INSUFFICIENT_IMAGE_CREDITS",
        )

        db = MagicMock()
        user = SimpleNamespace(id=1)
        api_key_record = SimpleNamespace(id=2, total_requests=0, last_used_at=None)
        unified_model = SimpleNamespace(image_credit_multiplier=3)
        channel = SimpleNamespace(id=9, name="google-image", protocol_type="google")

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._deduct_image_credits_and_log(
                db,
                user,
                api_key_record,
                unified_model,
                "req-1",
                "gemini-3-pro-image-preview",
                "gemini-3-pro-image-preview",
                channel,
                "127.0.0.1",
                1234,
                charged_credits=Decimal("3.000"),
                image_size="1K",
                image_count=1,
            )

        self.assertEqual(ctx.exception.error_code, "INSUFFICIENT_IMAGE_CREDITS")
        db.add.assert_not_called()
        db.flush.assert_not_called()


class ProxyImageBillingFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user = SimpleNamespace(id=1)
        self.api_key_record = SimpleNamespace(id=2, total_requests=0, last_used_at=None)
        self.channel_a = SimpleNamespace(
            id=10,
            name="channel-a",
            protocol_type="google",
            base_url="https://mock-channel-a.invalid",
        )
        self.channel_b = SimpleNamespace(
            id=11,
            name="channel-b",
            protocol_type="google",
            base_url="https://mock-channel-b.invalid",
        )
        self.unified_model = SimpleNamespace(
            id=99,
            model_name="gemini-3-pro-image-preview",
            model_type="image",
            billing_type="image_credit",
            image_credit_multiplier=3,
        )
        self.request_data = {
            "model": "gemini-3-pro-image-preview",
            "prompt": "draw a cat",
            "response_format": "b64_json",
            "n": 1,
        }

    @patch("app.services.proxy_service.ProxyService._deduct_image_credits_and_log")
    @patch("app.services.proxy_service.ProxyService._record_success")
    @patch(
        "app.services.proxy_service.ProxyService._parse_google_image_response",
        return_value=([{"b64_json": "abc", "mime_type": "image/png"}], None),
    )
    @patch("app.services.proxy_service.ProxyService._build_google_image_payload", return_value={})
    @patch("app.services.proxy_service.ProxyService._build_headers", return_value={})
    @patch("app.services.proxy_service.httpx.AsyncClient")
    async def test_non_stream_image_request_rolls_back_when_local_billing_fails(
        self,
        mock_async_client,
        _mock_headers,
        _mock_payload,
        _mock_parse,
        mock_record_success,
        mock_deduct_and_log,
    ):
        mock_async_client.return_value = _DummyAsyncClient(
            _DummyResponse(status_code=200, payload={"candidates": []})
        )
        mock_deduct_and_log.side_effect = ServiceException(
            500,
            "图片生成成功，但本地计费或记账失败，系统已中断返回，请稍后重试",
            "IMAGE_BILLING_FAILED",
        )

        with self.assertRaises(ServiceException) as ctx:
            await ProxyService._non_stream_image_request(
                self.db,
                self.user,
                self.api_key_record,
                self.channel_a,
                self.unified_model,
                self.request_data,
                "req-2",
                "gemini-3-pro-image-preview",
                "gemini-3-pro-image-preview",
                "127.0.0.1",
                Decimal("3.000"),
                image_size="1K",
            )

        self.assertEqual(ctx.exception.error_code, "IMAGE_BILLING_FAILED")
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
        mock_record_success.assert_called_once()
        self.assertEqual(mock_record_success.call_args.kwargs, {})

    @patch("app.services.proxy_service.ProxyService._log_failed_request")
    @patch("app.services.proxy_service.ProxyService._non_stream_image_request")
    @patch("app.services.proxy_service.ProxyService._resolve_image_billing_rule", return_value=("1K", Decimal("3.000")))
    @patch(
        "app.services.proxy_service.ModelService.get_available_channels",
        return_value=[(
            SimpleNamespace(
                id=10,
                name="channel-a",
                protocol_type="google",
                base_url="https://mock-channel-a.invalid",
            ),
            "upstream-a",
        )],
    )
    @patch("app.services.proxy_service.ImageCreditService.check_balance")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    async def test_handle_image_request_logs_zero_credits_when_all_channels_fail(
        self,
        mock_resolve_model,
        _mock_check_balance,
        _mock_resolve_billing_rule,
        _mock_get_channels,
        mock_non_stream_request,
        mock_log_failed_request,
    ):
        mock_resolve_model.return_value = self.unified_model
        mock_non_stream_request.side_effect = ServiceException(
            503,
            "Google image generation failed",
            "GOOGLE_IMAGE_GENERATION_FAILED",
        )

        with self.assertRaises(ServiceException) as ctx:
            await ProxyService.handle_image_request(
                self.db,
                self.user,
                self.api_key_record,
                self.request_data,
                "127.0.0.1",
            )

        self.assertEqual(ctx.exception.error_code, "GOOGLE_IMAGE_GENERATION_FAILED")
        self.assertEqual(mock_log_failed_request.call_count, 1)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_credits_charged"], 0)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_count"], 0)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_size"], "1K")

    @patch("app.services.proxy_service.ProxyService._log_failed_request")
    @patch("app.services.proxy_service.ProxyService._non_stream_image_request")
    @patch("app.services.proxy_service.ProxyService._resolve_image_billing_rule", return_value=("1K", Decimal("3.000")))
    @patch(
        "app.services.proxy_service.ModelService.get_available_channels",
        return_value=[
            (
                SimpleNamespace(
                    id=10,
                    name="channel-a",
                    protocol_type="google",
                    base_url="https://mock-channel-a.invalid",
                ),
                "upstream-a",
            ),
            (
                SimpleNamespace(
                    id=11,
                    name="channel-b",
                    protocol_type="google",
                    base_url="https://mock-channel-b.invalid",
                ),
                "upstream-b",
            ),
        ],
    )
    @patch("app.services.proxy_service.ImageCreditService.check_balance")
    @patch("app.services.proxy_service.ModelService.resolve_model")
    async def test_handle_image_request_stops_failover_on_local_billing_failure(
        self,
        mock_resolve_model,
        _mock_check_balance,
        _mock_resolve_billing_rule,
        _mock_get_channels,
        mock_non_stream_request,
        mock_log_failed_request,
    ):
        mock_resolve_model.return_value = self.unified_model
        mock_non_stream_request.side_effect = ServiceException(
            500,
            "图片生成成功，但本地计费或记账失败，系统已中断返回，请稍后重试",
            "IMAGE_BILLING_FAILED",
        )

        with self.assertRaises(ServiceException) as ctx:
            await ProxyService.handle_image_request(
                self.db,
                self.user,
                self.api_key_record,
                self.request_data,
                "127.0.0.1",
            )

        self.assertEqual(ctx.exception.error_code, "IMAGE_BILLING_FAILED")
        self.assertEqual(mock_non_stream_request.call_count, 1)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_credits_charged"], 0)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_count"], 0)
        self.assertEqual(mock_log_failed_request.call_args.kwargs["image_size"], "1K")


if __name__ == "__main__":
    unittest.main()
