"""Cache simulation invariants, real isolated Redis and durable local settlement."""
import copy
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import pytest
import redis
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, MetaData, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from pymysql.constants import CLIENT

from app.config import settings
from app.database import Base
from app.core.exceptions import ServiceException
from app.models.cache_simulation import CacheSimulationDecision, CacheSimulationRule
from app.models.log import ConsumptionRecord, RequestCacheSummary, RequestLog, SystemConfig, UserBalance
from app.models.model import ModelGroup, UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.schemas.cache_simulation import CacheSimulationConfigUpdate, CacheSimulationRuleCreate, CacheSimulationRuleUpdate
from app.services.cache_simulation_allocator import CacheSimulationAllocator as Allocator, TokenBuckets
from app.services.cache_simulation_identity_service import CacheSimulationIdentityService as Identity
from app.services.cache_simulation_service import CacheSimulationService as Service
from app.services.cache_simulation_state_service import CacheSimulationStateService as State, canonical_json
from app.services.cache_simulation_usage import accounted_bucket, usage_provenance
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService
from app.services.subscription_bonus_service import SubscriptionBonusService

CHANNEL = SimpleNamespace(id=70, name="cache-test", base_url="https://upstream.test", protocol_type="openai")


@pytest.fixture
def ledger():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[x.__table__ for x in (
        SysUser, UserApiKey, UserBalance, ConsumptionRecord, RequestLog, RequestCacheSummary)])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    state = SimpleNamespace(factory=factory, token_multiplier=1.0, fail_commit=False)
    with factory.begin() as db:
        db.add(SysUser(id=1, username="cache-test", email="cache@example.test", password_hash="test", subscription_type="balance"))
        db.add(UserApiKey(id=1, user_id=1, name="test", key_prefix="test", key_hash="test", total_requests=0, total_tokens=0, total_cost=0))
        db.add(UserBalance(user_id=1, balance=Decimal("1000"), total_consumed=0))
    state.context = {"global_price_multiplier_snapshot": 1, "adjustment_price_multiplier_snapshot": 1.5,
                     "price_adjustment_source_snapshot": "global", "group_multiplier_snapshot": 2}
    state.model = UnifiedModel(model_name="gpt-test", input_price_per_million=20, output_price_per_million=100,
        cache_read_price_per_million=2, cache_creation_price_per_million=25, billing_type="token",
        long_context_billing_enabled=1, long_context_token_threshold=256000, bonus_quota_enabled=0)
    try:
        with (patch("app.services.proxy_service.get_system_config", side_effect=lambda db, key, default=None:
                    state.token_multiplier if key == "token_multiplier" else default),
              patch.object(ProxyService, "_record_success")):
            yield state
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def isolated_redis(tmp_path_factory):
    binary = shutil.which("redis-server")
    if not binary:
        pytest.skip("real Redis server binary required")
    directory = tempfile.TemporaryDirectory(prefix="cs-", dir="/tmp")
    socket = directory.name + "/redis.sock"
    process = subprocess.Popen([binary, "--port", "0", "--unixsocket", socket, "--save", "", "--appendonly", "no"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = redis.Redis(unix_socket_path=socket, decode_responses=True, socket_timeout=2)
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except redis.RedisError:
                time.sleep(.02)
        else:
            pytest.fail("isolated Redis failed to start")
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        directory.cleanup()


@pytest.fixture
def mysql_engine():
    if os.environ.get("CACHE_SIMULATION_MYSQL_TEST") != "1":
        pytest.skip("set CACHE_SIMULATION_MYSQL_TEST=1 for isolated local MySQL verification")
    url = make_url(settings.DATABASE_URL)
    assert url.host in {"localhost", "127.0.0.1", "::1"}, "test database must be local"
    name = "cache_sim_test_" + uuid.uuid4().hex[:16]
    admin = create_engine(url.set(database=None), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    engine = create_engine(url.set(database=name), connect_args={"client_flag": CLIENT.MULTI_STATEMENTS})
    try:
        # Model the old schema, then execute the actual upgrade twice.
        metadata = MetaData()
        new_columns = {"usage_accounting_version", "billable_cache_creation_input_tokens", "cache_simulation_decision_id", "cache_simulation_applied", "failure_stage"}
        for model in (SysUser, UserApiKey, UserBalance, ConsumptionRecord, RequestLog, SystemConfig):
            table = model.__table__.to_metadata(metadata)
            table.indexes = {index for index in table.indexes if not any(col.name in new_columns for col in index.columns)}
            for column in list(table.columns):
                if column.name in new_columns:
                    table._columns.remove(column)
        metadata.create_all(engine)
        upgrade = (Path(__file__).parents[1] / "sql/upgrade_cache_simulation_20261015.sql").read_text()
        for _ in range(2):
            raw = engine.raw_connection()
            try:
                cursor = raw.cursor()
                cursor.execute(upgrade)
                while cursor.nextset():
                    pass
                raw.commit()
                cursor.close()
            finally:
                raw.close()
        with engine.connect() as db:
            assert db.execute(text("SELECT config_value FROM system_config WHERE config_key='cache_simulation_config'")).scalar()
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f"DROP DATABASE `{name}`"))
        admin.dispose()


@pytest.mark.parametrize("script", ["backend/sql/init.sql", "backend/sql/initData.sql", "sql/initData.sql"])
def test_fresh_install_simulation_schema(mysql_engine, script):
    """Execute only this feature's table definitions in the UUID test database."""
    source = (Path(__file__).parents[2] / script).read_text()
    tables = (CacheSimulationRule, CacheSimulationDecision, RequestLog, ConsumptionRecord)
    for model in tables:
        name = model.__tablename__
        match = re.search(r"CREATE TABLE(?: IF NOT EXISTS)? `?" + name + r"`?\s*\(.*?\)\s*ENGINE=[^\n]*;", source, re.S)
        assert match, f"missing fresh-install table {name} in {script}"
        with mysql_engine.begin() as connection:
            connection.execute(text(f"DROP TABLE `{name}`"))
            connection.exec_driver_sql(match.group(0))
        columns = {item["name"]: item for item in inspect(mysql_engine).get_columns(name)}
        if model in (CacheSimulationRule, CacheSimulationDecision):
            assert set(columns) == set(model.__table__.columns.keys())
        else:
            assert {"usage_accounting_version", "billable_cache_creation_input_tokens",
                    "cache_simulation_decision_id", "cache_simulation_applied"} <= set(columns)
        if model is RequestLog:
            assert "failure_stage" in columns
        if model is CacheSimulationDecision:
            assert all(str(columns[key]["type"]) == "MEDIUMTEXT" for key in ("snapshot_json", "proposed_state_json"))
            unique = {tuple(item["column_names"]) for item in inspect(mysql_engine).get_unique_constraints(name)}
            assert {("request_id",), ("decision_id",)} <= unique
        if model is CacheSimulationRule:
            unique = {tuple(item["column_names"]) for item in inspect(mysql_engine).get_unique_constraints(name)}
            assert ("user_id", "group_id") in unique

    config = re.search(r"INSERT INTO system_config \([^;]*?\)\s*VALUES \('cache_simulation_config',.*?;", source, re.S)
    assert config
    with mysql_engine.begin() as connection:
        connection.execute(text("DELETE FROM system_config WHERE config_key='cache_simulation_config'"))
        connection.exec_driver_sql(config.group(0))
        installed = json.loads(connection.execute(text("SELECT config_value FROM system_config WHERE config_key='cache_simulation_config'")).scalar_one())
        assert installed == Service.DEFAULT_CONFIG


@pytest.fixture
def simulation(request, ledger, isolated_redis, monkeypatch):
    isolated_redis.flushdb()  # This Redis process belongs exclusively to this test module.
    monkeypatch.setattr(settings, "CACHE_SIMULATION_HMAC_KEY", "test-only-key-" * 4)
    factory = ledger.factory
    if getattr(request, "param", "sqlite") == "mysql":
        engine = request.getfixturevalue("mysql_engine")
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        Base.metadata.create_all(engine, tables=[x.__table__ for x in (RequestLog, ConsumptionRecord, SysUser, UserApiKey, UserBalance)])
        with factory.begin() as db:
            db.query(SystemConfig).delete()
            db.add(SysUser(id=1, username="cache-test", email="cache@example.test", password_hash="test", subscription_type="balance"))
            db.add(UserApiKey(id=1, user_id=1, name="test", key_prefix="test", key_hash="test", total_requests=0, total_tokens=0, total_cost=0))
            db.add(UserBalance(user_id=1, balance=Decimal("1000"), total_consumed=0))
        ledger.factory = factory
    Base.metadata.create_all(factory.kw["bind"], tables=[x.__table__ for x in (CacheSimulationRule, CacheSimulationDecision, ModelGroup, SystemConfig)])
    ledger.model.id = 7
    ledger.model.model_series = "claude"
    with factory.begin() as db:
        db.add(ModelGroup(id=11, model_series="claude", code="claude-aws", name="claude-aws", enabled=1))
        db.add(ModelGroup(id=12, model_series="claude", code="other", name="other", enabled=1))
        db.add(SystemConfig(id=1, config_key=Service.CONFIG_KEY, config_value=canonical_json({**Service.DEFAULT_CONFIG, "enabled": True}), config_type="json"))
        db.add(CacheSimulationRule(id=1, user_id=1, group_id=11, operator_id=1, generation=1, enabled=1))
    @contextmanager
    def scope():
        with factory.begin() as db:
            yield db
    @contextmanager
    def accounting_scope():
        with factory.begin() as db:
            yield db
            if ledger.fail_commit:
                ledger.fail_commit = False
                raise RuntimeError("simulated transaction rollback")
    state = State(isolated_redis)
    session = str(uuid.uuid4())
    context = {**ledger.context, "group_id_snapshot": 11, "group_name_snapshot": "claude-aws", "simulation_success": True}
    def binding(n, session_id=session, parent=None, protocol="anthropic", extra=None):
        data = {"messages": messages(n)} if protocol != "responses" else {"input": messages(n)}
        if session_id:
            data["session_id"] = session_id
        if parent:
            data["previous_response_id"] = parent
        with factory() as db:
            user = db.get(SysUser, 1)
            return Service.bind_context(db, user, ledger.model, {**context, **(extra or {}),
                "cache_simulation_identity": Identity.capture(protocol, data)})
    def run(n, *, buckets=None, request_id=None, context_override=None, response_id=None):
        buckets = buckets or TokenBuckets(28000 + n * 1000, 500, 1000)
        cache_info = {"logical_input_tokens": buckets.context, "upstream_input_tokens": buckets.input,
            "upstream_cache_read_input_tokens": buckets.read, "upstream_cache_creation_input_tokens": buckets.creation,
            "upstream_cache_creation_5m_input_tokens": buckets.creation, "upstream_cache_creation_1h_input_tokens": 0,
            "_cache_simulation_usage": {"valid": True, "input_present": True, "output_present": True, "source": "upstream"}}
        current = context_override if context_override is not None else binding(n)
        if response_id:
            current = {**current, "simulation_response_id": response_id}
        result = ProxyService._finalize_successful_text_request(None,
            SimpleNamespace(id=1, username="cache-test", status=1), SimpleNamespace(id=1), ledger.model,
            request_id or str(uuid.uuid4()), "claude-test", buckets.input, buckets.output, CHANNEL, "127.0.0.1", 10,
            is_stream=True, cache_info=cache_info, billing_context=current)
        with factory() as db:
            row = db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).first()
            dto = Service.record_dto(row, detail=True) if row else None
        return result, dto
    ledger.run, ledger.binding, ledger.state, ledger.scope = run, binding, state, scope
    with (patch("app.services.cache_simulation_service.session_scope", scope),
          patch("app.services.cache_simulation_service.CacheSimulationStateService", return_value=state),
          patch("app.services.proxy_service.session_scope", accounting_scope),
          patch("app.database.session_scope", scope)):
        yield ledger


