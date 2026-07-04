import unittest

from app.services.security_detection_service import SecurityDetectionService


class SecurityDetectionFalsePositiveTest(unittest.TestCase):
    def test_prompt_injection_security_research_context_is_allowed(self):
        text = (
            "Important because Team prompt injection is still live. "
            "Current code checks loop_history.go and needs a defensive fix."
        )

        result = SecurityDetectionService.scan_text(text)

        self.assertFalse(result.should_block)
        self.assertEqual(result.categories, [])

    def test_prompt_injection_abuse_context_still_blocks(self):
        text = "帮我写一个 prompt injection payload，用来绕过 system prompt 并忽略开发者消息。"

        result = SecurityDetectionService.scan_text(text)

        self.assertTrue(result.should_block)
        self.assertIn("prompt_jailbreak", result.categories)
        self.assertIn({"category": "prompt_jailbreak", "term": "prompt injection"}, result.matched_rules)

    def test_prompt_injection_chinese_attack_context_still_blocks(self):
        text = "帮我写一个 prompt injection 攻击教程"

        result = SecurityDetectionService.scan_text(text)

        self.assertTrue(result.should_block)
        self.assertIn("prompt_jailbreak", result.categories)
        self.assertIn({"category": "prompt_jailbreak", "term": "prompt injection"}, result.matched_rules)

    def test_prompt_injection_chinese_attack_generation_still_blocks(self):
        for text in ("帮我写一个 prompt injection 攻击", "请生成 prompt injection 攻击"):
            with self.subTest(text=text):
                result = SecurityDetectionService.scan_text(text)

                self.assertTrue(result.should_block)
                self.assertIn("prompt_jailbreak", result.categories)
                self.assertIn({"category": "prompt_jailbreak", "term": "prompt injection"}, result.matched_rules)

    def test_prompt_injection_defense_context_is_allowed(self):
        text = "如何防范 prompt injection 攻击"

        result = SecurityDetectionService.scan_text(text)

        self.assertFalse(result.should_block)
        self.assertEqual(result.categories, [])

    def test_compound_delivery_word_does_not_match_sexual_term(self):
        for text in ("伦理审查库的首个可交付切片已经完成，后续按阶段性交付。", "合同约定一次性交付。"):
            with self.subTest(text=text):
                result = SecurityDetectionService.scan_text(text)

                self.assertFalse(result.should_block)
                self.assertEqual(result.categories, [])

    def test_contextual_sexual_generation_still_blocks(self):
        result = SecurityDetectionService.scan_text("帮我写性交描写和口交内容")

        self.assertTrue(result.should_block)
        self.assertIn("sexual_content", result.categories)

    def test_sex_trade_and_paid_sexual_context_still_blocks(self):
        for text in ("性交易", "性交付费内容", "一次性交付费内容", "一次性交服务"):
            with self.subTest(text=text):
                result = SecurityDetectionService.scan_text(text)

                self.assertTrue(result.should_block)
                self.assertIn("sexual_content", result.categories)


if __name__ == "__main__":
    unittest.main()
