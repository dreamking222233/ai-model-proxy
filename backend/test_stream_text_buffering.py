import json
import unittest

from app.services.proxy_service import ProxyService, _SecurityRiskMarkerStreamBuffer


def _event_name(sse: str) -> str:
    for line in sse.splitlines():
        if line.startswith("event: "):
            return line[7:]
    return ""


def _event_payload(sse: str) -> dict:
    for line in sse.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


class StreamTextBufferingTest(unittest.TestCase):
    def test_security_marker_buffer_passthrough_short_text_immediately(self):
        buffer = _SecurityRiskMarkerStreamBuffer()

        self.assertEqual(buffer.feed("好的。"), "好的。")
        self.assertEqual(buffer.flush(), "")

    def test_security_marker_buffer_flushes_all_visible_text(self):
        buffer = _SecurityRiskMarkerStreamBuffer()
        text = "你好！我在，可以帮你看代码、修 bug、做方案或跑命令。你想先处理什么？"

        visible = buffer.feed(text) + buffer.flush()

        self.assertEqual(visible, text)

    def test_security_marker_buffer_removes_internal_marker(self):
        buffer = _SecurityRiskMarkerStreamBuffer()
        text = "可见前缀[MIS_RISK_REPORT {\"level\":\"high\"}]可见后缀"

        visible = buffer.feed(text[:10])
        visible += buffer.feed(text[10:30])
        visible += buffer.feed(text[30:])
        visible += buffer.flush()

        self.assertEqual(visible, "可见前缀可见后缀")

    def test_flushed_anthropic_tail_uses_delta_event_before_block_stop(self):
        chunk = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "尾部文本"},
        }

        sse = (
            "event: content_block_delta\n"
            f"data: {json.dumps(ProxyService._rewrite_anthropic_payload_model(chunk, 'claude-opus-4-8'), ensure_ascii=False)}\n\n"
        )

        self.assertEqual(_event_name(sse), "content_block_delta")
        payload = _event_payload(sse)
        self.assertEqual(payload["type"], "content_block_delta")
        self.assertEqual(payload["delta"]["text"], "尾部文本")


if __name__ == "__main__":
    unittest.main()
