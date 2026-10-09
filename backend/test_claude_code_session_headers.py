import unittest
from types import SimpleNamespace

from app.services.proxy_service import ProxyService


class ClaudeCodeSessionHeadersTest(unittest.TestCase):
    def test_messages_upstream_preserves_session_and_agent_identity(self):
        channel = SimpleNamespace(api_key="upstream-test-token", auth_header_type="authorization")
        client_headers = {
            "X-Claude-Code-Session-Id": "session-a",
            "x-CLAUDE-code-AGENT-id": "agent-a",
            "User-Agent": "claude-code-test",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "test-feature",
            "Authorization": "Bearer client-test-token",
            "x-api-key": "client-test-token",
            "Cookie": "private=test",
            "X-Custom-Header": "not-forwarded",
        }
        original = dict(client_headers)

        headers = ProxyService._build_headers(channel, "anthropic", client_headers)

        self.assertEqual(headers["X-Claude-Code-Session-Id"], "session-a")
        self.assertEqual(headers["X-Claude-Code-Agent-Id"], "agent-a")
        self.assertEqual(headers["Authorization"], "Bearer upstream-test-token")
        self.assertEqual(headers["User-Agent"], "claude-code-test")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["anthropic-beta"], "test-feature")
        self.assertNotIn("x-api-key", headers)
        self.assertNotIn("Cookie", headers)
        self.assertNotIn("X-Custom-Header", headers)
        self.assertEqual(client_headers, original)

    def test_agent_branches_keep_distinct_identities_within_one_session(self):
        for agent in ["main", "agent-a", "agent-b"]:
            with self.subTest(agent=agent):
                headers = ProxyService._extract_forward_headers(
                    {"x-claude-code-session-id": "session-a", "x-claude-code-agent-id": agent},
                    "anthropic",
                )
                self.assertEqual(headers["X-Claude-Code-Session-Id"], "session-a")
                self.assertEqual(headers["X-Claude-Code-Agent-Id"], agent)

    def test_valid_identities_are_trimmed(self):
        headers = ProxyService._extract_forward_headers(
            {"x-claude-code-session-id": " session-a ", "x-claude-code-agent-id": " agent-a "},
            "anthropic",
        )
        self.assertEqual(headers["X-Claude-Code-Session-Id"], "session-a")
        self.assertEqual(headers["X-Claude-Code-Agent-Id"], "agent-a")

    def test_missing_headers_do_not_generate_new_identities(self):
        for request_headers in [None, {}, {"anthropic-version": "2023-06-01"}]:
            with self.subTest(request_headers=request_headers):
                headers = ProxyService._extract_forward_headers(request_headers, "anthropic")
                self.assertNotIn("X-Claude-Code-Session-Id", headers)
                self.assertNotIn("X-Claude-Code-Agent-Id", headers)

    def test_empty_and_non_string_identities_are_omitted(self):
        for value in ["", "  ", None, 123]:
            with self.subTest(value=value):
                headers = ProxyService._extract_forward_headers(
                    {"x-claude-code-session-id": value, "x-claude-code-agent-id": value},
                    "anthropic",
                )
                self.assertNotIn("X-Claude-Code-Session-Id", headers)
                self.assertNotIn("X-Claude-Code-Agent-Id", headers)

    def test_other_protocols_keep_the_existing_header_allowlist(self):
        for protocol in ["openai", "google"]:
            with self.subTest(protocol=protocol):
                headers = ProxyService._extract_forward_headers(
                    {
                        "x-claude-code-session-id": "session-a",
                        "x-claude-code-agent-id": "agent-a",
                        "openai-beta": "responses-test",
                    },
                    protocol,
                )
                self.assertNotIn("X-Claude-Code-Session-Id", headers)
                self.assertNotIn("X-Claude-Code-Agent-Id", headers)
                self.assertEqual(headers["OpenAI-Beta"], "responses-test")

    def test_individually_missing_identities_are_not_filled(self):
        for name in ["X-Claude-Code-Session-Id", "X-Claude-Code-Agent-Id"]:
            with self.subTest(name=name):
                headers = ProxyService._extract_forward_headers({name: "identity-a"}, "anthropic")
                self.assertEqual(headers, {name: "identity-a"})

    def test_channel_authentication_modes_replace_client_credentials(self):
        for mode in [None, "authorization", "x-api-key", "anthropic-api-key"]:
            with self.subTest(mode=mode):
                channel = SimpleNamespace(api_key="upstream-test-token", auth_header_type=mode)
                headers = ProxyService._build_headers(
                    channel,
                    "anthropic",
                    {
                        "Authorization": "Bearer client-test-token",
                        "x-api-key": "client-test-token",
                        "anthropic-api-key": "client-test-token",
                        "X-Claude-Code-Agent-Id": "agent-a",
                    },
                )
                self.assertEqual(headers["X-Claude-Code-Agent-Id"], "agent-a")
                self.assertNotIn("X-Claude-Code-Session-Id", headers)
                self.assertNotIn("client-test-token", headers.values())
                self.assertNotIn("Bearer client-test-token", headers.values())
                if mode == "authorization":
                    self.assertEqual(headers["Authorization"], "Bearer upstream-test-token")
                else:
                    self.assertEqual(headers["x-api-key"], "upstream-test-token")
                    self.assertEqual(headers["anthropic-api-key"], "upstream-test-token")


if __name__ == "__main__":
    unittest.main()
