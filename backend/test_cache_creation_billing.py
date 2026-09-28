"""Inclusive OpenAI input must produce disjoint ordinary/read/write buckets."""
import asyncio
import copy
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.log import ConsumptionRecord, RequestCacheSummary, RequestLog, UserBalance
from app.models.model import UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.services.anthropic_prompt_cache_service import AnthropicPromptCacheService
from app.services.channel_passthrough_service import ChannelPassthroughService, UsageObserver
from app.services.log_service import LogService
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService

REPLAYS = ((188258, 0, 188190, 6262, 194520), (193060, 31756, 161236, 3716, 196776), (188618, 31756, 156794, 2159, 190777))
PARSERS = (ProxyService._extract_responses_prompt_cache_summary, ProxyService._extract_openai_prompt_cache_summary)
CHANNEL = SimpleNamespace(id=70, name="cache-test", base_url="https://upstream.test", protocol_type="openai")


def usage(total=100, read=0, created=90, output=2):
    return {"input_tokens": total, "output_tokens": output,
            "input_tokens_details": {"cached_tokens": read, "cache_write_tokens": created}}


def cache_info(summary):
    return ProxyService._merge_upstream_cache_usage_into_cache_info(None, summary, source="test")


@pytest.mark.parametrize("parser", PARSERS)
@pytest.mark.parametrize("total,read,created,output,expected_total", REPLAYS)
def test_real_requests(parser, total, read, created, output, expected_total):
    result = parser(usage(total, read, created, output), CHANNEL)
    assert result["input_tokens"] == 68
    assert result["cache_creation_input_tokens"] == created
    assert result["cache_read_input_tokens"] == read
    assert result["output_tokens"] == output
    assert result["logical_input_tokens"] == total
    assert result["prompt_cache_status"] == ("MIXED" if read else "WRITE")
    assert 68 + read + created + output == expected_total


@pytest.mark.parametrize("parser", PARSERS)
@pytest.mark.parametrize("container", (None, "input_tokens_details", "prompt_tokens_details"))
@pytest.mark.parametrize("alias", ("cache_write_tokens", "cache_creation_tokens", "cache_creation_input_tokens", "cache_write_input_tokens"))
def test_creation_aliases(parser, container, alias):
    payload = {"input_tokens": 100, "output_tokens": 2}
    target = payload if container is None else payload.setdefault(container, {})
    target[alias] = "90"
    result = parser(payload)
    assert (result["input_tokens"], result["cache_creation_input_tokens"]) == (10, 90)


@pytest.mark.parametrize("parser", PARSERS)
@pytest.mark.parametrize("alias", ("cache_read_input_tokens", "cache_read_tokens", "cached_tokens"))
def test_read_aliases(parser, alias):
    result = parser({"input_tokens": 100, alias: 20, "cache_creation_input_tokens": 70})
    assert (result["input_tokens"], result["cache_read_input_tokens"], result["cache_creation_input_tokens"]) == (10, 20, 70)


@pytest.mark.parametrize("parser", PARSERS)
def test_zero_and_alias_precedence(parser):
    primary = "input_tokens_details" if parser is PARSERS[0] else "prompt_tokens_details"
    secondary = "prompt_tokens_details" if primary == "input_tokens_details" else "input_tokens_details"
    payload = {"input_tokens": 100, primary: {"cached_tokens": 0, "cache_write_tokens": 0},
               secondary: {"cached_tokens": 30, "cache_write_tokens": 40},
               "cache_creation_input_tokens": 90, "cache_read_input_tokens": 50}
    result = parser(payload)
    assert (result["input_tokens"], result["cache_read_input_tokens"], result["cache_creation_input_tokens"]) == (100, 0, 0)
    payload[primary] = {}
    result = parser(payload)
    assert (result["input_tokens"], result["cache_read_input_tokens"], result["cache_creation_input_tokens"]) == (30, 30, 40)


