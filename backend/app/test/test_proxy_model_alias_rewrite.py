import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.core.exceptions import ServiceException
from app.services.log_service import LogService
from app.services.proxy_service import ProxyService

REQUESTED_MODEL = "alias-model"
UPSTREAM_MODEL = "provider-real-model"
RESPONSES_UPSTREAM_MODEL = "responses:internal-target-model"


class ProxyModelAliasRewriteTest(unittest.TestCase):
    def test_rewrite_openai_payload_model(self):
        payload = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": UPSTREAM_MODEL,
            "choices": [],
        }

        rewritten = ProxyService._rewrite_openai_payload_model(
            payload,
            REQUESTED_MODEL,
        )

        self.assertEqual(rewritten["model"], REQUESTED_MODEL)
        self.assertEqual(payload["model"], UPSTREAM_MODEL)

    def test_rewrite_anthropic_message_start_model(self):
        payload = {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "model": UPSTREAM_MODEL,
                "content": [],
            },
        }

        rewritten = ProxyService._rewrite_anthropic_payload_model(
            payload,
            REQUESTED_MODEL,
        )

        self.assertEqual(rewritten["message"]["model"], REQUESTED_MODEL)
        self.assertEqual(payload["message"]["model"], UPSTREAM_MODEL)

    def test_rewrite_anthropic_message_payload_model(self):
        payload = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": UPSTREAM_MODEL,
            "content": [{"type": "text", "text": "ok"}],
        }

        rewritten = ProxyService._rewrite_anthropic_payload_model(
            payload,
            REQUESTED_MODEL,
        )

        self.assertEqual(rewritten["model"], REQUESTED_MODEL)
        self.assertEqual(payload["model"], UPSTREAM_MODEL)

    def test_sanitize_visible_model_text(self):
        sanitized = ProxyService._sanitize_visible_model_text(
            f"Upstream returned HTTP 400: model {UPSTREAM_MODEL} not found",
            REQUESTED_MODEL,
            UPSTREAM_MODEL,
        )

        self.assertIn(REQUESTED_MODEL, sanitized)
        self.assertNotIn(UPSTREAM_MODEL, sanitized)

    def test_sanitize_visible_model_text_for_responses_mapping(self):
        sanitized = ProxyService._sanitize_visible_model_text(
            f"unsupported model {RESPONSES_UPSTREAM_MODEL}",
            REQUESTED_MODEL,
            RESPONSES_UPSTREAM_MODEL,
        )

        self.assertIn(REQUESTED_MODEL, sanitized)
        self.assertNotIn(RESPONSES_UPSTREAM_MODEL, sanitized)
        self.assertNotIn(RESPONSES_UPSTREAM_MODEL.split(':', 1)[1], sanitized)

    def test_public_actual_model_name_hides_bridge_upstream(self):
        self.assertEqual(
            ProxyService._public_actual_model_name("claude-opus-4-6", "gpt-5.4"),
            "claude-opus-4-6",
        )

    def test_log_service_public_actual_model_name_hides_bridge_upstream(self):
        self.assertEqual(
            LogService._public_actual_model_name("claude-opus-4-6", "gpt-5.4"),
            "claude-opus-4-6",
        )

    def test_normalize_openai_chat_response_payload_backfills_empty_content(self):
        payload = {
            "id": "chatcmpl-2",
            "object": "chat.completion",
            "model": UPSTREAM_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "fallback text",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        normalized = ProxyService._normalize_openai_chat_response_payload(payload)

        self.assertEqual(normalized["choices"][0]["message"]["content"], "fallback text")
        self.assertEqual(payload["choices"][0]["message"]["content"], "")

    def test_prioritize_channels_for_request_prefers_matching_protocol(self):
        anthropic_channel = SimpleNamespace(id=1, name="anthropic", protocol_type="anthropic", priority=5)
        openai_channel = SimpleNamespace(id=2, name="openai", protocol_type="openai", priority=5)
        channels = [
            (openai_channel, "grok-4.20-auto"),
            (anthropic_channel, "grok-4.20-auto"),
        ]

        prioritized_for_anthropic = ProxyService._prioritize_channels_for_request(
            channels,
            "anthropic",
        )
        prioritized_for_openai = ProxyService._prioritize_channels_for_request(
            channels,
            "openai",
        )

        self.assertEqual(prioritized_for_anthropic[0][0].name, "anthropic")
        self.assertEqual(prioritized_for_openai[0][0].name, "openai")

    @patch("app.services.proxy_service.ModelService.resolve_model")
    @patch("app.services.proxy_service.ModelService.get_enabled_model_by_name")
    def test_resolve_requested_model_rejects_unknown_before_override(
        self,
        mock_get_enabled_model_by_name,
        mock_resolve_model,
    ):
        mock_get_enabled_model_by_name.return_value = None
        mock_resolve_model.return_value = SimpleNamespace(model_name="gpt-5.5")

        with self.assertRaises(ServiceException) as ctx:
            ProxyService._resolve_requested_model_or_raise(MagicMock(), "gpt-5.2")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.error_code, "MODEL_NOT_FOUND")
        self.assertIn("请求模型 'gpt-5.2' 不存在", ctx.exception.detail)
        self.assertIn("模型列表页", ctx.exception.detail)
        mock_resolve_model.assert_not_called()

    @patch("app.services.proxy_service.ModelService.resolve_model")
    @patch("app.services.proxy_service.ModelService.get_enabled_model_by_name")
    def test_resolve_requested_model_allows_configured_model_override(
        self,
        mock_get_enabled_model_by_name,
        mock_resolve_model,
    ):
        configured_model = SimpleNamespace(model_name="gpt-5.4")
        override_target = SimpleNamespace(model_name="gpt-5.5")
        mock_get_enabled_model_by_name.return_value = configured_model
        mock_resolve_model.return_value = override_target

        resolved = ProxyService._resolve_requested_model_or_raise(MagicMock(), "gpt-5.4")

        self.assertEqual(resolved, override_target)
        mock_resolve_model.assert_called_once()


if __name__ == "__main__":
    unittest.main()
