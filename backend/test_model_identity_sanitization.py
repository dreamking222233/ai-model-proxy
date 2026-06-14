import unittest

from app.services.proxy_service import ProxyService, _VisibleModelIdentityStreamBuffer


class ModelIdentitySanitizationTest(unittest.TestCase):
    def test_chinese_codex_gpt_identity_answer_is_collapsed(self):
        text = (
            "我当前是 Codex 在回复你，系统环境说明是：基于 GPT-5。\n\n"
            "但具体型号在当前对话里没有暴露给我。"
        )

        self.assertEqual(
            ProxyService._sanitize_visible_model_identity_text(
                text,
                "claude-opus-4-8",
                "gpt-5.5",
            ),
            "当前模型：claude-opus-4-8",
        )

    def test_stream_buffer_holds_split_identity_leak_until_sentence_boundary(self):
        buffer = _VisibleModelIdentityStreamBuffer(
            lambda value: ProxyService._sanitize_visible_model_identity_text(
                value,
                "claude-opus-4-8",
                "gpt-5.5",
            )
        )

        self.assertEqual(buffer.feed("我当前是 Cod"), "")
        self.assertEqual(buffer.feed("ex 在回复你，系统环境说明是：基于 GPT-5。"), "当前模型：claude-opus-4-8")
        self.assertEqual(buffer.flush(), "")


if __name__ == "__main__":
    unittest.main()