def messages(n):
    result = []
    for i in range(n):
        if i:
            result.append({"role": "assistant", "content": f"answer-{i-1}"})
        result.append({"role": "user", "content": f"question-{i}"})
    return result


def test_allocator_example_and_feasible_bounds():
    raw = TokenBuckets(32654, 524, 2655)
    allocation = Allocator.allocate(raw, raw, Decimal(1), coefficient=832)
    assert allocation.effective == TokenBuckets(5495, 524, 29814)
    assert allocation.effective.total == 35833
    assert allocation.billed == allocation.effective
    assert allocation.effective.read / raw.total >= .832
    assert Allocator.allocate(TokenBuckets(1, 100, 0, 100), TokenBuckets(1, 100, 0, 100), Decimal(1)).reason == "unreachable_floor"


def test_allocator_properties_across_rates_and_rounding():
    rng = random.Random(567)
    applied = 0
    for _ in range(1200):
        raw = TokenBuckets(rng.randrange(200000), rng.randrange(20000), rng.randrange(20000), rng.randrange(20000))
        m = Decimal(rng.choice(["0.01", ".3", ".999", "1", "1.234", "2.7"]))
        baseline = Allocator.baseline(raw, m)
        allocation = Allocator.allocate(raw, baseline, m, randbelow=lambda upper: upper - 1)
        assert allocation.effective.total == raw.total and allocation.billed.total == baseline.total
        assert (allocation.effective.output, allocation.effective.creation) == (raw.output, raw.creation)
        assert (allocation.billed.output, allocation.billed.creation) == (baseline.output, baseline.creation)
        if allocation.coefficient:
            applied += 1
            assert 800 <= allocation.coefficient <= 950
            assert allocation.effective.read * 5 >= raw.total * 4
            assert allocation.billed.read * 5 >= baseline.total * 4
            assert allocation.effective.input >= 0 and allocation.billed.input >= 0
    assert applied > 500


