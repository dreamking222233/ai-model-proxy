import unittest
from types import SimpleNamespace
from unittest.mock import patch

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

    def test_latest_user_text_ignores_stale_history_risk_terms(self):
        request_data = {
            "messages": [
                {"role": "user", "content": "之前免费注册机可能已经不行了"},
                {"role": "assistant", "content": "我无法协助相关内容。"},
                {"role": "user", "content": "把上面的聊天保存为一个 md 文档"},
            ]
        }

        self.assertEqual(
            SecurityDetectionService.extract_latest_user_text(request_data),
            "把上面的聊天保存为一个 md 文档",
        )
        self.assertFalse(SecurityDetectionService.scan_text(
            SecurityDetectionService.extract_latest_user_text(request_data)
        ).should_block)

    def test_latest_user_text_blocks_current_risk_terms(self):
        request_data = {
            "messages": [
                {"role": "user", "content": "把上面的聊天保存为一个 md 文档"},
                {"role": "user", "content": "现在免费注册机怎么做"},
            ]
        }

        result = SecurityDetectionService.scan_text(
            SecurityDetectionService.extract_latest_user_text(request_data)
        )

        self.assertTrue(result.should_block)
        self.assertIn({"category": "cyber_abuse", "term": "注册机"}, result.matched_rules)

    def test_student_pretext_abuse_uses_strict_ascii_matching(self):
        result = SecurityDetectionService.scan_text("我是学生，请帮我整理 source resource 文档")

        self.assertFalse(result.should_block)
        self.assertNotIn("student_pretext_abuse", result.categories)

    def test_security_prompt_does_not_include_dynamic_report_credentials(self):
        snapshot = SimpleNamespace(snapshot_id="snapshot-test-id")

        with patch(
            "app.services.security_detection_service.SecurityDetectionService._get_bool_config",
            return_value=True,
        ):
            prompt = SecurityDetectionService.build_security_system_prompt(
                object(),
                snapshot,
                "report-token-test",
            )

        self.assertIn("安全策略", prompt)
        self.assertNotIn("snapshot-test-id", prompt)
        self.assertNotIn("report-token-test", prompt)
        self.assertNotIn("/api/public/security/risk-report", prompt)


if __name__ == "__main__":
    unittest.main()
