import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.channel_affinity_service import ChannelAffinityService


def _config(_db, key, default=None):
    values = {
        "channel_affinity_enabled": True,
        "channel_affinity_ttl_seconds": 3600,
        "channel_affinity_fallback_enabled": True,
    }
    return values.get(key, default)


class ChannelAffinityServiceTest(unittest.TestCase):
    def setUp(self):
        ChannelAffinityService._cache.clear()

    def test_explicit_prompt_cache_key_reorders_to_successful_channel(self):
        user = SimpleNamespace(id=244, agent_id=12)
        channel_a = SimpleNamespace(id=1, name="a")
        channel_b = SimpleNamespace(id=2, name="b")
        request = {
            "model": "claude-opus-4-7",
            "prompt_cache_key": "session-abc",
            "messages": [{"role": "user", "content": "hello"}],
        }

        with patch(
            "app.services.channel_affinity_service.get_system_config",
            side_effect=_config,
        ):
            ordered = ChannelAffinityService.prioritize_channels(
                None,
                [(channel_a, "up-a"), (channel_b, "up-b")],
                user=user,
                requested_model="claude-opus-4-7",
                request_protocol="anthropic",
                request_data=request,
                request_headers={},
            )
            self.assertEqual([item[0].id for item in ordered], [1, 2])

            setattr(channel_b, "_runtime_channel_affinity_key", getattr(channel_a, "_runtime_channel_affinity_key"))
            setattr(channel_b, "_runtime_channel_affinity_enabled", True)
            setattr(channel_b, "_runtime_channel_affinity_ttl_seconds", 3600)
            ChannelAffinityService.record_success(channel_b)

            ordered = ChannelAffinityService.prioritize_channels(
                None,
                [(channel_a, "up-a"), (channel_b, "up-b")],
                user=user,
                requested_model="claude-opus-4-7",
                request_protocol="anthropic",
                request_data=request,
                request_headers={},
            )

        self.assertEqual([item[0].id for item in ordered], [2, 1])

    def test_fallback_fingerprint_is_scoped_by_user_and_model(self):
        user = SimpleNamespace(id=244, agent_id=None)
        request = {
            "system": [{"type": "text", "text": "stable system"}],
            "tools": [{"name": "read_file", "input_schema": {"type": "object"}}],
            "messages": [{"role": "user", "content": "first prompt"}],
        }

        with patch(
            "app.services.channel_affinity_service.get_system_config",
            side_effect=_config,
        ):
            key_a = ChannelAffinityService.build_affinity_key(
                None,
                user=user,
                requested_model="claude-opus-4-7",
                request_protocol="anthropic",
                request_data=request,
                request_headers={},
            )
            key_b = ChannelAffinityService.build_affinity_key(
                None,
                user=user,
                requested_model="claude-sonnet-4",
                request_protocol="anthropic",
                request_data=request,
                request_headers={},
            )

        self.assertIsNotNone(key_a)
        self.assertIsNotNone(key_b)
        self.assertNotEqual(key_a, key_b)


if __name__ == "__main__":
    unittest.main()