@pytest.mark.parametrize("coefficient", [800, 950])
def test_coefficient_endpoints(coefficient):
    result = Allocator.allocate(TokenBuckets(100000, 1), TokenBuckets(100000, 1), Decimal(1), coefficient=coefficient)
    assert result.coefficient == coefficient
    assert result.effective.total == 100001


def test_explicit_zero_and_strict_configuration():
    row = SimpleNamespace(usage_accounting_version=1, billable_input_tokens=0, input_tokens=400)
    assert accounted_bucket(row, "billable_input_tokens", "input_tokens") == 0
    row.usage_accounting_version = 0
    assert accounted_bucket(row, "billable_input_tokens", "input_tokens") == 400
    for value in [True, 0, 1441, 1.5, "5"]:
        with pytest.raises(ValidationError):
            CacheSimulationConfigUpdate(enabled=True, ttl_minutes=value, version=1)
    assert usage_provenance({"input_tokens": 0, "output_tokens": 0})["valid"]
    assert not usage_provenance({"input_tokens": -1, "output_tokens": 0})["valid"]
    assert not usage_provenance({"input_tokens": 1, "output_tokens": 1.5})["valid"]


def test_redis_fence_cas_memo_and_fixed_expiry(isolated_redis):
    state = State(isolated_redis)
    digest = uuid.uuid4().hex
    loaded = state.load(digest)
    assert loaded.status == "missing"
    proposed = {"revision": 1, "expires_at": loaded.now + 60}
    reserved = state.reserve(digest, "req", 0, proposed)
    assert reserved.status == "reserved"
    assert state.load(digest).state is None
    assert state.reserve(digest, "other", 0, proposed).status == "busy"
    assert state.commit(digest, "req", {**reserved.reservation, "fence": "wrong"}, proposed, "hash") == "lost"
    assert state.commit(digest, "req", reserved.reservation, proposed, "hash") == "committed"
    assert state.commit(digest, "req", reserved.reservation, proposed, "hash") == "committed"
    assert state.commit(digest, "req", reserved.reservation, proposed, "other") == "conflict"
    assert state.reserve(digest, "req", 1, proposed).status == "duplicate"
    assert state.reserve(digest, "other", 0, proposed).status == "conflict"
    expiration = isolated_redis.pexpiretime(state.keys(digest)[0])
    second = {**proposed, "revision": 2}
    reservation = state.reserve(digest, "r2", 1, second)
    assert state.commit(digest, "r2", reservation.reservation, second, "h2") == "committed"
    assert isolated_redis.pexpiretime(state.keys(digest)[0]) == expiration
    third = {**proposed, "revision": 3}
    lost = state.reserve(digest, "r3", 2, third)
    isolated_redis.delete(state.keys(digest)[0])
    assert state.commit(digest, "r3", lost.reservation, third, "h3") == "lost"
    assert state.load(digest).state is None


