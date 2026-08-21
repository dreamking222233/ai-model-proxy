import unittest

from app.models.channel import Channel
from app.services.proxy_service import ProxyService


class ReasoningEffortNormalizationTest(unittest.TestCase):
    def test_normalization_rewrites_only_reasoning_effort_fields(self):
        request_data = {
            "reasoning_effort": "xhigh",
            "reasoning": {"effort": "xhigh"},
            "thinking": {"effort": "XHIGH"},
            "messages": [
                {"role": "user", "content": "xhigh should stay inside a sentence"},
                {"role": "user", "content": [{"type": "text", "text": "xhigh"}]},
            ],
            "metadata": {"level": "xhigh"},
        }

        normalized = ProxyService._normalize_request_reasoning_levels(request_data)

        self.assertEqual(normalized["reasoning_effort"], "high")
        self.assertEqual(normalized["reasoning"]["effort"], "high")
        self.assertEqual(normalized["thinking"]["effort"], "high")
        self.assertEqual(
            normalized["messages"][0]["content"],
            "xhigh should stay inside a sentence",
        )
        self.assertEqual(normalized["messages"][1]["content"][0]["text"], "xhigh")
        self.assertEqual(normalized["metadata"]["level"], "xhigh")
        self.assertEqual(request_data["reasoning_effort"], "xhigh")
        self.assertEqual(request_data["reasoning"]["effort"], "xhigh")
        self.assertEqual(request_data["thinking"]["effort"], "XHIGH")

    def test_openai_prepare_normalizes_top_level_reasoning_effort(self):
        channel = Channel(id=1, name="openai", protocol_type="openai")
        prepared = ProxyService._prepare_openai_request_for_channel(
            channel,
            {
                "model": "gpt-test",
                "reasoning_effort": "xhigh",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(prepared["reasoning_effort"], "high")

    def test_anthropic_prepare_normalizes_thinking_effort(self):
        channel = Channel(id=1, name="anthropic", protocol_type="anthropic")
        prepared = ProxyService._prepare_anthropic_request_for_channel(
            channel,
            {
                "model": "claude-test",
                "thinking": {"type": "enabled", "effort": "xhigh"},
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

        self.assertEqual(prepared["thinking"]["effort"], "high")

    def test_responses_prepare_normalizes_reasoning_effort(self):
        prepared = ProxyService._prepare_responses_request_body(
            "gpt-test",
            {
                "model": "gpt-test",
                "reasoning": {"effort": "xhigh"},
                "input": "hello",
            },
        )

        self.assertEqual(prepared["reasoning"]["effort"], "high")

    def test_mapping_default_xhigh_is_downgraded_to_high(self):
        request_data = {"model": "gpt-test", "input": "hello"}

        ProxyService._apply_responses_mapping_default_reasoning_effort(
            request_data,
            upstream_model_name="gpt-test",
            default_reasoning_effort="xhigh",
        )

        self.assertEqual(request_data["reasoning"]["effort"], "high")

    def test_anthropic_to_responses_bridge_normalizes_explicit_effort(self):
        responses_request = ProxyService._convert_anthropic_request_to_responses(
            {
                "model": "gpt-test",
                "stream": False,
                "max_tokens": 128,
                "thinking": {"type": "enabled", "effort": "xhigh"},
                "messages": [{"role": "user", "content": "hello"}],
            },
            requested_model="claude-client-model",
        )

        self.assertEqual(responses_request["reasoning"]["effort"], "high")

    def test_anthropic_to_responses_bridge_normalizes_default_effort(self):
        responses_request = ProxyService._convert_anthropic_request_to_responses(
            {
                "model": "gpt-test",
                "stream": False,
                "max_tokens": 128,
                "messages": [{"role": "user", "content": "hello"}],
            },
            requested_model="claude-client-model",
            default_reasoning_effort="xhigh",
        )

        self.assertEqual(responses_request["reasoning"]["effort"], "high")

    def test_responses_websocket_create_normalizes_effort_without_touching_input_text(self):
        normalized, state_request, is_prewarm = ProxyService._normalize_responses_websocket_request(
            ProxyService._normalize_request_reasoning_levels({
                "type": "response.create",
                "model": "gpt-test",
                "reasoning": {"effort": "xhigh"},
                "input": "xhigh",
            }),
            None,
            [],
        )

        self.assertFalse(is_prewarm)
        self.assertEqual(normalized["reasoning"]["effort"], "high")
        self.assertEqual(normalized["input"][0]["content"][0]["text"], "xhigh")
        self.assertEqual(state_request["reasoning"]["effort"], "high")

    def test_responses_websocket_append_normalizes_effort_without_touching_input_text(self):
        last_request = {
            "model": "gpt-test",
            "reasoning": {"effort": "high"},
            "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "first"}]}],
            "stream": True,
        }

        normalized, state_request, is_prewarm = ProxyService._normalize_responses_websocket_request(
            ProxyService._normalize_request_reasoning_levels({
                "type": "response.append",
                "reasoning": {"effort": "xhigh"},
                "input": "xhigh",
            }),
            last_request,
            [],
        )

        self.assertFalse(is_prewarm)
        self.assertEqual(normalized["reasoning"]["effort"], "high")
        self.assertEqual(normalized["input"][-1]["content"][0]["text"], "xhigh")
        self.assertEqual(state_request["reasoning"]["effort"], "high")


if __name__ == "__main__":
    unittest.main()