@pytest.mark.parametrize("invalid", (None, True, False, -1, 0.5, "invalid", "1.5", [], {}, float("inf"), float("nan")))
def test_invalid_values_fall_back_without_truncating(invalid):
    result = PARSERS[0]({"input_tokens": 100, "input_tokens_details": {"cache_write_tokens": invalid}, "cache_creation_input_tokens": 90})
    assert (result["input_tokens"], result["cache_creation_input_tokens"]) == (10, 90)


@pytest.mark.parametrize("total,read,created,expected", ((100, 150, 90, (0, 100, 0)), (100, 70, 90, (0, 70, 30)), (0, 20, 90, (0, 0, 0))))
def test_cache_details_never_inflate_input(total, read, created, expected):
    result = PARSERS[0](usage(total, read, created))
    assert (result["input_tokens"], result["cache_read_input_tokens"], result["cache_creation_input_tokens"]) == expected


@pytest.mark.parametrize("parser", PARSERS)
def test_cpa_miss_does_not_prove_creation(parser):
    result = parser({"input_tokens": 100, "output_tokens": 2, "input_tokens_details": {"cached_tokens": 0},
                     "prompt_tokens_details": {"cached_tokens": 0}}, SimpleNamespace(base_url="http://localhost:8317"))
    assert result["input_tokens"] == 100 and result["cache_creation_input_tokens"] == 0
    assert result["prompt_cache_status"] == "BYPASS"


