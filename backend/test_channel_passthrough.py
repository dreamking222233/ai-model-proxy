import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.services.channel_passthrough_service import (
    ChannelPassthroughService,
    PassthroughCandidate,
    PassthroughUpstreamError,
    UsageObserver,
)


def build_request(path, body, headers=None, query=b""):
    raw_headers = headers or [
        (b"content-type", b"application/json"),
        (b"authorization", b"Bearer sk-user"),
        (b"x-custom-feature", b"keep-me"),
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": raw_headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


class FakeClientWebSocket:
    def __init__(self, first_message, followups=None, receive_initial=False):
        self.first_message = first_message
        self.receive_initial = receive_initial
        self.followups = asyncio.Queue()
        for message in followups or []:
            key = "bytes" if isinstance(message, bytes) else "text"
            self.followups.put_nowait({"type": "websocket.receive", key: message})
        self.sent = []
        self.closed = []
        self.scope = {
            "headers": [(b"authorization", b"Bearer sk-user")],
            "query_string": b"trace=1",
        }
        self.url = SimpleNamespace(path="/v1/responses")

    async def receive_text(self):
        return self.first_message

    async def receive(self):
        if self.receive_initial:
            self.receive_initial = False
            key = "bytes" if isinstance(self.first_message, bytes) else "text"
            return {"type": "websocket.receive", key: self.first_message}
        return await self.followups.get()

    async def send_text(self, payload):
        self.sent.append(payload)

    async def send_bytes(self, payload):
        self.sent.append(payload)

    async def close(self, code=1000, reason=""):
        self.closed.append((code, reason))


class FakeUpstreamWebSocket:
    def __init__(self, events, send_error=None):
        self.events = list(events)
        self.send_error = send_error
        self.sent = []
        self.closed = False

    async def send(self, payload):
        self.sent.append(payload)
        if self.send_error:
            raise self.send_error

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.events:
            raise StopAsyncIteration
        event = self.events.pop(0)
        if isinstance(event, BaseException):
            raise event
        await asyncio.sleep(0)
        return event

    async def close(self):
        self.closed = True


class ChannelPassthroughUnitTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.channel = Channel(
            id=7,
            name="native",
            base_url="https://upstream.example/v1",
            api_key="sk-upstream",
            protocol_type="openai",
            auth_header_type="authorization",
            priority=1,
            enabled=1,
            passthrough_enabled=1,
        )
        self.model = SimpleNamespace(
            id=3,
            model_name="claude-opus-5",
            model_type="chat",
            billing_type="token",
        )

    def test_url_keeps_native_endpoint_without_duplicate_v1(self):
        url = ChannelPassthroughService._build_url(
            self.channel,
            "/v1/responses",
            b"trace=1",
        )
        self.assertEqual(url, "https://upstream.example/v1/responses?trace=1")

    def test_passthrough_candidates_snapshot_orm_values_before_session_release(self):
        model = UnifiedModel(
            id=3,
            model_name="claude-opus-5",
            model_type="chat",
            billing_type="token",
            enabled=1,
        )
        with (
            patch(
                "app.services.channel_passthrough_service.ModelService.get_enabled_model_by_name",
                return_value=model,
            ),
            patch(
                "app.services.channel_passthrough_service.ModelService.get_available_channels",
                return_value=[(self.channel, "claude-opus-5")],
            ),
        ):
            candidate = ChannelPassthroughService.get_candidates(
                SimpleNamespace(), "claude-opus-5", "responses"
            )[0]

        self.assertIsInstance(candidate.channel, SimpleNamespace)
        self.assertIsInstance(candidate.unified_model, SimpleNamespace)
        self.assertEqual(candidate.channel.id, 7)
        self.assertEqual(candidate.unified_model.model_name, "claude-opus-5")
        model.model_name = "mutated-after-selection"
        self.channel.name = "mutated-after-selection"
        self.assertEqual(candidate.channel.name, "native")
        self.assertEqual(candidate.unified_model.model_name, "claude-opus-5")

    def test_headers_replace_platform_credentials_and_keep_business_headers(self):
        headers = ChannelPassthroughService._request_headers(
            self.channel,
            [
                (b"authorization", b"Bearer sk-user"),
                (b"x-api-key", b"sk-user"),
                (b"connection", b"keep-alive, x-hop"),
                (b"x-hop", b"drop"),
                (b"anthropic-beta", b"tools-2025"),
                (b"x-feature", b"one"),
                (b"x-feature", b"two"),
            ],
        )
        self.assertNotIn((b"authorization", b"Bearer sk-user"), headers)
        self.assertNotIn((b"x-hop", b"drop"), headers)
        self.assertIn((b"authorization", b"Bearer sk-upstream"), headers)
        self.assertIn((b"anthropic-beta", b"tools-2025"), headers)
        self.assertEqual([value for key, value in headers if key == b"x-feature"], [b"one", b"two"])

    def test_fragmented_openai_sse_usage_is_observed_without_rewriting(self):
        observer = UsageObserver("openai", self.channel)
        chunks = [
            b'data: {"id":"x","model":"real","choices":[{"delta":{"content":"ok"}}]}\n',
            b'\ndata: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":12,',
            b'"completion_tokens":3}}\n\ndata: [DONE]\n\n',
        ]
        for chunk in chunks:
            observer.feed_sse(chunk)
        self.assertTrue(observer.usage_seen)
        self.assertTrue(observer.completed)
        self.assertEqual(observer.summary["input_tokens"], 12)
        self.assertEqual(observer.summary["output_tokens"], 3)
        self.assertEqual(b"".join(chunks).count(b'"model":"real"'), 1)

    def test_anthropic_usage_merges_start_and_delta_snapshots(self):
        observer = UsageObserver("anthropic", self.channel)
        observer.feed_json({"type": "message_start", "message": {"usage": {"input_tokens": 20}}})
        observer.feed_json({"type": "message_delta", "usage": {"output_tokens": 4}})
        observer.feed_json({"type": "message_stop"})
        self.assertTrue(observer.completed)
        self.assertEqual(observer.summary["input_tokens"], 20)
        self.assertEqual(observer.summary["output_tokens"], 4)

    def test_unterminated_sse_event_is_observed_on_finish(self):
        observer = UsageObserver("responses", self.channel)
        observer.feed_sse(
            b'data: {"type":"response.completed","response":{"id":"r1","usage":{"input_tokens":4,"output_tokens":2}}}'
        )
        observer.finish_sse()
        self.assertTrue(observer.completed)
        self.assertEqual(observer.summary["input_tokens"], 4)
        self.assertEqual(observer.summary["output_tokens"], 2)

    async def test_non_stream_body_and_response_are_not_rewritten(self):
        raw_body = (
            b'{"model":"claude-opus-5","messages":[{"role":"system","content":"mine"}],'
            b'"thinking":{"effort":"xhigh"},"unknown":{"keep":true}}'
        )
        upstream_body = b'{"id":"native","model":"upstream-visible","usage":{"prompt_tokens":9,"completion_tokens":2}}'
        captured = {}

        def handler(request):
            captured["body"] = request.content
            captured["headers"] = request.headers
            return httpx.Response(200, content=upstream_body, headers={"content-type": "application/json"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        request = build_request("/v1/chat/completions", raw_body)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        with (
            patch("app.services.channel_passthrough_service.httpx.AsyncClient", return_value=client),
            patch.object(ChannelPassthroughService, "_build_billing", return_value=(None, {})),
            patch.object(ChannelPassthroughService, "_finalize") as finalize,
            patch("app.services.proxy_service.ProxyService._billing_concurrency_lease_ttl_seconds", return_value=7200),
        ):
            response = await ChannelPassthroughService.forward_http(
                None,
                SimpleNamespace(id=1),
                SimpleNamespace(id=2),
                candidate,
                json.loads(raw_body),
                raw_body,
                list(request.scope["headers"]),
                request.url.path,
                b"",
                "127.0.0.1",
                "openai",
            )

        self.assertEqual(captured["body"], raw_body)
        self.assertEqual(response.body, upstream_body)
        self.assertEqual(captured["headers"]["authorization"], "Bearer sk-upstream")
        self.assertNotIn("connection", captured["headers"])
        self.assertNotIn("user-agent", captured["headers"])
        self.assertNotIn("accept", captured["headers"])
        observer = finalize.call_args.args[5]
        self.assertEqual(observer.summary["input_tokens"], 9)
        self.assertEqual(observer.summary["output_tokens"], 2)

    async def test_dispatch_falls_back_from_native_channel_to_managed_channel(self):
        body = {"model": "claude-opus-5", "messages": [{"role": "user", "content": "hello"}]}
        raw = json.dumps(body, separators=(",", ":")).encode()
        request = build_request("/v1/chat/completions", raw)
        passthrough = PassthroughCandidate(self.channel, self.model, "passthrough")
        normal_channel = Channel(id=8, name="managed", priority=2, enabled=1)
        normal = PassthroughCandidate(normal_channel, None, "normal")
        managed = AsyncMock(return_value=SimpleNamespace(status_code=200, body=b"managed"))
        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[passthrough]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[normal]),
            patch.object(ChannelPassthroughService, "merge_candidates", return_value=[passthrough, normal]),
            patch.object(
                ChannelPassthroughService,
                "forward_http",
                side_effect=PassthroughUpstreamError(503, b"busy", []),
            ),
            patch("app.services.proxy_service.ProxyService._record_channel_failure"),
        ):
            response = await ChannelPassthroughService.dispatch_http(
                request,
                SimpleNamespace(),
                SimpleNamespace(),
                SimpleNamespace(),
                body,
                "openai",
                managed,
            )
        self.assertEqual(response.body, b"managed")
        managed.assert_awaited_once()
        self.assertEqual(managed.await_args.args[1], [8])

    async def test_dispatch_without_native_candidate_uses_legacy_once(self):
        body = {"model": "gpt-test", "messages": [{"role": "user", "content": "hello"}]}
        request = build_request("/v1/chat/completions", json.dumps(body).encode())
        managed = AsyncMock(return_value=SimpleNamespace(status_code=200))
        normal_channel = Channel(id=9, name="managed", priority=1, enabled=1)
        normal = PassthroughCandidate(normal_channel, None, "normal")
        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[normal]),
        ):
            await ChannelPassthroughService.dispatch_http(
                request, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                body, "openai", managed,
            )
        managed.assert_awaited_once()
        self.assertEqual(managed.await_args.args[0], body)
        self.assertEqual(managed.await_args.args[1], [9])

    async def test_streaming_response_bytes_are_not_rewritten(self):
        raw_body = b'{"model":"claude-opus-5","stream":true,"unknown":"keep"}'
        chunks = [
            b'data: {"id":"x","model":"native","choices":[{"delta":{"content":"a"}}]}\n\n',
            b'data: {"choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1}}\n\n',
            b'data: [DONE]\n\n',
        ]
        captured = {}

        def handler(request):
            captured["body"] = request.content
            return httpx.Response(
                200,
                stream=ChunkStream(chunks),
                headers={"content-type": "text/event-stream"},
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        request = build_request("/v1/chat/completions", raw_body)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        with (
            patch("app.services.channel_passthrough_service.httpx.AsyncClient", return_value=client),
            patch.object(ChannelPassthroughService, "_build_billing", return_value=(None, {})),
            patch.object(ChannelPassthroughService, "_finalize") as finalize,
            patch("app.services.proxy_service.ProxyService._billing_concurrency_lease_ttl_seconds", return_value=7200),
        ):
            response = await ChannelPassthroughService.forward_http(
                None, SimpleNamespace(id=1), SimpleNamespace(id=2), candidate,
                json.loads(raw_body), raw_body, list(request.scope["headers"]),
                request.url.path, b"", "127.0.0.1", "openai",
            )
            output = b"".join([chunk async for chunk in response.body_iterator])

        self.assertEqual(captured["body"], raw_body)
        self.assertEqual(output, b"".join(chunks))
        self.assertEqual(finalize.call_count, 1)
        self.assertEqual(finalize.call_args.args[5].summary["input_tokens"], 2)

    async def test_count_tokens_returns_native_client_error_without_local_fallback(self):
        raw_body = b'{"model":"claude-opus-5","messages":[]}'
        request = build_request("/v1/messages/count_tokens", raw_body)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        client = AsyncMock()
        client.send.return_value = httpx.Response(
            400,
            content=b'{"type":"error","error":{"message":"native invalid"}}',
            headers={"content-type": "application/json"},
        )
        client.aclose = AsyncMock()
        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[candidate]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[]),
            patch("app.services.channel_passthrough_service.httpx.AsyncClient", return_value=client),
        ):
            response = await ChannelPassthroughService.forward_count_tokens(
                request, SimpleNamespace(), json.loads(raw_body)
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"native invalid", response.body)

    async def test_prefetch_commits_unterminated_valid_sse_event(self):
        async def source():
            yield (
                b'data: {"type":"response.completed","response":'
                b'{"usage":{"input_tokens":1,"output_tokens":1}}}\n'
            )

        response = StreamingResponse(source())
        response, usable = await ChannelPassthroughService._prefetch_stream(response, "responses")
        output = b"".join([chunk async for chunk in response.body_iterator])
        self.assertTrue(usable)
        self.assertIn(b"response.completed", output)

    async def test_websocket_prewarm_is_forwarded_without_billing(self):
        first = json.dumps({
            "type": "response.create", "model": "claude-opus-5",
            "generate": False, "unknown": {"keep": True},
        }, separators=(",", ":"))
        upstream = FakeUpstreamWebSocket([
            json.dumps({"type": "response.created", "response": {"id": "r-pre"}}),
            json.dumps({
                "type": "response.completed",
                "response": {"id": "r-pre", "usage": {"input_tokens": 0, "output_tokens": 0}},
            }),
        ])
        websocket = FakeClientWebSocket(first)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        connect = AsyncMock(return_value=upstream)
        with (
            patch("websockets.connect", connect),
            patch("app.services.channel_passthrough_service.release_session_connection"),
            patch.object(ChannelPassthroughService, "_build_billing") as build_billing,
            patch.object(ChannelPassthroughService, "_finalize") as finalize,
        ):
            await ChannelPassthroughService._relay_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                candidate, first, json.loads(first), "127.0.0.1",
            )
        self.assertEqual(upstream.sent, [first])
        build_billing.assert_not_called()
        finalize.assert_not_called()

    async def test_websocket_completed_usage_is_billed_once(self):
        first = json.dumps({"type": "response.create", "model": "claude-opus-5"})
        terminal = json.dumps({
            "type": "response.completed",
            "response": {"id": "r1", "usage": {"input_tokens": 7, "output_tokens": 3}},
        })
        upstream = FakeUpstreamWebSocket([
            json.dumps({"type": "response.created", "response": {"id": "r1"}}),
            terminal,
            terminal,
        ])
        websocket = FakeClientWebSocket(first)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        with (
            patch("websockets.connect", AsyncMock(return_value=upstream)),
            patch("app.services.channel_passthrough_service.release_session_connection"),
            patch.object(ChannelPassthroughService, "_build_billing", return_value=(None, {})),
            patch.object(ChannelPassthroughService, "_finalize") as finalize,
            patch("app.services.proxy_service.ProxyService._billing_concurrency_lease_ttl_seconds", return_value=7200),
        ):
            await ChannelPassthroughService._relay_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                candidate, first, json.loads(first), "127.0.0.1",
            )
        self.assertEqual(upstream.sent, [first])
        self.assertEqual(finalize.call_count, 1)
        observer = finalize.call_args.args[5]
        self.assertEqual(observer.summary["input_tokens"], 7)
        self.assertEqual(observer.summary["output_tokens"], 3)

    async def test_websocket_append_starts_next_turn_on_same_channel(self):
        first = json.dumps({"type": "response.create", "model": "claude-opus-5"})
        followup = json.dumps({"type": "response.append", "input": "next"}).encode()
        allow_followup = asyncio.Event()
        followup_sent = asyncio.Event()

        class SequentialUpstream(FakeUpstreamWebSocket):
            def __init__(self):
                super().__init__([])
                self.index = 0

            async def send(self, payload):
                self.sent.append(payload)
                if len(self.sent) == 2:
                    followup_sent.set()

            async def __anext__(self):
                self.index += 1
                if self.index == 1:
                    return json.dumps({"type": "response.created", "response": {"id": "r1"}})
                if self.index == 2:
                    allow_followup.set()
                    return json.dumps({
                        "type": "response.completed",
                        "response": {"id": "r1", "usage": {"input_tokens": 5, "output_tokens": 1}},
                    })
                if self.index == 3:
                    await followup_sent.wait()
                    return json.dumps({
                        "type": "response.completed",
                        "response": {"id": "r1", "usage": {"input_tokens": 5, "output_tokens": 1}},
                    })
                if self.index == 4:
                    return json.dumps({"type": "response.created", "response": {"id": "r2"}})
                if self.index == 5:
                    return json.dumps({
                        "type": "response.completed",
                        "response": {"id": "r2", "usage": {"input_tokens": 6, "output_tokens": 2}},
                    })
                raise StopAsyncIteration

        class GatedClient(FakeClientWebSocket):
            async def receive(self):
                await allow_followup.wait()
                return await super().receive()

        upstream = SequentialUpstream()
        websocket = GatedClient(first, [followup])
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        with (
            patch("websockets.connect", AsyncMock(return_value=upstream)),
            patch("app.services.channel_passthrough_service.release_session_connection"),
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[candidate]),
            patch.object(ChannelPassthroughService, "_build_billing", return_value=(None, {})) as build_billing,
            patch.object(ChannelPassthroughService, "_finalize") as finalize,
            patch("app.services.proxy_service.ProxyService._billing_concurrency_lease_ttl_seconds", return_value=7200),
        ):
            await ChannelPassthroughService._relay_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                candidate, first, json.loads(first), "127.0.0.1",
            )
        self.assertEqual(upstream.sent, [first, followup])
        self.assertEqual(build_billing.call_count, 2)
        self.assertEqual(finalize.call_count, 2)
        self.assertEqual(finalize.call_args_list[1].args[5].summary["input_tokens"], 6)

    async def test_websocket_handshake_failure_replays_first_message_to_managed(self):
        first = json.dumps({"type": "response.create", "model": "claude-opus-5"})
        websocket = FakeClientWebSocket(first, receive_initial=True)
        passthrough = PassthroughCandidate(self.channel, self.model, "passthrough")
        normal_channel = Channel(id=8, name="managed", priority=2, enabled=1)
        normal = PassthroughCandidate(normal_channel, None, "normal")
        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[passthrough]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[normal]),
            patch.object(ChannelPassthroughService, "merge_candidates", return_value=[passthrough, normal]),
            patch.object(ChannelPassthroughService, "_relay_websocket", side_effect=OSError("connect failed")),
            patch(
                "app.services.proxy_service.ProxyService.handle_responses_websocket",
                AsyncMock(return_value=True),
            ) as managed,
            patch("app.services.proxy_service.ProxyService._record_channel_failure"),
        ):
            handled, replay, channel_ids = await ChannelPassthroughService.dispatch_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "127.0.0.1"
            )
        self.assertTrue(handled)
        self.assertIsNone(replay)
        self.assertIsNone(channel_ids)
        managed.assert_awaited_once()
        self.assertEqual(managed.await_args.kwargs["initial_message"], first)
        self.assertEqual(managed.await_args.kwargs["_allowed_channel_ids"], [8])

    async def test_websocket_initial_binary_frame_is_preserved(self):
        first = json.dumps({"type": "response.create", "model": "claude-opus-5"}).encode()
        websocket = FakeClientWebSocket(first, receive_initial=True)
        candidate = PassthroughCandidate(self.channel, self.model, "passthrough")
        relay = AsyncMock()
        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[candidate]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[]),
            patch.object(ChannelPassthroughService, "merge_candidates", return_value=[candidate]),
            patch.object(ChannelPassthroughService, "_relay_websocket", relay),
        ):
            handled, replay, channel_ids = await ChannelPassthroughService.dispatch_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "127.0.0.1"
            )
        self.assertTrue(handled)
        self.assertIsNone(replay)
        self.assertIsNone(channel_ids)
        self.assertEqual(relay.await_args.args[5], first)

    async def test_websocket_tries_later_passthrough_after_managed_candidate(self):
        first = json.dumps({"type": "response.create", "model": "claude-opus-5"})
        websocket = FakeClientWebSocket(first, receive_initial=True)
        pass_a = PassthroughCandidate(self.channel, self.model, "passthrough")
        normal_channel = Channel(id=8, name="managed", priority=2, enabled=1)
        normal = PassthroughCandidate(normal_channel, None, "normal")
        pass_c_channel = Channel(
            id=9, name="native-c", base_url="https://c.example/v1", api_key="sk-c",
            protocol_type="openai", auth_header_type="authorization", priority=3,
            enabled=1, passthrough_enabled=1,
        )
        pass_c = PassthroughCandidate(pass_c_channel, self.model, "passthrough")
        order = []

        async def relay(*args):
            channel_id = args[4].channel.id
            order.append(channel_id)
            if channel_id == 7:
                raise OSError("a failed")

        async def managed(*_args, **_kwargs):
            order.append(8)
            return False

        with (
            patch.object(ChannelPassthroughService, "get_candidates", return_value=[pass_a, pass_c]),
            patch.object(ChannelPassthroughService, "get_normal_candidates", return_value=[normal]),
            patch.object(
                ChannelPassthroughService, "merge_candidates",
                return_value=[pass_a, normal, pass_c],
            ),
            patch.object(ChannelPassthroughService, "_relay_websocket", side_effect=relay),
            patch(
                "app.services.proxy_service.ProxyService.handle_responses_websocket",
                side_effect=managed,
            ),
            patch("app.services.proxy_service.ProxyService._record_channel_failure"),
        ):
            handled, _, _ = await ChannelPassthroughService.dispatch_websocket(
                websocket, SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "127.0.0.1"
            )
        self.assertTrue(handled)
        self.assertEqual(order, [7, 8, 9])


if __name__ == "__main__":
    unittest.main()
