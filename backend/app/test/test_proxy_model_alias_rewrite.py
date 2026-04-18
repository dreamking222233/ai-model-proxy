import unittest

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


if __name__ == "__main__":
    unittest.main()
