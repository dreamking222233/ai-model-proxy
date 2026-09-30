import unittest
from types import SimpleNamespace

from app.services.channel_passthrough_service import ChannelPassthroughService
from app.services.proxy_service import ProxyService


class ModelMappingProtocolTest(unittest.TestCase):
    def setUp(self):
        self.openai_channel = SimpleNamespace(protocol_type="openai", priority=10)
        self.anthropic_channel = SimpleNamespace(protocol_type="anthropic", priority=10)

    def test_only_reserved_prefixes_select_protocol_and_strip_prefix(self):
        self.assertEqual(
            ProxyService._resolve_mapped_upstream_target(
                self.openai_channel, "responses:deepseek-v4.1-flash"
            ),
            ("deepseek-v4.1-flash", "responses"),
        )
        self.assertEqual(
            ProxyService._resolve_mapped_upstream_target(
                self.openai_channel, "messages:deepseek-v4.1-flash"
            ),
            ("deepseek-v4.1-flash", "anthropic_messages"),
        )

    def test_non_reserved_prefix_is_forwarded_as_part_of_model_name(self):
        self.assertEqual(
            ProxyService._resolve_mapped_upstream_target(
                self.openai_channel, "global:deepseek-v4.1-flash"
            ),
            ("global:deepseek-v4.1-flash", "openai_chat"),
        )
        self.assertEqual(
            ProxyService._resolve_mapped_upstream_target(
                self.anthropic_channel, "a:deepseek"
            ),
            ("a:deepseek", "anthropic_messages"),
        )

    def test_protocol_directives_are_not_native_passthrough_candidates(self):
        self.assertFalse(
            ChannelPassthroughService._channel_supports_protocol(
                self.openai_channel, "openai", "responses:deepseek"
            )
        )
        self.assertFalse(
            ChannelPassthroughService._channel_supports_protocol(
                self.anthropic_channel, "anthropic", "messages:deepseek"
            )
        )
        self.assertTrue(
            ChannelPassthroughService._channel_supports_protocol(
                self.openai_channel, "openai", "global:deepseek"
            )
        )

    def test_protocol_sorting_prefers_matching_reserved_directive(self):
        plain_openai = SimpleNamespace(protocol_type="openai", priority=20)
        channels = [
            (plain_openai, "deepseek"),
            (self.anthropic_channel, "messages:deepseek"),
        ]
        sorted_channels = ProxyService._prioritize_channels_for_request(channels, "openai")
        self.assertEqual(sorted_channels[0][1], "messages:deepseek")


if __name__ == "__main__":
    unittest.main()
