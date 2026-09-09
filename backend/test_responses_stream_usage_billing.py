import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.proxy_service import ProxyService


class ResponsesStreamUsageBillingTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _request_objects():
        return {
            "db": SimpleNamespace(close=lambda: None),
            "user": SimpleNamespace(),
            "api_key": SimpleNamespace(),
            "channel": SimpleNamespace(
                id=18,
                name="sub2api-codex",
                base_url="https://example.test",
            ),
            "model": SimpleNamespace(security_monitor_enabled=0),
        }

    async def test_completed_usage_is_snapshotted_before_asgi_disconnect(self):
        async def fake_upstream_payloads(*_args, **_kwargs):
            yield {
                "type": "response.output_text.delta",
                "delta": "done",
            }
            yield {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {
                        "input_tokens": 80320,
                        "output_tokens": 946,
                        "input_tokens_details": {"cached_tokens": 77568},
                    },
                },
            }

        finalize = Mock()
        objects = self._request_objects()
        completed_sent = asyncio.Event()

        with (
            patch.object(ProxyService, "_iter_responses_upstream_payloads", new=fake_upstream_payloads),
            patch.object(ProxyService, "_finalize_successful_text_request", finalize),
            patch.object(ProxyService, "_scan_stream_security_output"),
        ):
            response = await ProxyService._stream_responses_request(
                objects["db"],
                objects["user"],
                objects["api_key"],
                objects["channel"],
                objects["model"],
                {"model": "gpt-5.6-terra", "stream": True, "input": "test"},
                "request-id",
                "gpt-5.6-sol",
                "127.0.0.1",
            )

            receive_count = 0

            async def receive():
                nonlocal receive_count
                receive_count += 1
                if receive_count == 1:
                    return {"type": "http.request", "body": b"", "more_body": False}
                await completed_sent.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                if (
                    message["type"] == "http.response.body"
                    and b"response.completed" in message.get("body", b"")
                ):
                    completed_sent.set()

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/v1/responses",
                "headers": [],
                "query_string": b"",
                "http_version": "1.1",
                "scheme": "http",
                "server": ("test", 80),
                "client": ("127.0.0.1", 1),
                "root_path": "",
            }
            await response(scope, receive, send)

        finalize.assert_called_once()
        args = finalize.call_args.args
        self.assertEqual(args[6], 2752)
        self.assertEqual(args[7], 946)
        self.assertEqual(finalize.call_args.kwargs["cache_info"]["upstream_input_tokens"], 2752)
        self.assertEqual(
            finalize.call_args.kwargs["cache_info"]["upstream_cache_read_input_tokens"],
            77568,
        )

    async def test_completed_event_stops_before_upstream_tail_error(self):
        async def fake_upstream_payloads(*_args, **_kwargs):
            yield {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {"input_tokens": 100, "output_tokens": 7},
                },
            }
            raise RuntimeError("post-completion transport reset")

        finalize = Mock()
        failed = Mock()
        objects = self._request_objects()

        with (
            patch.object(ProxyService, "_iter_responses_upstream_payloads", new=fake_upstream_payloads),
            patch.object(ProxyService, "_finalize_successful_text_request", finalize),
            patch.object(ProxyService, "_log_failed_request", failed),
            patch.object(ProxyService, "_record_channel_failure"),
            patch.object(ProxyService, "_scan_stream_security_output"),
        ):
            response = await ProxyService._stream_responses_request(
                objects["db"],
                objects["user"],
                objects["api_key"],
                objects["channel"],
                objects["model"],
                {"model": "gpt-5.6-terra", "stream": True, "input": "test"},
                "request-id-tail",
                "gpt-5.6-sol",
                "127.0.0.1",
            )
            chunks = [chunk async for chunk in response.body_iterator]

        finalize.assert_called_once()
        failed.assert_not_called()
        self.assertEqual(finalize.call_args.args[6:8], (100, 7))
        self.assertFalse(any('"type": "error"' in chunk for chunk in chunks))

    @staticmethod
    def _asgi_scope():
        return {
            "type": "http",
            "method": "POST",
            "path": "/v1/responses",
            "headers": [],
            "query_string": b"",
            "http_version": "1.1",
            "scheme": "http",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1),
            "root_path": "",
        }

    async def test_client_disconnect_still_bills_late_upstream_usage(self):
        created_sent = asyncio.Event()

        async def fake_upstream_payloads(*_args, **_kwargs):
            yield {
                "type": "response.created",
                "response": {"id": "resp_late", "status": "in_progress"},
            }
            await created_sent.wait()
            await asyncio.sleep(0.05)
            yield {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {"input_tokens": 1410, "output_tokens": 181},
                },
            }

        finalize = Mock()
        failed = Mock()
        objects = self._request_objects()

        with (
            patch.object(ProxyService, "_iter_responses_upstream_payloads", new=fake_upstream_payloads),
            patch.object(ProxyService, "_finalize_successful_text_request", finalize),
            patch.object(ProxyService, "_log_failed_request", failed),
            patch.object(ProxyService, "_scan_stream_security_output"),
        ):
            response = await ProxyService._stream_responses_request(
                objects["db"],
                objects["user"],
                objects["api_key"],
                objects["channel"],
                objects["model"],
                {
                    "model": "gpt-5.6-terra",
                    "stream": True,
                    "input": "test",
                    "tools": [{"name": "shell", "description": "x" * 20000}],
                },
                "request-id-late-usage",
                "gpt-5.5",
                "127.0.0.1",
            )

            receive_count = 0

            async def receive():
                nonlocal receive_count
                receive_count += 1
                if receive_count == 1:
                    return {"type": "http.request", "body": b"", "more_body": False}
                await created_sent.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                body = message.get("body", b"")
                if message["type"] == "http.response.body" and b"response.created" in body:
                    created_sent.set()

            await response(self._asgi_scope(), receive, send)

        finalize.assert_called_once()
        failed.assert_not_called()
        self.assertEqual(finalize.call_args.args[6:8], (1410, 181))

    async def test_client_disconnect_without_usage_does_not_estimate(self):
        async def fake_upstream_payloads(*_args, **_kwargs):
            yield {
                "type": "response.created",
                "response": {"id": "resp_empty", "status": "in_progress"},
            }

        finalize = Mock()
        failed = Mock()
        objects = self._request_objects()

        with (
            patch.object(ProxyService, "_iter_responses_upstream_payloads", new=fake_upstream_payloads),
            patch.object(ProxyService, "_finalize_successful_text_request", finalize),
            patch.object(ProxyService, "_log_failed_request", failed),
            patch.object(ProxyService, "_record_channel_failure"),
            patch.object(ProxyService, "_scan_stream_security_output"),
        ):
            response = await ProxyService._stream_responses_request(
                objects["db"],
                objects["user"],
                objects["api_key"],
                objects["channel"],
                objects["model"],
                {
                    "model": "gpt-5.6-terra",
                    "stream": True,
                    "input": "test",
                    "tools": [{"name": "shell", "description": "x" * 20000}],
                },
                "request-id-no-usage",
                "gpt-5.5",
                "127.0.0.1",
            )
            chunks = [chunk async for chunk in response.body_iterator]

        finalize.assert_not_called()
        failed.assert_called_once()
        self.assertTrue(any("response.created" in chunk for chunk in chunks))

    async def test_first_upstream_event_is_forwarded_to_client(self):
        async def fake_upstream_payloads(*_args, **_kwargs):
            yield {
                "type": "response.created",
                "response": {"id": "resp_first", "status": "in_progress"},
            }
            yield {
                "type": "response.output_text.delta",
                "delta": "hello",
            }
            yield {
                "type": "response.completed",
                "response": {
                    "output": [],
                    "usage": {"input_tokens": 10, "output_tokens": 1},
                },
            }

        finalize = Mock()
        objects = self._request_objects()

        with (
            patch.object(ProxyService, "_iter_responses_upstream_payloads", new=fake_upstream_payloads),
            patch.object(ProxyService, "_finalize_successful_text_request", finalize),
            patch.object(ProxyService, "_scan_stream_security_output"),
        ):
            response = await ProxyService._stream_responses_request(
                objects["db"],
                objects["user"],
                objects["api_key"],
                objects["channel"],
                objects["model"],
                {"model": "gpt-5.6-terra", "stream": True, "input": "test"},
                "request-id-first-event",
                "gpt-5.5",
                "127.0.0.1",
            )
            chunks = [chunk async for chunk in response.body_iterator]

        joined = "".join(chunks)
        created_at = joined.find("response.created")
        delta_at = joined.find("response.output_text.delta")
        self.assertGreaterEqual(created_at, 0)
        self.assertGreaterEqual(delta_at, 0)
        self.assertLess(created_at, delta_at)
        self.assertIn("hello", joined)
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args.args[6:8], (10, 1))


if __name__ == "__main__":
    unittest.main()
