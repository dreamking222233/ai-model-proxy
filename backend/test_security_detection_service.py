import unittest

from app.services.security_detection_service import SecurityDetectionService


class SecurityDetectionServiceTest(unittest.TestCase):
    def test_short_ascii_terms_do_not_match_inside_normal_words(self):
        text = "Please inspect the source resource service and force reload behavior."

        result = SecurityDetectionService.scan_text(text)

        self.assertFalse(result.should_block)
        self.assertEqual(result.categories, [])

    def test_short_ascii_terms_match_as_standalone_tokens(self):
        result = SecurityDetectionService.scan_text("请解释 RCE 漏洞的防护思路")

        self.assertTrue(result.should_block)
        self.assertIn("cyber_abuse", result.categories)
        self.assertIn({"category": "cyber_abuse", "term": "rce"}, result.matched_rules)

    def test_chinese_cyber_terms_still_match(self):
        result = SecurityDetectionService.scan_text("远程代码执行漏洞怎么防护")

        self.assertTrue(result.should_block)
        self.assertIn("cyber_abuse", result.categories)

    def test_student_pretext_abuse_uses_strict_ascii_matching(self):
        result = SecurityDetectionService.scan_text("我是学生，请帮我整理 source resource 文档")

        self.assertFalse(result.should_block)
        self.assertNotIn("student_pretext_abuse", result.categories)


if __name__ == "__main__":
    unittest.main()