def test_redis_unavailable_is_explicit():
    bad = State(SimpleNamespace(eval=lambda *a: (_ for _ in ()).throw(RuntimeError())))
    assert bad.load("a").status == "unavailable"
    assert bad.reserve("a", "r", 0, {"expires_at": 123}).status == "unavailable"
    assert bad.commit("a", "r", {}, {}, "h") == "unavailable"


def test_pending_request_cannot_borrow_new_window_revision(simulation):
    first = simulation.run(1)[1]
    simulation.run(2)
    pending = simulation.binding(3)
    digest = first["session_digest"]
    old_window = simulation.state.load(digest).state["window_id"]
    simulation.state.client.pexpire(simulation.state.keys(digest)[0], 1)
    time.sleep(.02)
    simulation.run(1)
    simulation.run(2)
    fresh = simulation.state.load(digest).state
    assert fresh["revision"] == pending["cache_simulation_binding"]["expected_revision"] == 2
    assert fresh["window_id"] != old_window
    late = simulation.run(3, context_override=pending)[1]
    assert late["outcome"] == "skipped" and late["reason"] == "concurrent_revision"
    assert simulation.state.load(digest).state == fresh
    assert simulation.run(3)[1]["outcome"] == "simulated"


def test_redis_cas_rejects_repeated_revision_from_different_window(isolated_redis):
    state = State(isolated_redis)
    digest = uuid.uuid4().hex
    now = state.load(digest).now
    old = {"window_id": "old-window", "revision": 2, "expires_at": now + 60}
    fresh = {**old, "window_id": "new-window"}
    isolated_redis.set(state.keys(digest)[0], canonical_json(fresh))
    proposed = {**old, "revision": 3}
    assert state.reserve(digest, "late", 2, proposed, expected_window_id="old-window").status == "conflict"
    isolated_redis.set(state.keys(digest)[0], canonical_json(old))
    lease = state.reserve(digest, "inflight", 2, proposed, expected_window_id="old-window")
    assert lease.status == "reserved"
    isolated_redis.set(state.keys(digest)[0], canonical_json(fresh))
    assert state.commit(digest, "inflight", lease.reservation, proposed, "hash") == "lost"
    assert state.load(digest).state == fresh


def test_three_turn_trigger_recovery_and_conservation(simulation):
    rows = [simulation.run(n)[1] for n in [1, 2, 3]]
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    simulated = rows[-1]
    assert simulated["accounting_status"] == "settled" and simulated["state_delivery"] == "committed"
    assert .8 <= simulated["effective_hit_ratio"] <= .951
    usage = simulated["usage"]
    assert sum(usage["raw"].values()) == sum(usage["effective"].values())
    assert sum(usage["baseline"].values()) == sum(usage["billed"].values())
    good = simulation.run(4, buckets=TokenBuckets(1000, 500, 34000))[1]
    again = simulation.run(5, buckets=TokenBuckets(37000, 500, 1000))[1]
    assert good["outcome"] == "upstream_good" and good["usage"]["raw"] == good["usage"]["effective"]
    assert again["outcome"] == "simulated" and again["window_expires_at"] == simulated["window_expires_at"]
    with simulation.factory() as db:
        record = db.query(ConsumptionRecord).filter_by(request_id=simulated["request_id"]).one()
        assert record.upstream_cache_read_input_tokens == 1000
        assert record.billable_cache_read_input_tokens == usage["billed"]["read"]
        assert record.cache_simulation_applied == 1 and record.output_tokens == 500
        assert float(record.total_cost) == pytest.approx(simulated["effective_cost"], abs=1e-6)


def test_repeated_request_reuses_receipt_without_charge(simulation):
    simulation.run(1); simulation.run(2)
    context = simulation.binding(3)
    request_id = str(uuid.uuid4())
    first, a = simulation.run(3, request_id=request_id, context_override=context)
    second, b = simulation.run(3, request_id=request_id, context_override=context)
    assert first.success and second.success and a["coefficient"] == b["coefficient"]
    assert first.receipt == second.receipt
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3
        assert db.query(RequestLog).count() == 3
        assert db.get(UserApiKey, 1).total_requests == 3


def test_scope_and_concurrent_context_do_not_advance(simulation):
    simulation.run(1)
    old_a, old_b = simulation.binding(2), simulation.binding(3)
    assert simulation.run(2, context_override=old_a)[1]["outcome"] == "observing"
    assert simulation.run(3, context_override=old_b)[1]["reason"] == "concurrent_revision"
    assert simulation.run(4)[1]["outcome"] == "simulated"
    context = simulation.binding(5, extra={"group_id_snapshot": 12})
    assert "cache_simulation_binding" not in context
    a = simulation.binding(5)["cache_simulation_binding"]
    for change in ({"user_id": 2}, {"group_id": 12}, {"model_id": 9}, {"protocol": "openai"}):
        identity = Identity.capture("anthropic", {"session_id": "scope", "messages": messages(1)})
        scope = {"user_id": 1, "group_id": 11, "model_id": 7, "protocol": "anthropic", "rule_generation": 1, "enable_epoch": 1}
        x = Identity.bind(identity, scope, simulation.state)
        y = Identity.bind(identity, {**scope, **change}, simulation.state)
        assert x["digest"] != y["digest"]
    assert a["identity"]["complete"]


