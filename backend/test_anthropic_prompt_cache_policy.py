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
        "anthropic_prompt_cache_normalize_user_ids": "",
        "anthropic_prompt_cache_normalize_agent_ids": "",
    }

    def _get_config(_db, key, default=None):
        return values.get(key, default)

    return _get_config


def _config_side_effect_with_scope(
    policy: str,
    *,
    normalize_user_ids: str = "",
    normalize_agent_ids: str = "",
):
    base = _config_side_effect(policy)

    def _get_config(db, key, default=None):
        if key == "anthropic_prompt_cache_normalize_user_ids":
            return normalize_user_ids
        if key == "anthropic_prompt_cache_normalize_agent_ids":
            return normalize_agent_ids
        return base(db, key, default)

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
        self.assertNotIn("cache_control", fallback["request_data"]["messages"][0]["content"][0])

    def test_user_scope_overrides_augment_to_normalize(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect_with_scope(
                "augment",
                normalize_user_ids="244, 999",
            ),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(
                None,
                request,
                user_id=244,
                agent_id=5,
            )

        first = variants[0]
        self.assertEqual(first["meta"]["control_policy"], "normalize")
        self.assertEqual(first["meta"]["control_policy_source"], "normalize_user")
        self.assertTrue(first["meta"]["user_cache_control_removed"])
        self.assertNotIn("cache_control", first["request_data"]["messages"][0]["content"][0])

    def test_agent_scope_overrides_augment_to_normalize(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect_with_scope(
                "augment",
                normalize_agent_ids="5\n22",
            ),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(
                None,
                request,
                user_id=244,
                agent_id=5,
            )

        first = variants[0]
        self.assertEqual(first["meta"]["control_policy"], "normalize")
        self.assertEqual(first["meta"]["control_policy_source"], "normalize_agent")
        self.assertTrue(first["meta"]["user_cache_control_removed"])

    def test_user_scope_has_priority_over_agent_scope(self):
        request = _request_with_user_cache_control()

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect_with_scope(
                "augment",
                normalize_user_ids="244",
                normalize_agent_ids="5",
            ),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(
                None,
                request,
                user_id=244,
                agent_id=5,
            )

        first = variants[0]
        self.assertEqual(first["meta"]["control_policy"], "normalize")
        self.assertEqual(first["meta"]["control_policy_source"], "normalize_user")

    def test_history_breakpoint_uses_previous_user_turn(self):
        request = {
            "model": "claude-opus-4-8",
            "system": [{"type": "text", "text": "stable system"}],
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "first user"}]},
                {"role": "assistant", "content": [{"type": "text", "text": "assistant"}]},
                {"role": "user", "content": [{"type": "text", "text": "latest user"}]},
            ],
        }

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect("augment"),
        ):
            variants = AnthropicPromptCacheService.build_request_variants(None, request)

        first = variants[0]["request_data"]
        self.assertIn("cache_control", first["system"][0])
        self.assertIn("cache_control", first["messages"][0]["content"][0])
        self.assertNotIn("cache_control", first["messages"][2]["content"][0])

    def test_ttl_order_downgrades_late_1h_after_5m(self):
        request = {
            "model": "claude-opus-4-8",
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read a file.",
                    "input_schema": {"type": "object"},
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "system": [{"type": "text", "text": "stable system"}],
        }

        with patch(
            "app.services.anthropic_prompt_cache_service.get_system_config",
            side_effect=_config_side_effect("augment"),
        ) as mocked_config:
            def _get_config(_db, key, default=None):
                if key == "anthropic_prompt_cache_static_ttl":
                    return "1h"
                return _config_side_effect("augment")(_db, key, default)

            mocked_config.side_effect = _get_config
            variants = AnthropicPromptCacheService.build_request_variants(None, request)

        first = variants[0]["request_data"]
        self.assertNotIn("ttl", first["system"][0]["cache_control"])


if __name__ == "__main__":
    unittest.main()
