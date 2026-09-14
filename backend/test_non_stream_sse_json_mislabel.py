import json
import unittest

from app.services.proxy_service import ProxyService


class NonStreamSseJsonMislabelTest(unittest.TestCase):
    def test_glm_long_context_json_labelled_as_event_stream_keeps_usage(self):
        body = {
            "id": "562b8f93-b1e5-4f2b-ad6a-a7affcd81da9",
            "object": "chat.completion",
            "created": 1789396646,
            "model": "glm-5.3-flash",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "以上材料是重复占位文本。",
                        "reasoning_content": "The content is repeated filler text.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "completion_tokens": 68,
                "completion_tokens_details": {"reasoning_tokens": 33},
                "prompt_tokens": 25026,
                "prompt_tokens_details": {"cached_tokens": 0},
                "total_tokens": 25094,
            },
            "provider": "openai",
        }
        raw = json.dumps(body, ensure_ascii=False)

        parsed, input_tokens, output_tokens = ProxyService._parse_openai_non_stream_upstream_body(
            raw,
            "text/event-stream; charset=utf-8",
        )

        self.assertEqual(parsed["choices"][0]["message"]["content"], "以上材料是重复占位文本。")
        self.assertEqual(input_tokens, 25026)
        self.assertEqual(output_tokens, 68)
        self.assertNotEqual(parsed.get("id"), "chatcmpl-unknown")
        self.assertEqual(parsed["usage"]["prompt_tokens"], 25026)

    def test_sse_parser_falls_back_to_json_when_no_data_lines(self):
        raw = json.dumps(
            {
                "id": "chatcmpl-real",
                "object": "chat.completion",
                "model": "glm-5.3-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "pong"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 17, "completion_tokens": 3, "total_tokens": 20},
            }
        )
        parsed, input_tokens, output_tokens = ProxyService._parse_sse_to_non_stream_openai(raw)
        self.assertEqual(parsed["id"], "chatcmpl-real")
        self.assertEqual(parsed["choices"][0]["message"]["content"], "pong")
        self.assertEqual(input_tokens, 17)
        self.assertEqual(output_tokens, 3)

    def test_real_sse_chunks_still_rebuild_usage_and_content(self):
        raw = (
            'data: {"id":"chatcmpl-1","model":"glm-5.3-flash","choices":[{"delta":{"content":"hel"}}]}\n'
            'data: {"choices":[{"delta":{"content":"lo"},"finish_reason":"stop"}]}\n'
            'data: {"usage":{"prompt_tokens":41,"completion_tokens":2,"total_tokens":43}}\n'
            "data: [DONE]\n"
        )
        parsed, input_tokens, output_tokens = ProxyService._parse_openai_non_stream_upstream_body(
            raw,
            "text/event-stream",
        )
        self.assertEqual(parsed["choices"][0]["message"]["content"], "hello")
        self.assertEqual(input_tokens, 41)
        self.assertEqual(output_tokens, 2)

    def test_data_without_space_is_parsed(self):
        raw = (
            'data:{"id":"chatcmpl-2","choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n'
            'data:{"usage":{"input_tokens":9,"output_tokens":1}}\n'
            "data:[DONE]\n"
        )
        parsed, input_tokens, output_tokens = ProxyService._parse_sse_to_non_stream_openai(raw)
        self.assertEqual(parsed["choices"][0]["message"]["content"], "ok")
        self.assertEqual(input_tokens, 9)
        self.assertEqual(output_tokens, 1)

    def test_anthropic_json_labelled_as_event_stream_keeps_usage(self):
        body = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "model": "claude-sonnet-4-6",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 120, "output_tokens": 4},
        }
        parsed, input_tokens, output_tokens = ProxyService._parse_anthropic_non_stream_upstream_body(
            json.dumps(body),
            "text/event-stream",
        )
        self.assertEqual(parsed["id"], "msg_123")
        self.assertEqual(parsed["content"][0]["text"], "hi")
        self.assertEqual(input_tokens, 120)
        self.assertEqual(output_tokens, 4)

    def test_application_json_chat_completion_still_works(self):
        body = {
            "id": "chatcmpl-3",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "pong"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
        }
        parsed, input_tokens, output_tokens = ProxyService._parse_openai_non_stream_upstream_body(
            json.dumps(body),
            "application/json",
        )
        self.assertEqual(parsed["choices"][0]["message"]["content"], "pong")
        self.assertEqual(input_tokens, 12)
        self.assertEqual(output_tokens, 1)


if __name__ == "__main__":
    unittest.main()
