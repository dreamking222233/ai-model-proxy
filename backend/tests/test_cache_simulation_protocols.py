"""Real local decisions through native transports and managed/bridge finalizers."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import settings
from app.models.cache_simulation import CacheSimulationDecision
from app.models.channel import Channel
from app.models.log import ConsumptionRecord
from app.services.cache_simulation_service import CacheSimulationService as Service
from app.services.anthropic_prompt_cache_service import AnthropicPromptCacheService
from app.services.channel_passthrough_service import ChannelPassthroughService as Native, PassthroughCandidate
from app.services.proxy_service import ProxyService
from test_cache_simulation import isolated_redis, ledger, simulation  # reusable isolated fixtures


class Chunks(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body[:33]
        yield self.body[33:]


def upstream_payload(protocol, n):
    plain = 28000 + n * 1000
    if protocol == "anthropic":
        usage = {"input_tokens": plain, "output_tokens": 500, "cache_read_input_tokens": 1000,
                 "cache_creation_input_tokens": 250, "cache_creation": {"ephemeral_5m_input_tokens": 250, "ephemeral_1h_input_tokens": 0}}
        return {"type": "message", "stop_reason": "end_turn", "content": [], "usage": usage}
    usage = {"input_tokens": plain + 1250, "output_tokens": 500,
             "input_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 250}}
    if protocol == "responses":
        return {"id": f"resp-{n}", "object": "response", "status": "completed", "output": [], "usage": usage}
    return {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "usage": usage}


def record_rows(simulation):
    with simulation.factory() as db:
        return [Service.record_dto(row, detail=True) for row in db.query(CacheSimulationDecision).order_by(CacheSimulationDecision.id).all()]


@pytest.mark.parametrize("protocol", ["anthropic", "openai", "responses"])
@pytest.mark.parametrize("stream", [False, True])
def test_native_http_and_sse_simulate_third_without_rewriting_wire(simulation, protocol, stream):
    channel = Channel(id=70, name="native-test", base_url="https://upstream.test", api_key="test-only",
                      auth_header_type="authorization", protocol_type=protocol)
    candidate = PassthroughCandidate(channel, simulation.model, "passthrough")
    user, api_key = SimpleNamespace(id=1, username="cache-test"), SimpleNamespace(id=1)

    async def run():
        for n in (1, 2, 3):
            payload = upstream_payload(protocol, n)
            request_data = {"model": "claude-test", "stream": stream}
            request_body = json.dumps(request_data).encode()
            if stream:
                if protocol == "anthropic":
                    initial = {"type": "message_start", "message": {"usage": {**payload["usage"], "input_tokens": 60000, "output_tokens": 0}}}
                    events = [initial, {"type": "message_delta", "usage": payload["usage"]}, {"type": "message_stop"}]
                elif protocol == "responses":
                    events = [{"type": "response.completed", "response": payload}]
                else:
                    events = [payload]
                wire = b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events)
                wire += b"data: [DONE]\n\n"
            else:
                wire = json.dumps(payload).encode()

            def handler(request):
                assert request.content == request_body
                return httpx.Response(200, stream=Chunks(wire), headers={"content-type": "text/event-stream" if stream else "application/json"})
            client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with (patch("app.services.channel_passthrough_service.httpx.AsyncClient", return_value=client),
                  patch.object(Native, "_build_billing", return_value=(None, simulation.binding(n, protocol=protocol))),
                  patch.object(ProxyService, "_billing_concurrency_lease_ttl_seconds", return_value=7200)):
                response = await Native.forward_http(None, user, api_key, candidate, request_data, request_body,
                    [(b"content-type", b"application/json")], "/v1/messages" if protocol == "anthropic" else "/v1/responses" if protocol == "responses" else "/v1/chat/completions",
                    b"", "127.0.0.1", protocol)
                actual = b"".join([chunk async for chunk in response.body_iterator]) if stream else response.body
            assert actual == wire
    asyncio.run(run())
    rows = record_rows(simulation)
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    last = rows[-1]
    assert last["usage"]["raw"] == {"input": 31000, "output": 500, "read": 1000, "creation": 250}
    assert last["usage"]["effective"]["output"] == 500 and last["usage"]["effective"]["creation"] == 250
    assert all(row["accounting_status"] == "settled" for row in rows)


class ClientSocket:
    def __init__(self):
        self.sent = []
        self.scope = {"headers": [], "query_string": b""}
        self.url = SimpleNamespace(path="/v1/responses")

    async def receive(self):
        await asyncio.Future()

    async def send_text(self, payload):
        self.sent.append(payload)

    async def send_bytes(self, payload):
        self.sent.append(payload)

    async def close(self, **kwargs):
        pass


class UpstreamSocket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0)
        try:
            return next(self.events)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        pass


def test_native_websocket_completed_duplicates_bill_once_per_turn(simulation):
    channel = Channel(id=70, name="native-test", base_url="https://upstream.test", api_key="test-only", protocol_type="responses")
    candidate = PassthroughCandidate(channel, simulation.model, "passthrough")
    async def run():
        for n in (1, 2, 3):
            terminal = json.dumps({"type": "response.completed", "response": upstream_payload("responses", n)})
            upstream, client = UpstreamSocket([terminal, terminal]), ClientSocket()
            data = {"type": "response.create", "model": "claude-test"}
            first = json.dumps(data)
            with (patch("websockets.connect", AsyncMock(return_value=upstream)),
                  patch("app.services.channel_passthrough_service.release_session_connection"),
                  patch.object(Native, "_build_billing", return_value=(None, simulation.binding(n, protocol="responses"))),
                  patch.object(ProxyService, "_billing_concurrency_lease_ttl_seconds", return_value=7200)):
                await Native._relay_websocket(client, None, SimpleNamespace(id=1, username="cache-test"),
                    SimpleNamespace(id=1), candidate, first, data, "127.0.0.1")
            assert upstream.sent == [first]
            assert client.sent == [terminal, terminal]
    asyncio.run(run())
    assert [row["outcome"] for row in record_rows(simulation)] == ["observing", "observing", "simulated"]
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3


def test_native_websocket_incremental_append_uses_completed_parent(simulation):
    """One real connection with only incremental inputs must retain its lineage."""
    channel = Channel(id=70, name="native-test", base_url="https://upstream.test", api_key="test-only", protocol_type="responses")
    candidate = PassthroughCandidate(channel, simulation.model, "passthrough")
    frames = [json.dumps({"type": "response.create" if n == 1 else "response.append",
                          "model": "claude-test", "input": "继续"}) for n in (1, 2, 3)]
    terminals = [json.dumps({"type": "response.completed", "response": upstream_payload("responses", n)}) for n in (1, 2, 3)]

    async def run():
        class InteractiveClient(ClientSocket):
            def __init__(self):
                super().__init__()
                self.incoming = asyncio.Queue()
                self.closed = []

            async def receive(self):
                return await self.incoming.get()

            async def send_text(self, payload):
                await super().send_text(payload)
                index = len(self.sent)
                await self.incoming.put({"type": "websocket.receive", "text": frames[index]}
                    if index < len(frames) else {"type": "websocket.disconnect"})

            async def close(self, **kwargs):
                self.closed.append(kwargs)

        class InteractiveUpstream(UpstreamSocket):
            def __init__(self):
                super().__init__([])
                self.incoming = asyncio.Queue()

            async def send(self, payload):
                await super().send(payload)
                await self.incoming.put(terminals[len(self.sent) - 1])

            async def __anext__(self):
                return await self.incoming.get()

        upstream, client = InteractiveUpstream(), InteractiveClient()
        with (simulation.factory() as db,
              patch("websockets.connect", AsyncMock(return_value=upstream)),
              patch("app.services.channel_passthrough_service.release_session_connection"),
              patch.object(Native, "get_candidates", return_value=[candidate]),
              patch.object(ProxyService, "_resolve_group_billing_context", return_value={"group_id_snapshot": 11, "group_name_snapshot": "claude-aws", "group_multiplier_snapshot": 2}),
              patch.object(ProxyService, "_build_text_quota_precheck", return_value=simulation.context),
              patch.object(ProxyService, "_assert_text_request_allowed", return_value=None),
              patch.object(ProxyService, "_billing_concurrency_lease_ttl_seconds", return_value=7200)):
            # Exercise the actual _build_billing capture/binding path, without a supplied session.
            await asyncio.wait_for(Native._relay_websocket(client, db, SimpleNamespace(id=1, username="cache-test"),
                SimpleNamespace(id=1), candidate, frames[0], json.loads(frames[0]), "127.0.0.1"), timeout=5)
        assert not client.closed
        assert upstream.sent == frames
        assert client.sent == terminals

    asyncio.run(run())
    rows = record_rows(simulation)
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    assert len({row["session_digest"] for row in rows}) == 1
    assert [row["identity_source"] for row in rows] == ["content_prefix", "response_lineage", "response_lineage"]
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3


def test_managed_responses_stream_finalizer_simulates_once(simulation):
    channel = Channel(id=70, name="managed-test", base_url="https://upstream.test", api_key="test-only", protocol_type="responses")
    async def run():
        for n in (1, 2, 3):
            payload = {"type": "response.completed", "response": upstream_payload("responses", n)}
            async def upstream(*args, **kwargs):
                yield payload
            with (patch.object(ProxyService, "_iter_responses_upstream_payloads", new=upstream),
                  patch.object(ProxyService, "_scan_stream_security_output")):
                response = await ProxyService._stream_responses_request(
                    SimpleNamespace(close=lambda: None), SimpleNamespace(id=1, username="cache-test"), SimpleNamespace(id=1),
                    channel, simulation.model, {"model": "claude-test", "input": "test", "stream": True},
                    f"managed-{n}", "claude-test", "127.0.0.1", billing_context=simulation.binding(n, protocol="responses"))
                wire = "".join([chunk async for chunk in response.body_iterator])
                assert '"cached_tokens": 1000' in wire
    asyncio.run(run())
    assert [row["outcome"] for row in record_rows(simulation)] == ["observing", "observing", "simulated"]


@pytest.mark.parametrize("audit_enabled", [False, True])
def test_managed_anthropic_audit_preserves_zero_input_one_output(
        simulation, monkeypatch, caplog, audit_enabled):
    channel = Channel(id=70, name="managed-anthropic", base_url="https://upstream.test", api_key="test-only",
                      auth_header_type="authorization", protocol_type="anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_USAGE_AUDIT_CHANNEL_IDS", [70] if audit_enabled else [])
    caplog.set_level("INFO", logger="app.services.proxy_service")
    events = [
        {"type": "message_start", "message": {"id": "test-message", "role": "assistant", "content": [],
            "usage": {"input_tokens": 60000, "output_tokens": 0, "cache_read_input_tokens": 5000}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": " "}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "max_tokens"}, "usage": {
            "input_tokens": 0, "output_tokens": 1, "cache_read_input_tokens": 50865,
            "cache_creation_input_tokens": 0, "private_metadata": "SECRET"}},
        {"type": "message_stop"},
    ]
    wire = b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events)
    data = {"model": "claude-test", "max_tokens": 128000, "stream": True,
            "messages": [{"role": "user", "content": "test"}]}

    def handler(request):
        assert json.loads(request.content)["max_tokens"] == 128000
        return httpx.Response(200, stream=Chunks(wire), headers={"content-type": "text/event-stream"})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with (patch("app.services.proxy_service.httpx.AsyncClient", return_value=client),
              patch.object(AnthropicPromptCacheService, "build_request_variants", return_value=[
                  {"request_data": data, "header_overrides": {}, "meta": {"attempted": False}}]),
              patch.object(ProxyService, "_scan_stream_security_output")):
            response = await ProxyService._stream_anthropic_request(
                SimpleNamespace(close=lambda: None), SimpleNamespace(id=1, username="cache-test"),
                SimpleNamespace(id=1), channel, simulation.model, data, "managed-audit", "claude-test",
                "127.0.0.1", billing_context=simulation.binding(1))
            result = "".join([chunk async for chunk in response.body_iterator])
            assert '"input_tokens": 0' in result and '"output_tokens": 1' in result

    asyncio.run(run())
    rows = record_rows(simulation)
    assert len(rows) == 1 and rows[0]["accounting_status"] == "settled"
    assert rows[0]["outcome"] == "upstream_good"
    assert rows[0]["usage"]["raw"] == rows[0]["usage"]["effective"] == {
        "input": 0, "output": 1, "read": 50865, "creation": 0}
    audits = [r.getMessage() for r in caplog.records if "Anthropic usage audit" in r.getMessage()]
    assert len(audits) == int(audit_enabled)
    if audits:
        trace = json.loads(audits[0].split("trace=", 1)[1])
        assert trace["usage_events"] == 2
        assert trace["fragments"][0]["usage"]["input_tokens"] == 60000
        assert trace["fragments"][-1]["merged"]["input_tokens"] == 0
        assert trace["fragments"][-1]["merged"]["output_tokens"] == 1
        assert trace["fragments"][-1]["stop_reason"] == "max_tokens"
        assert "SECRET" not in audits[0] and "private_metadata" not in audits[0]
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 1


def test_managed_anthropic_usage_audit_is_bounded_and_filters_untrusted_fields():
    audit = {"usage_events": 0, "fragments": []}
    for n in range(8):
        usage = {"input_tokens": n, "output_tokens": 0, "content": "SECRET",
                 "cache_creation": {"ephemeral_5m_input_tokens": 30, "private": "SECRET"}}
        ProxyService._record_anthropic_usage_audit(audit, "SECRET", usage, usage, {"private": "SECRET"})
    assert audit["usage_events"] == 8 and len(audit["fragments"]) == 4
    assert audit["fragments"][0]["usage"]["input_tokens"] == 0
    assert audit["fragments"][-1]["usage"]["input_tokens"] == 7
    assert audit["fragments"][-1]["usage"]["cache_creation.ephemeral_5m_input_tokens"] == 30
    assert audit["fragments"][-1]["usage"]["output_tokens"] == 0
    assert audit["fragments"][-1]["event"] == audit["fragments"][-1]["stop_reason"] == "other"
    assert "SECRET" not in json.dumps(audit) and "private" not in json.dumps(audit)


def test_anthropic_responses_bridge_bills_once_with_original_client_usage(simulation):
    channel = Channel(id=70, name="bridge-test", base_url="https://upstream.test", api_key="test-only", protocol_type="responses")

    async def passthrough_cache(**kwargs):
        return await kwargs["upstream_call"](), None

    async def run():
        for n in (1, 2, 3):
            payload = upstream_payload("responses", n)
            with (patch.object(ProxyService, "_post_with_retries", AsyncMock(return_value=httpx.Response(200, json=payload))),
                  patch("app.services.proxy_service.CacheMiddleware.wrap_request", side_effect=passthrough_cache),
                  patch("app.services.proxy_service.release_session_connection"),
                  patch.object(ProxyService, "_log_responses_request_json")):
                response = await ProxyService._non_stream_anthropic_via_responses_request(
                    None, SimpleNamespace(id=1, username="cache-test"), SimpleNamespace(id=1), channel, simulation.model,
                    {"model": "claude-test", "messages": [{"role": "user", "content": "test"}], "max_tokens": 1000},
                    f"bridge-{n}", "claude-test", "127.0.0.1", billing_context=simulation.binding(n, protocol="anthropic"))
            actual = json.loads(response.body)
            assert actual["usage"]["input_tokens"] == payload["usage"]["input_tokens"]
            assert actual["usage"]["output_tokens"] == 500

    asyncio.run(run())
    rows = record_rows(simulation)
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    assert rows[-1]["usage"]["raw"] == {"input": 31000, "output": 500, "read": 1000, "creation": 250}
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3


@pytest.mark.parametrize("path", ["anthropic", "openai", "openai_via_anthropic"])
@pytest.mark.parametrize("case", ["complete", "complete_zero", "split_usage", "error", "error_then_complete", "incomplete",
                                  "missing_input", "missing_output", "invalid_usage", "invalid_then_corrected", "conflicting_usage",
                                  "malformed_usage", "json_complete", "json_missing_output", "cache_overflow_corrected",
                                  "inclusive_conflict", "json_inclusive_conflict", "output_alias_only", "json_output_alias_only"])
def test_non_stream_sse_compatibility_requires_real_completion_and_usage(simulation, path, case):
    """Exercise the actual compatibility parser and billing path after two observations."""
    protocol = "openai" if path == "openai" else "anthropic"
    client_protocol = "anthropic" if path == "anthropic" else "openai"
    simulation.run(1, context_override=simulation.binding(1, protocol=client_protocol))
    second = simulation.run(2, context_override=simulation.binding(2, protocol=client_protocol))[1]
    digest = second["session_digest"]
    before = simulation.state.load(digest).state

    payload = upstream_payload(protocol, 3)
    usage = payload["usage"]
    input_key = "input_tokens"
    output_key = "output_tokens"
    if case == "missing_input":
        usage.pop(input_key)
    elif case in {"missing_output", "json_missing_output"}:
        usage.pop(output_key)
    elif case in {"invalid_usage", "invalid_then_corrected"}:
        usage[output_key] = -1
    elif case == "conflicting_usage":
        usage["completion_tokens"] = 499
    elif case in {"inclusive_conflict", "json_inclusive_conflict"}:
        usage["prompt_tokens"] = 32251
    elif case in {"output_alias_only", "json_output_alias_only"}:
        usage["completion_tokens"] = usage.pop(output_key)
    elif case == "cache_overflow_corrected":
        if protocol == "anthropic":
            usage["cache_creation_input_tokens"] = 200
        else:
            usage["input_tokens_details"]["cached_tokens"] = 40000

    if protocol == "anthropic":
        events = [{"type": "message_start", "message": {"id": "sse-compat", "model": "claude-test", "usage": usage}}]
        if case in {"error", "error_then_complete"}:
            events.append({"type": "error", "error": {"type": "overloaded_error", "message": "busy"}})
        if case not in {"error", "incomplete"}:
            if case == "cache_overflow_corrected":
                events.append({"type": "message_delta", "usage": {"cache_creation_input_tokens": 250}})
            if case in {"complete_zero", "split_usage", "invalid_then_corrected"}:
                events.append({"type": "message_delta", "usage": {output_key: 0 if case == "complete_zero" else 500}})
                if case == "split_usage":
                    usage.pop(output_key)
            events.extend([{"type": "message_delta", "delta": {"stop_reason": "end_turn"}}, {"type": "message_stop"}])
    else:
        events = [{"id": "sse-compat", "model": "claude-test", "choices": [], "usage": usage}]
        if case in {"error", "error_then_complete"}:
            events.append({"error": {"type": "server_error", "message": "busy"}})
        if case not in {"error", "incomplete"}:
            if case == "cache_overflow_corrected":
                events.append({"choices": [], "usage": {"input_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 250}}})
            if case in {"complete_zero", "split_usage", "invalid_then_corrected"}:
                events.append({"choices": [], "usage": {output_key: 0 if case == "complete_zero" else 500}})
                if case == "split_usage":
                    usage.pop(output_key)
            events.append({"choices": [{"delta": {}, "finish_reason": "stop"}]})
    if case == "malformed_usage":
        if protocol == "anthropic":
            events[0]["message"]["usage"] = "invalid-usage-object"
        else:
            events[0]["usage"] = "invalid-usage-object"
    wire = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    if protocol == "openai" and case not in {"error", "incomplete"}:
        wire += "data: [DONE]\n\n"
    if case.startswith("json_"):
        # A genuine final JSON object may be mislabeled as text/event-stream.
        wire = json.dumps(payload)
    channel = Channel(id=70, name="compat-test", base_url="https://upstream.test", api_key="test-only", protocol_type=protocol)

    async def passthrough_cache(**kwargs):
        return await kwargs["upstream_call"](), None

    async def run():
        request_data = {"model": "claude-test", "messages": [{"role": "user", "content": "test"}], "max_tokens": 1000}
        method = getattr(ProxyService, "_non_stream_" + path + "_request")
        with (patch.object(ProxyService, "_post_with_retries", AsyncMock(return_value=httpx.Response(200, text=wire, headers={"content-type": "text/event-stream"}))),
              patch("app.services.proxy_service.CacheMiddleware.wrap_request", side_effect=passthrough_cache),
              patch("app.services.proxy_service.release_session_connection"),
              patch("app.services.proxy_service.AnthropicPromptCacheService.build_request_variants", return_value=[{"request_data": request_data, "meta": {}}])):
            response = await method(None, SimpleNamespace(id=1, username="cache-test"), SimpleNamespace(id=1),
                channel, simulation.model, request_data, "compat-third", "claude-test", "127.0.0.1",
                billing_context=simulation.binding(3, protocol=client_protocol))
        # Parser evidence belongs only to local accounting, never the client payload.
        assert "_simulation" not in response.body.decode()
        assert "simulation_success" not in response.body.decode()

    asyncio.run(run())
    row = record_rows(simulation)[-1]
    if case in {"complete", "complete_zero", "split_usage", "json_complete"} or (
            protocol == "openai" and case in {"output_alias_only", "json_output_alias_only"}):
        assert row["outcome"] == "simulated"
        assert row["usage"]["raw"] == {"input": 31000, "output": 0 if case == "complete_zero" else 500, "read": 1000, "creation": 250}
    else:
        assert row["outcome"] == "skipped" and row["reason"] == "incomplete_or_failed_usage"
        assert row["usage"]["raw"] == row["usage"]["effective"]
        assert row["usage"]["baseline"] == row["usage"]["billed"]
        assert simulation.state.load(digest).state == before