def test_compression_strong_and_weak_identity(simulation):
    simulation.run(1); simulation.run(2); simulation.run(3)
    compressed = simulation.binding(1)
    compressed["cache_simulation_binding"]["identity"]["fingerprint"] = "compressed-new"
    row = simulation.run(1, buckets=TokenBuckets(15000, 500, 1000), context_override=compressed)[1]
    assert row["outcome"] == "simulated" and row["reason"] == "confirmed_compaction"
    weak_a = simulation.binding(1, session_id=None)["cache_simulation_binding"]
    weak_b = simulation.binding(1, session_id=None)["cache_simulation_binding"]
    assert weak_a["digest"] != weak_b["digest"]


def test_ttl_change_does_not_extend_old_window_and_disable_invalidates(simulation):
    simulation.run(1); simulation.run(2)
    row = simulation.run(3)[1]
    with simulation.factory() as db:
        config = Service.config_dto(db)
        saved = Service.update_config(db, CacheSimulationConfigUpdate(enabled=True, ttl_minutes=30, version=config["version"]), 1)
    assert saved["ttl_seconds"] == 1800
    next_row = simulation.run(4)[1]
    assert next_row["window_expires_at"] == row["window_expires_at"]
    digest = next_row["session_digest"]
    simulation.state.client.delete(simulation.state.keys(digest)[0])
    after_expiry = simulation.run(5)[1]
    assert after_expiry["outcome"] == "observing"
    assert datetime.fromisoformat(after_expiry["window_expires_at"].rstrip("Z")) - datetime.fromisoformat(after_expiry["window_started_at"].rstrip("Z")) == timedelta(minutes=30)
    with simulation.factory() as db:
        Service.update_rule(db, 1, CacheSimulationRuleUpdate(enabled=False, generation=1), 1)
        Service.update_rule(db, 1, CacheSimulationRuleUpdate(enabled=True, generation=2), 1)
    assert simulation.run(6)[1]["outcome"] == "observing"


def test_failed_settlement_recovery_updates_same_log_and_frozen_price(simulation):
    simulation.run(1); simulation.run(2)
    with patch.object(ProxyService, "_deduct_balance_and_log", side_effect=RuntimeError("transient accounting failure")):
        result, failed = simulation.run(3)
    assert not result.success and failed["accounting_status"] == "failed" and failed["outcome"] == "simulated"
    with simulation.factory() as db:
        log = db.query(RequestLog).filter_by(request_id=result.request_id).one()
        original_log_id = log.id
        assert log.failure_stage == "accounting" and log.status == "error"
    simulation.token_multiplier = 2.8
    simulation.model.input_price_per_million = 9999
    Service.recover_accounting(result.decision_id)
    Service.recover_accounting(result.decision_id)
    with simulation.factory() as db:
        decision = db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).one()
        log = db.query(RequestLog).filter_by(request_id=result.request_id).one()
        consumption = db.query(ConsumptionRecord).filter_by(request_id=result.request_id).one()
        assert decision.accounting_status == "settled"
        assert log.id == original_log_id and log.status == "success" and log.failure_stage is None
        assert consumption.total_tokens == failed["total_tokens"]
        assert float(consumption.total_cost) == pytest.approx(failed["effective_cost"], abs=1e-6)
        assert db.get(UserApiKey, 1).total_requests == 3


def test_invalid_usage_no_sample_and_pair_conflict(simulation):
    simulation.run(1)
    with patch.object(Service, "usage_evidence", return_value={"source": "estimated", "valid": True, "input_present": True, "output_present": True}):
        row = simulation.run(2)[1]
    assert row["reason"] == "incomplete_or_failed_usage"
    assert simulation.run(3)[1]["outcome"] == "observing"
    assert simulation.run(4)[1]["outcome"] == "simulated"
    with simulation.factory() as db:
        with pytest.raises(ServiceException) as exc:
            Service.create_rule(db, CacheSimulationRuleCreate(user_id=1, group_id=11), 1)
        assert exc.value.status_code == 409


def test_conflicting_request_id_cannot_change_or_deliver_decision(simulation):
    simulation.run(1); simulation.run(2)
    request_id = str(uuid.uuid4())
    context = simulation.binding(3)
    first, row = simulation.run(3, request_id=request_id, context_override=context)
    before = simulation.state.load(row["session_digest"]).state
    second, changed = simulation.run(3, request_id=request_id, context_override=context,
                                     buckets=TokenBuckets(41000, 500, 1000))
    assert first.success and not second.success
    assert changed is None and second.decision_id is None
    assert simulation.state.load(row["session_digest"]).state == before
    with simulation.factory() as db:
        stored = Service.record_dto(db.query(CacheSimulationDecision).filter_by(request_id=request_id).one(), detail=True)
        assert stored["usage"] == row["usage"] and stored["accounting_status"] == "settled"
        assert db.query(ConsumptionRecord).count() == 3


def test_unique_full_prefix_and_ambiguous_candidates(simulation):
    rows = [simulation.run(n, context_override=simulation.binding(n, session_id=None))[1] for n in (1, 2, 3)]
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    assert len({row["session_digest"] for row in rows}) == 1
    other = simulation.run(1, context_override=simulation.binding(1, session_id="parallel"))[1]
    prefix = simulation.binding(4, session_id=None)["cache_simulation_binding"]
    assert prefix["expected_revision"] == 0
    assert prefix["digest"] not in {rows[0]["session_digest"], other["session_digest"]}
    # The 65th entry is an overflow sentinel: never match a truncated set of 64.
    scope = prefix["scope"]
    for i in range(65):
        simulation.state.index(scope, "overflow-" + str(i), time.time() + 300)
    assert len(simulation.state.candidates(scope)) == 65
    assert simulation.binding(4, session_id=None)["cache_simulation_binding"]["expected_revision"] == 0