def test_reasoning_reconciles_against_inclusive_input():
    result = PARSERS[1]({"prompt_tokens": 100, "completion_tokens": 2, "total_tokens": 112,
                         "prompt_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 70}})
    assert (result["input_tokens"], result["output_tokens"]) == (10, 12)
    assert PARSERS[0]({"input_tokens": 100, "output_tokens": 2, "total_tokens": 112})["output_tokens"] == 2


def test_anthropic_input_remains_exclusive():
    result = AnthropicPromptCacheService.extract_usage_summary({"input_tokens": 68, "output_tokens": 6262,
             "cache_creation_input_tokens": 188190, "cache_read_input_tokens": 31756})
    assert result["input_tokens"] == 68 and result["logical_input_tokens"] == 220014


@pytest.mark.parametrize("protocol", ("responses", "openai"))
def test_passthrough_corrections_rebuild_snapshot(protocol):
    observer = UsageObserver(protocol, CHANNEL)
    def feed(payload):
        event = {"type": "response.completed", "response": {"usage": payload}} if protocol == "responses" else {"usage": payload}
        before = copy.deepcopy(event)
        observer.feed_json(event)
        assert event == before
    feed({"input_tokens": 100, "output_tokens": 0})
    feed({"input_tokens_details": {"cache_write_tokens": 90}, "output_tokens": 2})
    assert (observer.summary["input_tokens"], observer.summary["cache_creation_input_tokens"]) == (10, 90)
    feed({"output_tokens": 3})
    assert observer.summary["cache_creation_input_tokens"] == 90
    feed({"input_tokens_details": {"cache_write_tokens": 0}})
    assert (observer.summary["input_tokens"], observer.summary["cache_creation_input_tokens"]) == (100, 0)
    feed({"input_tokens": 0, "output_tokens": 0})
    assert observer.usage_seen and observer.summary["input_tokens"] == observer.summary["output_tokens"] == 0


def test_fragmented_passthrough_sse_keeps_creation():
    observer = UsageObserver("responses", CHANNEL)
    data = ('data: ' + json.dumps({"type": "response.completed", "response": {"usage": usage(188258, 0, 188190, 6262)}}) + '\n\n').encode()
    for chunk in (data[:35], data[35:90], data[90:]):
        observer.feed_sse(chunk)
    assert observer.completed
    info = ChannelPassthroughService._cache_info(observer, "responses")
    assert info["upstream_input_tokens"] == 68 and info["upstream_cache_creation_input_tokens"] == 188190


def test_zero_snapshot_is_distinct_from_initialized_placeholders():
    assert ProxyService._collect_stream_billing_tokens(0, 0, {"collected_usage": {"prompt_tokens": 0, "completion_tokens": 0}}) == (0, 0, False)
    state = {"collected_usage": {"prompt_tokens": 0, "completion_tokens": 0, "_upstream_cache_usage": {"input_tokens": 100, "output_tokens": 5}}}
    assert ProxyService._collect_stream_billing_tokens(100, 5, state) == (0, 0, True)
    summary = PARSERS[0](usage(100, 30, 70, 0))
    assert ProxyService._collect_stream_billing_tokens(0, 0, {"collected_usage": {"_upstream_cache_usage": summary}}) == (0, 0, True)


@pytest.mark.parametrize("total,read,created,output,expected_total", REPLAYS)
def test_responses_stream_passes_correct_accounting_arguments(total, read, created, output, expected_total):
    async def upstream(*args, **kwargs):
        yield {"type": "response.completed", "response": {"output": [], "usage": usage(total, read, created, output)}}
    async def run():
        finalize = Mock()
        with (patch.object(ProxyService, "_iter_responses_upstream_payloads", new=upstream),
              patch.object(ProxyService, "_finalize_successful_text_request", finalize),
              patch.object(ProxyService, "_scan_stream_security_output")):
            response = await ProxyService._stream_responses_request(
                SimpleNamespace(close=lambda: None), SimpleNamespace(), SimpleNamespace(), CHANNEL,
                SimpleNamespace(security_monitor_enabled=0), {"model": "gpt-test", "input": "test", "stream": True},
                "test-stream", "gpt-test", "127.0.0.1")
            assert [chunk async for chunk in response.body_iterator]
        finalize.assert_called_once()
        assert finalize.call_args.args[6:8] == (68, output)
        info = finalize.call_args.kwargs["cache_info"]
        assert info["upstream_cache_creation_input_tokens"] == created and info["upstream_cache_read_input_tokens"] == read
    asyncio.run(run())


@pytest.fixture
def ledger():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[cls.__table__ for cls in (SysUser, UserApiKey, UserBalance, ConsumptionRecord, RequestLog, RequestCacheSummary)])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    state = SimpleNamespace(token_multiplier=1.0, fail_commit=False)
    with factory.begin() as db:
        db.add(SysUser(id=1, username="cache-test", email="cache@example.test", password_hash="test", subscription_type="balance"))
        db.add(UserApiKey(id=1, user_id=1, name="test", key_prefix="test", key_hash="test", total_requests=0, total_tokens=0, total_cost=0))
        db.add(UserBalance(user_id=1, balance=Decimal("1000"), total_consumed=0))
    @contextmanager
    def scope():
        with factory() as db:
            try:
                yield db
                if state.fail_commit:
                    state.fail_commit = False
                    raise RuntimeError("simulated transaction failure")
                db.commit()
            except Exception:
                db.rollback()
                raise
    context = {"global_price_multiplier_snapshot": 1, "adjustment_price_multiplier_snapshot": 1.5,
               "price_adjustment_source_snapshot": "global", "group_multiplier_snapshot": 2}
    model = UnifiedModel(model_name="gpt-test", input_price_per_million=20, output_price_per_million=100,
                         cache_read_price_per_million=2, cache_creation_price_per_million=25,
                         billing_type="token", long_context_billing_enabled=1, long_context_token_threshold=256000, bonus_quota_enabled=0)
    def book(summary, request_id="test-book", finalize=False):
        args = (None, SimpleNamespace(id=1, subscription_type="balance"), SimpleNamespace(id=1), model,
                request_id, "gpt-test", summary["input_tokens"], summary["output_tokens"], CHANNEL, "127.0.0.1", 10)
        method = ProxyService._finalize_successful_text_request if finalize else ProxyService._deduct_balance_and_log_once
        method(*args, is_stream=True, request_type="responses", cache_info=cache_info(summary), billing_context=context)
    state.factory, state.book, state.model = factory, book, model
    with (patch("app.services.proxy_service.session_scope", scope),
          patch("app.services.proxy_service.get_system_config", side_effect=lambda db, key, default=None: state.token_multiplier if key == "token_multiplier" else default),
          patch.object(ProxyService, "_record_success")):
        yield state
    engine.dispose()


@pytest.mark.parametrize("total,read,created,output,expected_total", REPLAYS)
def test_sqlite_accounting_counts_creation_once(ledger, total, read, created, output, expected_total):
    ledger.book(PARSERS[0](usage(total, read, created, output)))
    with ledger.factory() as db:
        row, cost, key, balance = db.query(RequestLog).one(), db.query(ConsumptionRecord).one(), db.get(UserApiKey, 1), db.query(UserBalance).one()
        expected_cost = (Decimal(68 * 20 + read * 2 + created * 25 + output * 100) / 1000000 * 3).quantize(Decimal("0.000001"))
        assert row.input_tokens == row.raw_input_tokens == 68 and row.upstream_cache_creation_input_tokens == created
        assert row.total_tokens == row.raw_total_tokens == row.context_tokens_snapshot == expected_total
        assert cost.total_tokens == cost.raw_total_tokens == expected_total
        assert cost.cache_creation_cost == Decimal(created * 25) / 1000000 * 3
        assert cost.total_cost == expected_cost and balance.balance == Decimal("1000") - expected_cost
        assert key.total_requests == 1 and key.total_tokens == expected_total and key.total_cost == expected_cost


def test_fractional_multiplier_rounds_individual_buckets(ledger):
    ledger.token_multiplier = 1.5
    ledger.book(PARSERS[0](usage(3, 1, 1, 1)))
    with ledger.factory() as db:
        row = db.query(RequestLog).one()
        assert row.raw_total_tokens == row.total_tokens == 4  # Four int(1 * 1.5), not int(4 * 1.5).
        assert row.token_multiplier_snapshot == Decimal("1.5")
        assert db.query(ConsumptionRecord).one().cache_creation_cost == Decimal("0.000075")


@pytest.mark.parametrize("threshold,multiplier", ((100, 1), (99, 2)))
def test_cache_only_usage_drives_context_threshold(ledger, threshold, multiplier):
    ledger.model.long_context_token_threshold = threshold
    ledger.book(PARSERS[0](usage(100, 30, 70, 0)))
    with ledger.factory() as db:
        row, cost = db.query(RequestLog).one(), db.query(ConsumptionRecord).one()
        assert row.input_tokens == row.output_tokens == 0 and row.total_tokens == row.context_tokens_snapshot == 100
        assert row.context_price_multiplier_snapshot == multiplier and cost.input_cost == 0
        assert cost.total_cost == Decimal("0.005430") * multiplier


def test_zero_creation_price_keeps_usage(ledger):
    ledger.model.cache_creation_price_per_million = 0
    ledger.book(PARSERS[0](usage(100, 0, 100, 0)))
    with ledger.factory() as db:
        assert db.query(RequestLog).one().total_tokens == 100 and db.query(ConsumptionRecord).one().total_cost == 0
        assert db.query(UserBalance).one().balance == 1000


@pytest.mark.parametrize("metric,official,expected", (("total_tokens", False, "194520"), ("cost_usd", False, "15.996930"), ("cost_usd", True, "5.332310")))
def test_quota_receives_complete_usage(ledger, metric, official, expected):
    with ledger.factory.begin() as db:
        db.get(SysUser, 1).subscription_type = "quota"
    subscription = SimpleNamespace(id=1, plan_kind_snapshot="daily_quota", model_scope_snapshot="all_models")
    cycle = SimpleNamespace(id=1, quota_limit=Decimal("1000000"), used_amount=Decimal("0"), cycle_date=date(2026, 9, 28))
    def consume(db, subscription, **kwargs):
        amount = kwargs["consumed_amount"]
        return {"subscription_cycle_id": 1, "quota_metric": metric, "quota_consumed_amount": amount,
                "quota_limit_snapshot": cycle.quota_limit, "quota_used_after": amount, "quota_cycle_date": cycle.cycle_date}
    with (patch.object(SubscriptionService, "resolve_active_subscription", return_value=subscription),
          patch.object(SubscriptionService, "_get_effective_quota_metric", return_value=metric),
          patch.object(SubscriptionService, "_uses_official_cost_for_quota", return_value=official),
          patch.object(SubscriptionService, "_get_or_create_cycle", return_value=cycle),
          patch.object(SubscriptionService, "consume_quota_amount_after_request", side_effect=consume) as consumed):
        ledger.book(PARSERS[0](usage(188258, 0, 188190, 6262)))
    assert consumed.call_args.kwargs["consumed_amount"] == Decimal(expected)
    with ledger.factory() as db:
        assert db.query(RequestLog).one().quota_consumed_amount == Decimal(expected)
        assert db.query(UserBalance).one().balance == 1000


def test_failed_transaction_preserves_full_usage_without_charge(ledger):
    ledger.fail_commit = True
    ledger.book(PARSERS[0](usage(188258, 0, 188190, 6262)), finalize=True)
    with ledger.factory() as db:
        assert db.query(UserBalance).one().balance == 1000 and db.query(ConsumptionRecord).count() == 0
        assert db.get(UserApiKey, 1).total_requests == 0
        row = db.query(RequestLog).one()
        assert row.status == "error" and row.total_tokens == row.raw_total_tokens == 194520
        assert row.upstream_cache_creation_input_tokens == 188190
        assert LogService._visible_token_totals(row, True) == (194520, 194520)


def test_duplicate_attempt_rolls_back_charge(ledger):
    summary = PARSERS[0](usage(188258, 0, 188190, 6262))
    ledger.book(summary)
    with pytest.raises(SQLAlchemyError):
        ledger.book(summary)
    with ledger.factory() as db:
        assert db.query(ConsumptionRecord).count() == 1 and db.query(UserBalance).one().balance == Decimal("984.003070")
        assert db.get(UserApiKey, 1).total_requests == 1


def test_historical_cpa_totals_remain_unchanged():
    old = SimpleNamespace(input_tokens=100, output_tokens=2, total_tokens=102, raw_input_tokens=100, raw_output_tokens=2,
                          raw_total_tokens=102, upstream_cache_read_input_tokens=0, upstream_cache_creation_input_tokens=100)
    assert LogService._visible_token_totals(old, False) == LogService._visible_token_totals(old, True) == (102, 102)


@pytest.mark.parametrize("total,read,created,output,expected_total", REPLAYS)
def test_nonstream_responses_keeps_wire_usage_and_bills_disjoint_buckets(total, read, created, output, expected_total):
    wire = {"object": "response", "id": "resp-test", "status": "completed", "output": [],
            "usage": usage(total, read, created, output)}
    async def run():
        finalize = Mock()
        with (patch.object(ProxyService, "_post_with_retries", new=AsyncMock(return_value=SimpleNamespace(status_code=200, text=json.dumps(wire)))),
              patch.object(ProxyService, "_build_headers", return_value={}),
              patch.object(ProxyService, "_finalize_successful_text_request", finalize)):
            response = await ProxyService._non_stream_responses_request(
                SimpleNamespace(close=lambda: None), SimpleNamespace(), SimpleNamespace(), CHANNEL,
                SimpleNamespace(security_monitor_enabled=0), {"model": "gpt-test", "input": "test"},
                "test-nonstream", "gpt-test", "127.0.0.1", billing_context={"service_tier": "default"})
        assert json.loads(response.body)["usage"] == wire["usage"]
        finalize.assert_called_once()
        assert finalize.call_args.args[6:8] == (68, output)
        info = finalize.call_args.kwargs["cache_info"]
        assert info["upstream_cache_creation_input_tokens"] == created
        assert info["upstream_cache_read_input_tokens"] == read
    asyncio.run(run())


def test_anthropic_independent_buckets_are_counted_once_at_accounting(ledger):
    summary = AnthropicPromptCacheService.extract_usage_summary({
        "input_tokens": 68, "output_tokens": 6262, "cache_read_input_tokens": 31756,
        "cache_creation_input_tokens": 188190,
        "cache_creation": {"ephemeral_5m_input_tokens": 188000, "ephemeral_1h_input_tokens": 190},
    })
    ledger.book(summary)
    with ledger.factory() as db:
        row = db.query(RequestLog).one()
        assert row.input_tokens == 68
        assert row.upstream_cache_creation_input_tokens == 188190
        assert row.upstream_cache_creation_5m_input_tokens == 188000
        assert row.upstream_cache_creation_1h_input_tokens == 190
        assert row.raw_total_tokens == row.total_tokens == 226276


@pytest.mark.parametrize("payload,expected", ((None, False), ({}, False), ("explicit-null", False),
                                              ({"input_tokens": "invalid", "output_tokens": True,
                                                "input_tokens_details": {"cached_tokens": -1, "cache_write_tokens": 0.5}}, False),
                                              ({"input_tokens": 0, "output_tokens": 0}, True),
                                              (usage(100, 0, 100, 0), True), (usage(100, 30, 70, 0), True)))
def test_completed_stream_distinguishes_missing_zero_and_cache_only_usage(payload, expected):
    async def upstream(*args, **kwargs):
        response = {"output": []}
        if payload is not None:
            response["usage"] = None if payload == "explicit-null" else payload
        yield {"type": "response.completed", "response": response}
    async def run():
        finalize, failed = Mock(), Mock()
        with (patch.object(ProxyService, "_iter_responses_upstream_payloads", new=upstream),
              patch.object(ProxyService, "_finalize_successful_text_request", finalize),
              patch.object(ProxyService, "_log_failed_request", failed),
              patch.object(ProxyService, "_record_channel_failure"),
              patch.object(ProxyService, "_scan_stream_security_output")):
            response = await ProxyService._stream_responses_request(
                SimpleNamespace(close=lambda: None), SimpleNamespace(), SimpleNamespace(), CHANNEL,
                SimpleNamespace(security_monitor_enabled=0), {"model": "gpt-test", "input": "test", "stream": True},
                "test-usage-presence", "gpt-test", "127.0.0.1")
            chunks = [chunk async for chunk in response.body_iterator]
        if expected:
            finalize.assert_called_once()
            failed.assert_not_called()
            assert not any('"type": "error"' in chunk for chunk in chunks)
        else:
            finalize.assert_not_called()
            failed.assert_called_once()
    asyncio.run(run())


@pytest.mark.parametrize("protocol", ("responses", "openai"))
def test_empty_passthrough_usage_is_not_reported_usage(protocol):
    observer = UsageObserver(protocol, CHANNEL)
    observer.feed_json({"usage": {}})
    assert not observer.usage_seen
    observer.feed_json({"usage": {"input_tokens": 0, "output_tokens": 0}})
    assert observer.usage_seen


@pytest.mark.parametrize("reported_usage", (None, {}))
def test_missing_stream_usage_does_not_charge_per_request_model(ledger, reported_usage):
    ledger.model.billing_type = "request"
    ledger.model.request_price = Decimal("1")
    async def upstream(*args, **kwargs):
        response = {"output": []}
        if reported_usage is not None:
            response["usage"] = reported_usage
        yield {"type": "response.completed", "response": response}
    async def run():
        with (patch.object(ProxyService, "_iter_responses_upstream_payloads", new=upstream),
              patch.object(ProxyService, "_record_channel_failure"),
              patch.object(ProxyService, "_scan_stream_security_output")):
            response = await ProxyService._stream_responses_request(
                SimpleNamespace(close=lambda: None), SimpleNamespace(id=1, subscription_type="balance"),
                SimpleNamespace(id=1), CHANNEL, ledger.model,
                {"model": "gpt-test", "input": "test", "stream": True},
                "missing-request-usage", "gpt-test", "127.0.0.1")
            assert [chunk async for chunk in response.body_iterator]
    asyncio.run(run())
    with ledger.factory() as db:
        assert db.query(UserBalance).one().balance == 1000
        assert db.query(ConsumptionRecord).count() == 0
        assert db.get(UserApiKey, 1).total_requests == 0
        assert db.query(RequestLog).one().status == "error"
