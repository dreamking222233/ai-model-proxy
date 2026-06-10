import unittest
from unittest.mock import patch

from app.services.anthropic_prompt_cache_service import AnthropicPromptCacheService


def _config_side_effect(policy: str):
    values = {
        "anthropic_prompt_cache_enabled": True,
        "anthropic_prompt_cache_control_policy": policy,
        "anthropic_prompt_cache_static_ttl": "5m",
        "anthropic_prompt_cache_history_enabled": True,
        "anthropic_prompt_cache_history_ttl": "5m",
        "anthropic_prompt_cache_beta_header": "",
    }

    def _get_config(_db, key, default=None):
        return values.get(key, default)

    return _get_config


def _request_with_user_cache_control() -> dict:
    return {
        "model": "claude-opus-4-8",
        "tools": [
            {
                "name": "read_file",
                "description": "Read a file.",
                "input_schema": {"type": "object"},
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "latest volatile user prompt",
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        ],
    }


class AnthropicPromptCachePolicyTest(unittest.TestCase):
    def test_preserve_keeps_existing_user_cache_control_without_system_variant(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect("preserve"),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(None, request)

        self.assertEqual(len(variants), 1)
        self.assertFalse(variants[0]["meta"]["attempted"])
        self.assertEqual(variants[0]["meta"]["source"], "user")
        self.assertEqual(variants[0]["meta"]["skip_reason"], "user_cache_control_present")
        self.assertIn("cache_control", variants[0]["request_data"]["messages"][0]["content"][0])

    def test_augment_preserves_user_cache_control_and_adds_stable_tool_breakpoint(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect("augment"),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(None, request)

        self.assertEqual(len(variants), 2)
        first = variants[0]
        self.assertTrue(first["meta"]["attempted"])
        self.assertEqual(first["meta"]["source"], "system+user")
        self.assertEqual(first["meta"]["control_policy"], "augment")
        self.assertTrue(first["meta"]["system_cache_control_added"])
        self.assertIn("cache_control", first["request_data"]["tools"][0])
        self.assertIn("cache_control", first["request_data"]["messages"][0]["content"][0])

        fallback = variants[-1]
        self.assertFalse(fallback["meta"]["attempted"])
        self.assertEqual(fallback["meta"]["skip_reason"], "fallback_no_cache")
        self.assertNotIn("cache_control", fallback["request_data"]["tools"][0])
        self.assertIn("cache_control", fallback["request_data"]["messages"][0]["content"][0])

    def test_normalize_removes_user_cache_control_and_rebuilds_stable_breakpoints(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect("normalize"),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(None, request)

        self.assertEqual(len(variants), 2)
        first = variants[0]
        self.assertTrue(first["meta"]["attempted"])
        self.assertEqual(first["meta"]["source"], "system")
        self.assertEqual(first["meta"]["control_policy"], "normalize")
        self.assertTrue(first["meta"]["user_cache_control_removed"])
        self.assertIn("cache_control", first["request_data"]["tools"][0])
        self.assertNotIn("cache_control", first["request_data"]["messages"][0]["content"][0])

        fallback = variants[-1]
        self.assertFalse(fallback["meta"]["attempted"])
        self.assertNotIn("cache_control", fallback["request_data"]["tools"][0])
        self.assertIn("cache_control", fallback["request_data"]["messages"][0]["content"][0])


if __name__ == "__main__":
    unittest.main()