def test_claude_identity_conflicts_and_agent_isolation(simulation):
    session = str(uuid.uuid4())
    data = {"messages": messages(1), "metadata": {"user_id": f"user_ab12_account_test_session_{session}"}}
    metadata = Identity.capture("anthropic", data)
    assert metadata["session"] == session and metadata["source"] == "claude_metadata"
    assert not Identity.capture("anthropic", {**data, "session_id": session}, {"X-Conversation-Id": session})["ambiguous"]
    assert Identity.capture("anthropic", data, {"x-conversation-id": "different"})["ambiguous"]
    assert Identity.capture("anthropic", {**data, "session_id": "bad\nvalue"})["ambiguous"]
    arbitrary = Identity.capture("anthropic", {"messages": messages(1), "metadata": {"user_id": "ordinary-user"}})
    assert arbitrary["session"] is None
    scope = {"user_id": 1, "group_id": 11, "model_id": 7, "protocol": "anthropic", "rule_generation": 1, "enable_epoch": 1}
    a = Identity.bind(Identity.capture("anthropic", data, {"x-claude-code-agent-id": "a"}), scope, simulation.state)
    b = Identity.bind(Identity.capture("anthropic", data, {"x-claude-code-agent-id": "b"}), scope, simulation.state)
    assert a["digest"] != b["digest"] and a["scope"] != b["scope"]
    assert session not in canonical_json(a)
    oversized = Identity.capture("anthropic", {"messages": [{"role": "user", "content": "x"}] * (Identity.MAX_MESSAGES + 1)})
    assert Identity.bind(oversized, scope, simulation.state)["entry_status"] == "incomplete_context"


@pytest.mark.parametrize("session_id", [None, "strong-responses"])
def test_responses_parent_lineage_and_fork_rejected(simulation, session_id):
    one = simulation.binding(1, session_id=session_id, protocol="responses")
    row = simulation.run(1, context_override=one, response_id="resp-first")[1]
    two = simulation.binding(2, session_id=session_id, protocol="responses", parent="resp-first")
    assert two["cache_simulation_binding"]["digest"] == row["session_digest"]
    assert simulation.run(2, context_override=two, response_id="resp-second")[1]["outcome"] == "observing"
    stale = simulation.binding(3, session_id=session_id, protocol="responses", parent="resp-first")
    assert stale["cache_simulation_binding"]["entry_status"] == "lineage_conflict"
    assert simulation.run(3, context_override=stale)[1]["reason"] == "lineage_conflict"
    current = simulation.binding(4, session_id=session_id, protocol="responses", parent="resp-second")
    assert simulation.run(4, context_override=current)[1]["outcome"] == "simulated"


def test_incremental_responses_repeated_input_uses_verified_parent(simulation):
    def binding(parent=None):
        data = {"input": "继续"}
        if parent:
            data["previous_response_id"] = parent
        with simulation.factory() as db:
            return Service.bind_context(db, db.get(SysUser, 1), simulation.model,
                {**simulation.context, "group_id_snapshot": 11, "simulation_success": True,
                 "cache_simulation_identity": Identity.capture("responses", data)})
    rows = []
    for n in (1, 2, 3):
        rows.append(simulation.run(n, context_override=binding(f"repeat-{n-1}" if n > 1 else None),
                                   response_id=f"repeat-{n}")[1])
    assert [row["outcome"] for row in rows] == ["observing", "observing", "simulated"]
    assert len({row["session_digest"] for row in rows}) == 1
    replay = simulation.run(4, context_override=binding("repeat-2"))[1]
    assert replay["outcome"] == "skipped" and replay["reason"] == "lineage_conflict"


def test_unmapped_fork_parent_cannot_borrow_strong_session(simulation):
    first = simulation.run(1, context_override=simulation.binding(1, protocol="responses"), response_id="main-1")[1]
    simulation.run(2, context_override=simulation.binding(2, protocol="responses", parent="main-1"), response_id="main-2")
    fork = simulation.run(3, context_override=simulation.binding(3, protocol="responses", parent="main-1"), response_id="fork-1")[1]
    assert fork["reason"] == "lineage_conflict"
    before = simulation.state.load(first["session_digest"]).state
    next_fork = simulation.run(4, context_override=simulation.binding(4, protocol="responses", parent="fork-1"))[1]
    assert next_fork["outcome"] == "skipped" and next_fork["reason"] == "unresolved_lineage"
    assert simulation.state.load(first["session_digest"]).state == before
    main = simulation.run(4, context_override=simulation.binding(4, protocol="responses", parent="main-2"))[1]
    assert main["outcome"] == "simulated"


def test_fence_expired_before_prepared_freezes_original(simulation):
    simulation.run(1); simulation.run(2)
    original_reserve = simulation.state.reserve
    def delayed_reserve(digest, *args, **kwargs):
        result = original_reserve(digest, *args, **kwargs)
        simulation.state.client.pexpire(simulation.state.keys(digest)[1], 1)
        time.sleep(.02)
        return result
    with patch.object(simulation.state, "reserve", side_effect=delayed_reserve):
        row = simulation.run(3)[1]
    assert row["decision_status"] == "prepared" and row["accounting_status"] == "settled"
    assert row["outcome"] == "skipped" and row["reason"] == "redis_expired"
    assert row["usage"]["raw"] == row["usage"]["effective"]
    assert simulation.state.load(row["session_digest"]).state["revision"] == 2
    assert simulation.run(4)[1]["outcome"] == "simulated"


