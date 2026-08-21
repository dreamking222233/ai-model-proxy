import unittest

from app.services.log_service import LogService


class UserLogErrorSanitizationTest(unittest.TestCase):
    def test_plain_text_error_hides_internal_routing_fields(self):
        text = LogService._sanitize_user_visible_error_message(
            "failed on channel OpenAI actual_model=gpt-4o-mini channel_id=12 sk-12345678abcdef",
            requested_model="gpt-4o",
            actual_model="gpt-4o-mini",
            channel_name="OpenAI",
        )

        self.assertNotIn("gpt-4o-mini", text)
        self.assertNotIn("OpenAI", text)
        self.assertNotIn("channel_id=12", text)
        self.assertIn("sk-12345678***", text)

    def test_query_like_error_hides_internal_routing_fields(self):
        text = LogService._sanitize_user_visible_error_message(
            "provider failed channel_name=OpenAI actual_model=gpt-4o-mini channel id: 19",
            requested_model="gpt-4o",
            actual_model="gpt-4o-mini",
            channel_name="OpenAI",
        )

        self.assertNotIn("OpenAI", text)
        self.assertNotIn("gpt-4o-mini", text)
        self.assertNotIn("19", text)
        self.assertIn("已隐藏", text)

    def test_json_string_error_hides_internal_routing_fields(self):
        text = LogService._sanitize_user_visible_error_message(
            '{"channel_id":12,"channel_name":"OpenAI","actual_model":"gpt-4o-mini","error":"bad"}',
            requested_model="gpt-4o",
            actual_model="gpt-4o-mini",
            channel_name="OpenAI",
        )

        self.assertNotIn('"channel_id":12', text)
        self.assertNotIn('"channel_name":"OpenAI"', text)
        self.assertNotIn('"actual_model":"gpt-4o-mini"', text)
        self.assertIn('"channel_id":"已隐藏"', text)
        self.assertIn('"channel_name":"已隐藏"', text)
        self.assertIn('"actual_model":"已隐藏"', text)

    def test_json_string_error_hides_internal_field_aliases(self):
        text = LogService._sanitize_user_visible_error_message(
            '{"actual_model_name":"gpt-4o-mini","channel":12,"client_ip":"1.2.3.4","user_id":7,"username":"alice","user_api_key_id":3,"error":"bad"}',
            requested_model="gpt-4o",
            actual_model="gpt-4o-mini",
            channel_name="OpenAI",
        )

        for value in ["gpt-4o-mini", '"channel":12', "1.2.3.4", '"user_id":7', "alice", '"user_api_key_id":3']:
            self.assertNotIn(value, text)
        for key in ["actual_model_name", "channel", "client_ip", "user_id", "username", "user_api_key_id"]:
            self.assertIn(f'"{key}":"已隐藏"', text)

    def test_plain_text_error_hides_internal_field_aliases(self):
        text = LogService._sanitize_user_visible_error_message(
            "failed model=gpt-4o-mini channel=12 client_ip=1.2.3.4 user_id=7 username=alice user_api_key_id=3",
            requested_model="gpt-4o",
            actual_model="gpt-4o-mini",
            channel_name="OpenAI",
        )

        for value in ["gpt-4o-mini", "channel=12", "1.2.3.4", "user_id=7", "alice", "user_api_key_id=3"]:
            self.assertNotIn(value, text)
        self.assertIn("model=已隐藏", text)
        self.assertIn("channel=已隐藏", text)
        self.assertIn("client_ip=已隐藏", text)
        self.assertIn("user_id=已隐藏", text)
        self.assertIn("username=已隐藏", text)
        self.assertIn("user_api_key_id=已隐藏", text)

    def test_user_visible_dto_excludes_internal_fields(self):
        items = LogService.build_user_visible_request_log_items([
            {
                "id": 1,
                "request_id": "req_1",
                "model": "gpt-4o",
                "requested_model": "gpt-4o",
                "actual_model": "gpt-4o-mini",
                "channel_name": "OpenAI",
                "channel_id": 12,
                "client_ip": "127.0.0.1",
                "user_id": 7,
                "username": "alice",
                "user_api_key_id": 3,
                "status": "error",
                "error_message": "failed on channel OpenAI actual_model=gpt-4o-mini channel_id=12",
            }
        ])

        public_item = items[0]
        for key in ["actual_model", "channel_name", "channel_id", "client_ip", "user_id", "username", "user_api_key_id"]:
            self.assertNotIn(key, public_item)
        self.assertEqual(public_item["model"], "gpt-4o")
        self.assertNotIn("OpenAI", public_item["error_message"])
        self.assertNotIn("gpt-4o-mini", public_item["error_message"])
        self.assertNotIn("channel_id=12", public_item["error_message"])

    def test_raw_upstream_http_error_is_replaced_with_generic_message(self):
        samples = [
            'Upstream returned HTTP 503: {"error":{"message":"auth_unavailable: no auth available (providers=codex, model=gpt-5.4)","type":"server_error","code":"internal_server_error"}}',
            "Upstream returned HTTP 403: Your request was blocked.",
            '上游服务返回异常（HTTP 429）：{"error":{"code":"model_cooldown","message":"All credentials are cooling down via provider codex"}}',
        ]

        for sample in samples:
            with self.subTest(sample=sample):
                text = LogService._sanitize_user_visible_error_message(sample)
                self.assertEqual(text, "调用失败，渠道异常，请稍后重试")
                self.assertNotIn("Upstream returned", text)
                self.assertNotIn("providers=codex", text)

    def test_agent_visible_dto_keeps_user_identity_but_hides_internal_details(self):
        items = LogService.build_agent_visible_request_log_items([
            {
                "id": 1,
                "request_id": "req_1",
                "model": "claude-opus-4-7",
                "requested_model": "claude-opus-4-7",
                "actual_model": "gpt-5.4",
                "channel_name": "gptstore-codex",
                "channel_id": 12,
                "client_ip": "127.0.0.1",
                "user_id": 7,
                "username": "alice",
                "status": "error",
                "error_message": 'Upstream returned HTTP 503: {"error":{"message":"auth_unavailable providers=codex model=gpt-5.4"}}',
            }
        ])

        public_item = items[0]
        self.assertEqual(public_item["user_id"], 7)
        self.assertEqual(public_item["username"], "alice")
        self.assertEqual(public_item["model"], "claude-opus-4-7")
        self.assertEqual(public_item["error_message"], "调用失败，渠道异常，请稍后重试")
        for key in ["actual_model", "channel_name", "channel_id", "client_ip"]:
            self.assertNotIn(key, public_item)


if __name__ == "__main__":
    unittest.main()
