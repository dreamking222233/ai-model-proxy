"""Request metadata must survive logging without exposing routing or changing billing."""
import asyncio
import json
from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import WebSocketDisconnect

from app.database import Base
from app.models.log import ConsumptionRecord, RequestCacheSummary, RequestLog, UserBalance
from app.models.model import UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.services.channel_passthrough_service import ChannelPassthroughService
from app.services.log_service import LogService
from app.services.proxy_service import ProxyService, ResponsesTurnError
from app.services.billing_concurrency_service import BillingConcurrencyService
from app.services.request_reasoning_service import RequestReasoningService as Reasoning
from app.middleware.cache_middleware import CacheMiddleware


@pytest.mark.parametrize("payload,expected", [
    ({}, {"mode": "default"}),
    ({"reasoning_effort": "HIGH"}, {"effort": "high"}),
    ({"reasoning": {"effort": "xhigh"}}, {"effort": "xhigh"}),
    ({"reasoning": {"effort": "none"}}, {"effort": "none"}),
    ({"thinking": {"type": "adaptive"}, "output_config": {"effort": "max"}}, {"mode": "adaptive", "effort": "max"}),
    ({"thinking": {"type": "enabled", "budget_tokens": 16384}}, {"mode": "enabled", "budget_tokens": 16384}),
    ({"thinking": {"type": "disabled", "budget_tokens": 16384}, "output_config": {"effort": "high"}}, {"mode": "disabled"}),
    ({"generationConfig": {"thinkingConfig": {"thinkingLevel": "HIGH"}}}, {"effort": "high"}),
    ({"generation_config": {"thinking_config": {"thinking_budget": -1}}}, {"mode": "auto"}),
    ({"generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}}, {"mode": "disabled"}),
    ({"generationConfig": {"thinkingConfig": {"thinkingBudget": 8192}}}, {"mode": "enabled", "budget_tokens": 8192}),
    ({"reasoning_effort": {"secret": "bad"}, "thinking": {"budget_tokens": True}}, {"mode": "default"}),
    ({"thinking": {"type": "enabled", "budget_tokens": 0.5}}, {"mode": "enabled"}),
    ({"thinking": {"type": "enabled", "budget_tokens": 0}}, {"mode": "enabled"}),
    ({"thinking": {"type": "enabled", "budget_tokens": -1}}, {"mode": "enabled"}),
    ({"type": "response.create", "response": {"reasoning": {"effort": "xhigh"}}}, {"effort": "xhigh"}),
])
def test_extract_only_reasoning_configuration(payload, expected):
    payload["messages"] = [{"role": "user", "content": "private content"}]
    assert Reasoning.extract(payload) == expected
    assert "private content" not in json.dumps(Reasoning.extract(payload))


@pytest.mark.parametrize("invalid", [None, "{", "[]", "null", [], True, '{"effort":"secret"}'])
def test_unknown_or_invalid_historical_snapshot(invalid):
    assert Reasoning.load(invalid) is None


def test_load_discards_unrecognized_fields_and_invalid_budget():
    assert Reasoning.load('{"effort":"high","messages":"private","budget_tokens":true}') == {"effort": "high"}


def test_public_dto_keeps_group_and_removes_routing_even_inside_snapshot():
    public = LogService.build_user_visible_request_log_items([{
        "model": "claude-test", "group_name_snapshot": "Claude-AWS", "group_id_snapshot": 12,
        "channel_name": "private-channel", "channel_id": 74, "actual_model": "private-model",
        "reasoning_snapshot": {"effort": "high", "channel_name": "private-channel"},
    }])[0]
    assert public["group_name_snapshot"] == "Claude-AWS"
    assert public["reasoning_snapshot"] == {"effort": "high"}
    for key in ("channel_name", "channel_id", "actual_model"):
        assert key not in public


def test_bridge_failure_logger_receives_forwarded_snapshot():
    outer = Reasoning.with_snapshot({"group_name_snapshot": "group"}, {"reasoning_effort": "high"})
    other = Reasoning.with_snapshot(outer, {"reasoning_effort": "low"})
    inner = Reasoning.refresh_forwarded_snapshot(outer, {"thinking": {"type": "enabled", "budget_tokens": 4096}})
    assert inner is outer
    assert Reasoning.load(Reasoning.log_fields(outer)["reasoning_snapshot"]) == {"mode": "enabled", "budget_tokens": 4096}
    assert other["reasoning_snapshot"] == {"effort": "low"}


@pytest.mark.parametrize("method,payload,expected", [
    (ProxyService._non_stream_openai_via_anthropic_request,
     {"model": "claude-test", "reasoning_effort": "high", "messages": [{"role": "user", "content": "hello"}]},
     {"mode": "default"}),
    (ProxyService._non_stream_anthropic_via_responses_request,
     {"model": "gpt-test", "thinking": {"type": "enabled", "budget_tokens": 8192}, "messages": [{"role": "user", "content": "hello"}]},
     {"effort": "high"}),
])
def test_real_bridge_failure_preserves_configuration_sent_to_upstream(method, payload, expected):
    context = Reasoning.with_snapshot({"group_name_snapshot": "group"}, payload)
    channel = SimpleNamespace(id=1, name="test", base_url="https://upstream.test", protocol_type="openai")
    failed = AsyncMock(side_effect=RuntimeError("simulated upstream failure"))
    async def run():
        with (patch("app.services.proxy_service.release_session_connection"),
              patch.object(ProxyService, "_build_headers", return_value={}),
              patch.object(CacheMiddleware, "wrap_request", failed)):
            with pytest.raises(RuntimeError, match="simulated upstream failure"):
                await method(Mock(), Mock(), Mock(), channel, Mock(), payload, "req", "client-model", "127.0.0.1", billing_context=context)
        assert context["reasoning_snapshot"] == expected
        assert Reasoning.extract(failed.call_args.kwargs["request_body"]) == expected
    asyncio.run(run())


def test_websocket_exhausted_retries_log_last_forwarded_effort(monkeypatch):
    model = SimpleNamespace(id=1)
    channels = [(SimpleNamespace(id=1, name="low"), "gpt-test"), (SimpleNamespace(id=2, name="high"), "gpt-test")]
    websocket = SimpleNamespace(receive_text=AsyncMock(side_effect=WebSocketDisconnect()), send_text=AsyncMock())
    monkeypatch.setattr("app.services.proxy_service.release_session_connection", Mock())
    monkeypatch.setattr(ProxyService, "_resolve_requested_model_or_raise", Mock(return_value=model))
    monkeypatch.setattr(ProxyService, "_maybe_create_security_snapshot", Mock(return_value=(None, None)))
    for name in ("_maybe_scan_security_request_or_raise", "_inject_model_identity", "_maybe_inject_security_prompt", "_apply_runtime_retry_config", "_record_channel_failure", "_log_responses_request_json"):
        monkeypatch.setattr(ProxyService, name, Mock())
    quota = {"group_name_snapshot": "historical-group"}
    monkeypatch.setattr(ProxyService, "_prepare_responses_request_context", Mock(return_value=(model, channels, quota, Mock())))
    monkeypatch.setattr(ProxyService, "_resolve_mapped_upstream_target", Mock(return_value=("gpt-test", "responses")))
    monkeypatch.setattr(ProxyService, "_get_mapping_default_reasoning_effort", Mock(side_effect=["low", "high"]))
    monkeypatch.setattr(ProxyService, "_billing_concurrency_lease_ttl_seconds", Mock(return_value=300))
    monkeypatch.setattr(BillingConcurrencyService, "acquire_if_needed", Mock(return_value=None))
    monkeypatch.setattr(BillingConcurrencyService, "release", Mock())
    forwarded = AsyncMock(side_effect=ResponsesTurnError("simulated retryable failure", can_retry=True))
    logged = Mock()
    monkeypatch.setattr(ProxyService, "_forward_responses_websocket_turn", forwarded)
    monkeypatch.setattr(ProxyService, "_log_failed_request", logged)
    asyncio.run(ProxyService.handle_responses_websocket(
        Mock(), SimpleNamespace(id=1), SimpleNamespace(id=1), websocket, "127.0.0.1",
        initial_message=json.dumps({"type": "response.create", "model": "gpt-test", "input": "hello"}),
    ))
    assert [Reasoning.extract(call.args[4]) for call in forwarded.call_args_list] == [{"effort": "low"}, {"effort": "high"}]
    logged.assert_called_once()
    assert logged.call_args.kwargs["billing_context"]["reasoning_snapshot"] == {"effort": "high"}
    assert logged.call_args.kwargs["billing_context"]["group_name_snapshot"] == "historical-group"


def test_final_configuration_overrides_initial_without_mutating_context():
    original = ProxyService._build_text_billing_context("responses", {"reasoning": {"effort": "xhigh"}})
    prepared = ProxyService._prepare_responses_request_body("gpt-test", {"reasoning": {"effort": "xhigh"}, "input": "hello"})
    final = Reasoning.with_snapshot(original, prepared)
    assert original["reasoning_snapshot"] == {"effort": "xhigh"}
    assert final["reasoning_snapshot"] == {"effort": "high"}
    frozen = ProxyService._build_frozen_text_billing_context(final, {"global_price_multiplier_snapshot": 2})
    assert frozen["reasoning_snapshot"] == final["reasoning_snapshot"]


def test_mapping_default_is_recorded_after_conversion():
    request = {"model": "gpt-test", "input": "hello"}
    ProxyService._apply_responses_mapping_default_reasoning_effort(request, upstream_model_name="gpt-test", default_reasoning_effort="xhigh")
    assert Reasoning.extract(request) == {"effort": "high"}
    converted = ProxyService._convert_anthropic_request_to_responses(
        {"model": "gpt-test", "messages": [{"role": "user", "content": "hello"}]},
        requested_model="claude-client", default_reasoning_effort="low",
    )
    assert Reasoning.extract(converted) == {"effort": "low"}


def test_passthrough_keeps_exact_client_effort():
    with (patch.object(ProxyService, "_resolve_group_billing_context", return_value={"group_id": 12}),
          patch.object(ProxyService, "_build_text_quota_precheck", return_value={}),
          patch.object(ProxyService, "_assert_text_request_allowed", return_value=Mock())):
        _, context = ChannelPassthroughService._build_billing(None, SimpleNamespace(id=1), Mock(), "responses", {"reasoning": {"effort": "xhigh"}}, "gpt-test")
    assert context["reasoning_snapshot"] == {"effort": "xhigh"}


@pytest.fixture
def ledger():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[cls.__table__ for cls in (
        SysUser, UserApiKey, UserBalance, ConsumptionRecord, RequestLog, RequestCacheSummary,
    )])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(SysUser(id=1, username="reasoning-test", email="reasoning@example.test", password_hash="test", subscription_type="balance"))
        db.add(UserApiKey(id=1, user_id=1, name="test", key_prefix="test", key_hash="test", total_requests=0, total_tokens=0, total_cost=0))
        db.add(UserBalance(user_id=1, balance=Decimal("10"), total_consumed=0))

    @contextmanager
    def scope():
        with factory.begin() as db:
            yield db

    with (patch("app.services.proxy_service.session_scope", scope),
          patch("app.services.proxy_service.get_system_config", side_effect=lambda db, key, default=None: default),
          patch.object(ProxyService, "_record_success")):
        yield factory
    engine.dispose()


def test_success_failure_and_minimal_logs_keep_snapshot_and_group(ledger):
    user = SimpleNamespace(id=1, agent_id=None, subscription_type="balance")
    key = SimpleNamespace(id=1)
    channel = SimpleNamespace(id=74, name="private-upstream", protocol_type="anthropic")
    model = UnifiedModel(model_name="claude-test", input_price_per_million=20, output_price_per_million=100, billing_type="token", bonus_quota_enabled=0)
    context = Reasoning.with_snapshot({
        "group_id_snapshot": 12, "group_name_snapshot": "Claude-AWS", "group_multiplier_snapshot": 2,
        "global_price_multiplier_snapshot": 1, "adjustment_price_multiplier_snapshot": 1,
        "price_adjustment_source_snapshot": "default",
    }, {"thinking": {"type": "enabled", "budget_tokens": 4096}})
    ProxyService._deduct_balance_and_log_once(None, user, key, model, "success", "claude-test", 10, 2, channel, "127.0.0.1", 10, is_stream=True, billing_context=context)
    assert ProxyService._log_failed_request(None, user, key, "failed", "claude-test", "127.0.0.1", True, "failed", channel=channel, billing_context=context)
    assert ProxyService._write_minimal_failed_request_log(user, key, "minimal", "claude-test", channel, "127.0.0.1", False, "failed", billing_context=context)
    with ledger() as db:
        logs, total = LogService.list_request_logs(db, user_id=1, include_internal_fields=True)
        public = LogService.build_user_visible_request_log_items(logs)
        assert total == 3
        for item in public:
            assert item["reasoning_snapshot"] == {"mode": "enabled", "budget_tokens": 4096}
            assert item["group_name_snapshot"] == "Claude-AWS"
            assert "channel_name" not in item and "actual_model" not in item
        assert db.query(ConsumptionRecord).count() == 1
        assert db.query(ConsumptionRecord).one().total_cost == Decimal("0.000800")
        assert db.query(UserBalance).one().balance == Decimal("9.999200")


def test_historical_null_does_not_guess_current_configuration(ledger):
    with ledger.begin() as db:
        db.add(RequestLog(request_id="old", user_id=1, requested_model="gpt-test", status="success", reasoning_snapshot=None, group_name_snapshot="original-group"))
    with ledger() as db:
        rows, _ = LogService.list_request_logs(db, user_id=1)
        assert rows[0]["reasoning_snapshot"] is None
        assert rows[0]["group_name_snapshot"] == "original-group"


def test_concurrent_turns_have_independent_metadata():
    async def run():
        base = {"group_name_snapshot": "group"}
        async def turn(effort):
            context = Reasoning.with_snapshot(base, {"reasoning": {"effort": effort}})
            await asyncio.sleep(0)
            return Reasoning.log_fields(context)
        low, high = await asyncio.gather(turn("low"), turn("high"))
        assert json.loads(low["reasoning_snapshot"])["effort"] == "low"
        assert json.loads(high["reasoning_snapshot"])["effort"] == "high"
        assert base == {"group_name_snapshot": "group"}
    asyncio.run(run())