def test_good_observation_resets_and_duplicate_context_is_ignored(simulation):
    simulation.run(1)
    assert simulation.run(2, buckets=TokenBuckets(1000, 500, 30000))[1]["outcome"] == "upstream_good"
    assert simulation.run(3)[1]["outcome"] == "observing"
    duplicate = simulation.run(3)[1]
    assert duplicate["reason"] == "duplicate_context"
    assert simulation.run(4)[1]["outcome"] == "observing"
    assert simulation.run(5)[1]["outcome"] == "simulated"


def test_unreachable_floor_does_not_activate_and_global_epoch_isolates(simulation):
    simulation.run(1); simulation.run(2)
    row = simulation.run(3, buckets=TokenBuckets(1000, 30000, 1000, 35000))[1]
    assert row["reason"] == "unreachable_floor" and row["usage"]["raw"] == row["usage"]["effective"]
    assert simulation.state.load(row["session_digest"]).state["stage"] == "observing"
    row = simulation.run(4, buckets=TokenBuckets(70000, 500, 1000))[1]
    assert row["outcome"] == "simulated"
    simulation.state.client.pexpire(simulation.state.keys(row["session_digest"])[0], 1)
    time.sleep(.02)
    assert simulation.run(5)[1]["outcome"] == "observing"
    with simulation.factory() as db:
        config = Service.get_config(db)
        off = Service.update_config(db, CacheSimulationConfigUpdate(enabled=False, ttl_minutes=5, version=config["version"]), 1)
        assert "cache_simulation_binding" not in simulation.binding(6)
        on = Service.update_config(db, CacheSimulationConfigUpdate(enabled=True, ttl_minutes=5, version=off["version"]), 1)
        assert on["enable_epoch"] == config["enable_epoch"] + 1
    assert simulation.run(6)[1]["outcome"] == "observing"


def test_usage_alias_conflicts_are_ineligible():
    base = {"input_tokens": 50, "output_tokens": 4}
    for extra in ({"prompt_tokens": 51}, {"completion_tokens": 5},
                  {"cache_read_input_tokens": 0, "cached_tokens": 10},
                  {"cache_creation_input_tokens": 0, "cache_write_tokens": 20},
                  {"prompt_tokens_details": {"cached_tokens": -1}},
                  {"cache_creation": {"ephemeral_5m_input_tokens": 1.5}}):
        assert not usage_provenance({**base, **extra})["valid"]
    assert usage_provenance({**base, "prompt_tokens": 50, "completion_tokens": 4})["valid"]


def make_due(simulation, decision_id):
    with simulation.factory.begin() as db:
        db.query(CacheSimulationDecision).filter_by(decision_id=decision_id).update({"next_retry_at": datetime.utcnow() - timedelta(seconds=1)})


def test_expired_draft_defers_live_or_unknown_reservation_then_freezes_raw(simulation):
    simulation.run(1); simulation.run(2)
    with patch.object(Service, "prepare_draft", side_effect=RuntimeError("crash after draft")):
        result, row = simulation.run(3)
    assert not result.success and row["decision_status"] == "draft"
    digest = row["session_digest"]
    reservation = simulation.state.reserve(digest, result.request_id, 2,
        {"revision": 3, "expires_at": time.time() + 300},
        expected_window_id=simulation.state.load(digest).state["window_id"])
    assert reservation.status == "reserved"
    make_due(simulation, result.decision_id)
    assert Service.recover_due() == 0
    with simulation.factory() as db:
        assert db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).one().recovery_attempts == 0
    make_due(simulation, result.decision_id)
    with patch.object(simulation.state, "reservation_status", return_value="unavailable"):
        assert Service.recover_due() == 0
    simulation.state.release(digest, reservation.reservation)
    make_due(simulation, result.decision_id)
    assert Service.recover_due() == 1
    with simulation.factory() as db:
        recovered = Service.record_dto(db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).one(), detail=True)
        assert recovered["reason"] == "expired_draft" and recovered["accounting_status"] == "settled"
        assert recovered["usage"]["raw"] == recovered["usage"]["effective"]
        assert db.query(ConsumptionRecord).count() == 3
    assert simulation.state.load(digest).state["revision"] == 2


def test_prepared_fence_loss_keeps_frozen_allocation_and_recovers_once(simulation):
    simulation.run(1); simulation.run(2)
    with patch.object(Service, "deliver_state", side_effect=RuntimeError("crash after prepared")):
        result, row = simulation.run(3)
    assert row["decision_status"] == "prepared" and row["outcome"] == "simulated"
    simulation.state.client.delete(*simulation.state.keys(row["session_digest"])[:2])
    make_due(simulation, result.decision_id)
    assert Service.recover_due() == 1
    assert Service.recover_due() == 0
    with simulation.factory() as db:
        recovered = Service.record_dto(db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).one(), detail=True)
        assert recovered["state_delivery"] == "lost" and recovered["accounting_status"] == "settled"
        assert recovered["usage"] == row["usage"] and recovered["coefficient"] == row["coefficient"]
        assert db.query(ConsumptionRecord).count() == 3
    assert simulation.state.load(row["session_digest"]).status == "missing"


def test_recovery_stops_at_manual_review(simulation):
    with patch.object(ProxyService, "_deduct_balance_and_log", side_effect=RuntimeError("persistent failure")):
        result, _ = simulation.run(1)
        for _ in range(Service.MAX_RECOVERY_ATTEMPTS + 1):
            make_due(simulation, result.decision_id)
            assert Service.recover_due() == 0
    with simulation.factory() as db:
        row = db.query(CacheSimulationDecision).filter_by(decision_id=result.decision_id).one()
        assert row.decision_status == "manual_review" and row.recovery_attempts == Service.MAX_RECOVERY_ATTEMPTS
        assert db.query(ConsumptionRecord).count() == 0


