import unittest

from app.services.proxy_service import ProxyService


class AnthropicBridgeClaudeCodeGuidanceTest(unittest.TestCase):
    def test_convert_adds_claude_code_guidance_for_opus_bridge_sessions(self):
        request_data = {
            "model": "gpt-5.4",
            "stream": True,
            "system": "system prompt",
            "tools": [
                {
                    "name": "Agent",
                    "description": "Spawn an agent",
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "name": "TodoWrite",
                    "description": "Write todos",
                    "input_schema": {"type": "object", "properties": {}},
                },
            ],
            "messages": [
                {"role": "user", "content": "Analyze the repo and produce a plan."}
            ],
        }

        converted = ProxyService._convert_anthropic_request_to_responses(
            request_data,
            requested_model="claude-opus-4-6",
        )

        developer_messages = [
            item
            for item in converted.get("input", [])
            if isinstance(item, dict)
            and item.get("type") == "message"
            and item.get("role") == "developer"
        ]

        self.assertGreaterEqual(len(developer_messages), 2)
        self.assertTrue(
            any(
                "Claude Code" in str(item.get("content", ""))
                and "run_in_background=true" in str(item.get("content", ""))
                for item in developer_messages
            )
        )
        self.assertNotIn("reasoning", converted)
        self.assertNotIn("parallel_tool_calls", converted)

    def test_convert_skips_bridge_guidance_for_non_claude_code_toolsets(self):
        request_data = {
            "model": "gpt-5.4",
            "stream": True,
            "system": "system prompt",
            "tools": [
                {
                    "name": "Bash",
                    "description": "Run bash",
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "name": "Read",
                    "description": "Read files",
                    "input_schema": {"type": "object", "properties": {}},
                },
            ],
            "messages": [
                {"role": "user", "content": "List the repository files."}
            ],
        }

        converted = ProxyService._convert_anthropic_request_to_responses(
            request_data,
            requested_model="claude-opus-4-6",
        )

        developer_messages = [
            item
            for item in converted.get("input", [])
            if isinstance(item, dict)
            and item.get("type") == "message"
            and item.get("role") == "developer"
        ]

        self.assertEqual(len(developer_messages), 1)
        self.assertFalse(
            any("Claude Code" in str(item.get("content", "")) for item in developer_messages)
        )

    def test_normalize_agent_tool_input_for_read_only_bridge_sessions(self):
        normalized = ProxyService._normalize_claude_code_bridge_tool_input(
            "claude-opus-4-6",
            "Agent",
            {
                "description": "只读探索",
                "prompt": "Read-only exploration only. Analyze the backend code. Do not modify code.",
                "subagent_type": "Explore",
                "run_in_background": False,
                "isolation": "worktree",
            },
        )

        self.assertTrue(normalized["run_in_background"])
        self.assertNotIn("isolation", normalized)

    def test_normalize_read_tool_input_removes_empty_pages(self):
        normalized = ProxyService._normalize_claude_code_bridge_tool_input(
            "claude-opus-4-6",
            "Read",
            {
                "file_path": "/tmp/example.txt",
                "offset": 1,
                "limit": 2000,
                "pages": "",
            },
        )

        self.assertEqual(normalized["file_path"], "/tmp/example.txt")
        self.assertNotIn("pages", normalized)

    def test_normalize_grep_tool_input_moves_wildcard_path_into_glob(self):
        normalized = ProxyService._normalize_claude_code_bridge_tool_input(
            "claude-opus-4-6",
            "Grep",
            {
                "pattern": "subscription",
                "path": "/Volumes/project/modelInvocationSystem/backend/app/api/user/*.py",
            },
        )

        self.assertEqual(
            normalized["path"],
            "/Volumes/project/modelInvocationSystem/backend/app/api/user",
        )
        self.assertEqual(normalized["glob"], "*.py")


if __name__ == "__main__":
    unittest.main()