@pytest.mark.parametrize("metric,official", [("total_tokens", False), ("cost_usd", True), ("cost_usd", False)])
def test_simulated_quota_uses_raw_tokens_or_effective_cost(simulation, metric, official):
    simulation.run(1); simulation.run(2)
    simulation.token_multiplier = 1.7
    with simulation.factory.begin() as db:
        db.get(SysUser, 1).subscription_type = "quota"
    subscription = SimpleNamespace(id=1, plan_kind_snapshot="daily_quota", model_scope_snapshot="all_models")
    cycle = SimpleNamespace(id=1, quota_limit=Decimal("1000000"), used_amount=Decimal("0"), cycle_date=date(2026, 10, 15))
    def consume(db, subscription, **kwargs):
        amount = kwargs["consumed_amount"]
        return {"subscription_cycle_id": 1, "quota_metric": metric, "quota_consumed_amount": amount,
                "quota_limit_snapshot": cycle.quota_limit, "quota_used_after": amount, "quota_cycle_date": cycle.cycle_date}
    with (patch.object(SubscriptionService, "resolve_active_subscription", return_value=subscription),
          patch.object(SubscriptionService, "_get_effective_quota_metric", return_value=metric),
          patch.object(SubscriptionService, "_uses_official_cost_for_quota", return_value=official),
          patch.object(SubscriptionService, "_get_or_create_cycle", return_value=cycle),
          patch.object(SubscriptionService, "consume_quota_amount_after_request", side_effect=consume) as consumed):
        result, row = simulation.run(3)
    assert result.success and row["outcome"] == "simulated"
    expected = (Decimal(row["total_tokens"]) if metric == "total_tokens" else Service.local_cost(
        TokenBuckets(**row["usage"]["effective" if official else "billed"]), row["prices"], quota=official))
    assert float(consumed.call_args.kwargs["consumed_amount"]) == pytest.approx(float(expected))


def test_bonus_then_partial_subscription_then_balance_and_daily_cost(simulation):
    simulation.run(1); simulation.run(2)
    simulation.model.bonus_quota_enabled = 1
    with simulation.factory.begin() as db:
        db.get(SysUser, 1).subscription_type = "quota"
    subscription = SimpleNamespace(id=1, plan_kind_snapshot="daily_quota", model_scope_snapshot="all_models")
    cycle = SimpleNamespace(id=1, quota_limit=Decimal(".01"), used_amount=Decimal("0"), cycle_date=date(2026, 10, 15))
    def consume(db, subscription, **kwargs):
        return {"subscription_cycle_id": 1, "quota_metric": "cost_usd", "quota_consumed_amount": kwargs["consumed_amount"],
                "quota_limit_snapshot": cycle.quota_limit, "quota_used_after": kwargs["consumed_amount"], "quota_cycle_date": cycle.cycle_date}
    with simulation.factory() as db:
        balance_before = db.query(UserBalance).one().balance
        key_cost_before = db.get(UserApiKey, 1).daily_used_usd
    with (patch.object(SubscriptionBonusService, "consume_available", return_value=Decimal(".01")) as bonus,
          patch.object(SubscriptionService, "resolve_active_subscription", return_value=subscription),
          patch.object(SubscriptionService, "_get_effective_quota_metric", return_value="cost_usd"),
          patch.object(SubscriptionService, "_uses_official_cost_for_quota", return_value=False),
          patch.object(SubscriptionService, "_get_or_create_cycle", return_value=cycle),
          patch.object(SubscriptionService, "consume_quota_amount_after_request", side_effect=consume) as consumed):
        result, row = simulation.run(3)
    assert result.success and row["outcome"] == "simulated"
    assert float(bonus.call_args.args[2]) == pytest.approx(row["effective_cost"])
    assert consumed.call_args.kwargs["consumed_amount"] == Decimal(".01")
    with simulation.factory() as db:
        cost = db.query(ConsumptionRecord).filter_by(request_id=result.request_id).one()
        assert cost.billing_mode == "mixed" and cost.bonus_quota_consumed == Decimal(".01")
        assert float(balance_before - db.query(UserBalance).one().balance) == pytest.approx(row["effective_cost"] - .02, abs=1e-6)
        assert float(db.get(UserApiKey, 1).daily_used_usd - key_cost_before) == pytest.approx(row["effective_cost"], abs=1e-6)


@pytest.mark.parametrize("simulation", ["mysql"], indirect=True)
def test_mysql_upgrade_concurrent_settlement_and_rollback(simulation):
    from concurrent.futures import ThreadPoolExecutor
    simulation.run(1); simulation.run(2)
    # Prepare a fixed decision but let two workers race on its local settlement.
    with patch.object(ProxyService, "_deduct_balance_and_log", side_effect=RuntimeError("pause before accounting")):
        result, row = simulation.run(3)
    assert row["outcome"] == "simulated"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: Service.recover_accounting(result.decision_id), [1, 2]))
    assert outcomes == [None, None]
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3
        assert db.get(UserApiKey, 1).total_requests == 3
    simulation.fail_commit = True
    result, row = simulation.run(4)
    assert not result.success and row["accounting_status"] == "failed"
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 3
        assert db.get(UserApiKey, 1).total_requests == 3
    Service.recover_accounting(result.decision_id)
    with simulation.factory() as db:
        assert db.query(ConsumptionRecord).count() == 4
        assert db.get(UserApiKey, 1).total_requests == 4
        assert db.query(RequestLog).count() == 4
