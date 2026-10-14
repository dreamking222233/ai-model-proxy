"""Daily USD limits across ledger funding sources and HTTP/WS/video protocols."""
import asyncio
import json
import time
from contextlib import contextmanager, ExitStack
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI, Depends
import httpx
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.dependencies import verify_api_key
from app.core.exceptions import ServiceException, register_exception_handlers
from app.database import Base, get_db
from app.models.user import SysUser, UserApiKey
from app.models.model import ModelGroup
from app.models.log import ConsumptionRecord, UserBalance, VideoTaskBillingSnapshot, RequestLog
from app.schemas.user import ApiKeyCreateRequest, ApiKeyDailyLimitUpdate
from app.services.api_key_service import ApiKeyService
from app.services.proxy_service import ProxyService
from app.services.subscription_service import SubscriptionService
from app.services.subscription_bonus_service import SubscriptionBonusService
from app.services.channel_passthrough_service import ChannelPassthroughService, PassthroughCandidate, UsageObserver
from test_cache_creation_billing import CHANNEL, ledger, PARSERS, usage
from test_channel_passthrough import FakeClientWebSocket, FakeUpstreamWebSocket
from app.models.channel import Channel

TODAY = date(2026, 10, 14)

@pytest.fixture
def keys():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[m.__table__ for m in (SysUser, UserApiKey, ModelGroup, VideoTaskBillingSnapshot, RequestLog)])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(SysUser(id=1, username='owner', email='owner@test.example', password_hash='x'))
        for i, owner in ((1, 1), (2, 1), (3, 2)):
            db.add(UserApiKey(id=i, user_id=owner, name=str(i), key_hash=str(i), key_prefix='sk-test', daily_limit_usd=300, daily_used_usd=300, daily_usage_date=TODAY, total_cost=500))
    with patch.object(ApiKeyService, 'get_beijing_date', return_value=TODAY):
        yield factory
    engine.dispose()

@pytest.mark.parametrize('utc,expected', [('2026-10-14T15:59:59+00:00', TODAY), ('2026-10-14T16:00:00+00:00', date(2026,10,15))])
def test_beijing_midnight(utc, expected):
    with patch('app.services.api_key_service.datetime') as clock:
        clock.now.return_value = datetime.fromisoformat(utc)
        assert ApiKeyService.get_beijing_date() == expected
        clock.now.assert_called_once_with(timezone.utc)

def test_threshold_rotation_and_round_half_up(keys):
    with keys() as db:
        key = db.get(UserApiKey, 1)
        with pytest.raises(ServiceException) as exc:
            ApiKeyService.assert_daily_limit(key)
        assert (exc.value.status_code, exc.value.error_code, exc.value.detail) == (429, 'API_KEY_DAILY_LIMIT_EXCEEDED', '当日请求已超出设置最大额度')
        key.daily_used_usd = Decimal('299.999999')
        ApiKeyService.assert_daily_limit(key)
        ApiKeyService.record_daily_cost(key, Decimal('0.0000005'))
        assert key.daily_used_usd == 300
        key.daily_usage_date = date(2026,10,13)
        assert ApiKeyService.daily_usage_payload(key)['daily_used_usd'] == 0
        ApiKeyService.assert_daily_limit(key)
        ApiKeyService.record_daily_cost(key, Decimal('0.25'))
        assert (key.daily_used_usd, key.daily_usage_date) == (Decimal('.25'), TODAY)

def test_limit_changes_and_two_resets_are_isolated(keys):
    with keys() as db:
        assert ApiKeyService.set_daily_limit(db, 1, 1, Decimal(250))['daily_limit_exceeded']
        assert ApiKeyService.set_daily_limit(db, 1, 1, None)['daily_used_usd'] == 300
        ApiKeyService.set_daily_limit(db, 1, 1, Decimal(300))
        ApiKeyService.reset_usage(db, 1, 1)
        assert ApiKeyService.daily_usage_payload(db.get(UserApiKey, 1))['daily_limit_exceeded']
        result = ApiKeyService.reset_daily_usage(db, 1, 1)
        assert result['daily_used_usd'] == 0 and result['daily_limit_usd'] == 300
        assert db.get(UserApiKey, 2).daily_used_usd == 300 and db.get(UserApiKey, 1).total_cost == 0
        for method, args in ((ApiKeyService.set_daily_limit, (None,)), (ApiKeyService.reset_daily_usage, ())):
            with pytest.raises(ServiceException):
                method(db, 1, 3, *args)

def test_ws_fresh_read_sees_committed_reset(keys):
    @contextmanager
    def scope():
        with keys() as db:
            yield db
    with patch('app.database.session_scope', scope), keys() as stale:
        cached = stale.get(UserApiKey, 1)
        with pytest.raises(ServiceException):
            ApiKeyService.assert_current_daily_limit(1)
        with keys() as writer:
            ApiKeyService.reset_daily_usage(writer, 1, 1)
        assert cached.daily_used_usd == 300
        ApiKeyService.assert_current_daily_limit(1)
        with pytest.raises(ServiceException):
            ApiKeyService.assert_current_daily_limit(999)

@pytest.mark.parametrize('invalid', [0, -1, '0.0000001', '1000000001', 'NaN', 'Infinity'])
def test_schema_rejects_invalid_caps(invalid):
    for model, extra in ((ApiKeyCreateRequest, {'name': 'x'}), (ApiKeyDailyLimitUpdate, {})):
        with pytest.raises(ValidationError):
            model(daily_limit_usd=invalid, **extra)

def test_schema_nullable_but_update_required():
    assert ApiKeyCreateRequest(name='x').daily_limit_usd is None
    assert ApiKeyDailyLimitUpdate(daily_limit_usd=None).daily_limit_usd is None
    with pytest.raises(ValidationError):
        ApiKeyDailyLimitUpdate()

@pytest.mark.parametrize('funding', ['balance', 'bonus', 'subscription_usd', 'subscription_tokens', 'mixed'])
def test_real_ledger_accumulates_full_usd_before_funding_split(ledger, funding):
    with ledger.factory.begin() as db:
        if funding.startswith('subscription') or funding == 'mixed':
            db.get(SysUser, 1).subscription_type = 'quota'
    metric = 'total_tokens' if funding == 'subscription_tokens' else 'cost_usd'
    subscription = SimpleNamespace(id=1, plan_kind_snapshot='daily_quota', model_scope_snapshot='all_models')
    cycle = SimpleNamespace(id=1, quota_limit=Decimal('.001') if funding == 'mixed' else Decimal('1000000'), used_amount=Decimal(0), cycle_date=TODAY)
    def consume(db, sub, **kwargs):
        amount = kwargs['consumed_amount']
        return dict(subscription_cycle_id=1, quota_metric=metric, quota_consumed_amount=amount, quota_limit_snapshot=cycle.quota_limit, quota_used_after=amount, quota_cycle_date=TODAY)
    with ExitStack() as stack:
        stack.enter_context(patch.object(SubscriptionService, 'resolve_active_subscription', return_value=subscription))
        stack.enter_context(patch.object(SubscriptionService, '_get_effective_quota_metric', return_value=metric))
        stack.enter_context(patch.object(SubscriptionService, '_uses_official_cost_for_quota', return_value=False))
        stack.enter_context(patch.object(SubscriptionService, '_get_or_create_cycle', return_value=cycle))
        stack.enter_context(patch.object(SubscriptionService, 'consume_quota_amount_after_request', side_effect=consume))
        if funding == 'bonus':
            ledger.model.bonus_quota_enabled = 1
            stack.enter_context(patch.object(SubscriptionBonusService, 'consume_available', side_effect=lambda db, user_id, amount, *a, **kw: amount))
        ledger.book(PARSERS[0](usage()))
    with ledger.factory() as db:
        record, key = db.query(ConsumptionRecord).one(), db.get(UserApiKey, 1)
        assert record.total_cost > 0
        assert key.daily_limit_usd is None and key.daily_used_usd == record.total_cost == key.total_cost
        assert key.daily_usage_date == ApiKeyService.get_beijing_date()
        assert record.billing_mode == ('subscription' if funding.startswith('subscription') else funding)
        if funding in ('bonus', 'subscription_usd', 'subscription_tokens'):
            assert db.query(UserBalance).one().balance == 1000

def test_transaction_failure_does_not_increment_daily(ledger):
    ledger.fail_commit = True
    with pytest.raises(RuntimeError):
        ledger.book(PARSERS[0](usage()))
    with ledger.factory() as db:
        assert db.get(UserApiKey, 1).daily_used_usd == 0 and db.query(ConsumptionRecord).count() == 0


def _finalize_passthrough_usage(ledger, protocol, upstream_usage, request_id, is_stream):
    observer = UsageObserver(protocol, CHANNEL)
    if protocol == 'anthropic':
        payload = dict(type='message', stop_reason='end_turn', usage=upstream_usage)
    elif protocol == 'responses':
        response = dict(object='response', status='completed', usage=upstream_usage)
        payload = dict(type='response.completed', response=response) if is_stream else response
    else:
        payload = dict(choices=[dict(finish_reason='stop')], usage=upstream_usage)
    if is_stream:
        observer.feed_sse(('data: ' + json.dumps(payload) + '\n\n').encode())
    else:
        observer.feed_json(payload)
    assert observer.usage_seen and observer.completed
    ChannelPassthroughService._finalize(
        None, SimpleNamespace(id=1, subscription_type='balance'), SimpleNamespace(id=1),
        ledger.model, CHANNEL, observer, request_id, 'gpt-test', '127.0.0.1',
        time.time(), is_stream, protocol, {**ledger.context, 'logical_input_tokens': 100},
    )


@pytest.mark.parametrize('protocol', ['openai', 'responses', 'anthropic'])
@pytest.mark.parametrize('is_stream', [False, True], ids=['json', 'sse'])
@pytest.mark.parametrize('read,created,expected_cost,limit,request_count', [
    (100, 0, '0.001200', '0.005', 5),
    (0, 100, '0.008100', '0.01', 2),
    (40, 60, '0.005340', '0.006', 2),
], ids=['all-read', 'all-write', 'mixed'])
def test_passthrough_cache_only_usage_reaches_daily_limit_without_double_charge(
    ledger, protocol, is_stream, read, created, expected_cost, limit, request_count,
):
    expected_cost, limit = Decimal(expected_cost), Decimal(limit)
    if protocol == 'anthropic':
        upstream_usage = dict(input_tokens=0, output_tokens=2,
                              cache_read_input_tokens=read, cache_creation_input_tokens=created)
    else:
        upstream_usage = usage(total=100, read=read, created=created, output=2)
    with ledger.factory.begin() as db:
        db.get(UserApiKey, 1).daily_limit_usd = limit
    with patch.object(ApiKeyService, 'get_beijing_date', return_value=TODAY):
        for count in range(1, request_count + 1):
            with ledger.factory() as db:
                ApiKeyService.assert_daily_limit(db.get(UserApiKey, 1))
            request_id = f'cache-daily-{count}'
            _finalize_passthrough_usage(ledger, protocol, upstream_usage, request_id, is_stream)
            with ledger.factory() as db:
                record = db.query(ConsumptionRecord).filter_by(request_id=request_id).one()
                row = db.query(RequestLog).filter_by(request_id=request_id).one()
                key, balance = db.get(UserApiKey, 1), db.query(UserBalance).one()
                assert row.input_tokens == row.raw_input_tokens == record.input_tokens == 0
                assert row.upstream_cache_read_input_tokens == read
                assert row.upstream_cache_creation_input_tokens == created
                assert row.total_tokens == row.raw_total_tokens == record.total_tokens == 102
                assert record.input_cost == 0 and record.total_cost == expected_cost
                assert record.cache_read_cost == Decimal(read * 2) / 1000000 * 3
                assert record.cache_creation_cost == Decimal(created * 25) / 1000000 * 3
                total_cost = expected_cost * count
                assert balance.balance == Decimal(1000) - total_cost
                assert key.total_cost == key.daily_used_usd == total_cost
                assert key.total_requests == count and key.total_tokens == 102 * count
                assert key.daily_usage_date == TODAY
                if count < request_count:
                    assert total_cost < limit
                    assert not ApiKeyService.daily_usage_payload(key)['daily_limit_exceeded']
                    ApiKeyService.assert_daily_limit(key)
                else:
                    assert total_cost >= limit
                    assert ApiKeyService.daily_usage_payload(key)['daily_limit_exceeded']
                    with pytest.raises(ServiceException) as exc:
                        ApiKeyService.assert_daily_limit(key)
                    assert exc.value.error_code == ApiKeyService.DAILY_LIMIT_ERROR
                    assert exc.value.detail == '当日请求已超出设置最大额度'


@pytest.mark.parametrize('protocol', ['openai', 'responses', 'anthropic'])
@pytest.mark.parametrize('is_stream', [False, True], ids=['json', 'sse'])
@pytest.mark.parametrize('upstream_usage', [dict(output_tokens=2), dict(input_tokens=0, output_tokens=2)],
                         ids=['missing-input', 'zero-input'])
def test_passthrough_without_reported_input_keeps_estimated_charge_and_daily_limit(
    ledger, protocol, is_stream, upstream_usage,
):
    with ledger.factory.begin() as db:
        db.get(UserApiKey, 1).daily_limit_usd = Decimal('0.005')
    with patch.object(ApiKeyService, 'get_beijing_date', return_value=TODAY):
        _finalize_passthrough_usage(ledger, protocol, upstream_usage, 'fallback-daily', is_stream)
        with ledger.factory() as db:
            record, row = db.query(ConsumptionRecord).one(), db.query(RequestLog).one()
            key, balance = db.get(UserApiKey, 1), db.query(UserBalance).one()
            assert row.input_tokens == row.raw_input_tokens == record.input_tokens == 100
            assert row.upstream_cache_read_input_tokens == row.upstream_cache_creation_input_tokens == 0
            assert row.total_tokens == record.total_tokens == key.total_tokens == 102
            assert record.total_cost == key.total_cost == key.daily_used_usd == Decimal('0.006600')
            assert balance.balance == Decimal('999.993400')
            assert key.daily_usage_date == TODAY and key.total_requests == 1
            with pytest.raises(ServiceException) as exc:
                ApiKeyService.assert_daily_limit(key)
            assert exc.value.error_code == ApiKeyService.DAILY_LIMIT_ERROR


@pytest.mark.parametrize('method,path,blocked', [('POST','/v1/chat/completions',True), ('POST','/v1/responses',True), ('POST','/v1/images/generations',True), ('POST','/v1/videos',True), ('POST','/v1/messages/count_tokens',False), ('GET','/v1/videos/task/content',False), ('GET','/v1/models',False)])
def test_http_contract_and_existing_task_exemption(keys, method, path, blocked):
    app = FastAPI(); register_exception_handlers(app)
    app.dependency_overrides[get_db] = lambda: None
    async def endpoint(auth=Depends(verify_api_key)):
        return {'ok': True}
    app.add_api_route(path, endpoint, methods=[method])
    with keys() as db, patch('app.core.dependencies.verify_api_key_from_headers', return_value=(db.get(SysUser,1),db.get(UserApiKey,1))):
        async def call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                return await client.request(method, path)
        response = asyncio.run(call())
    assert response.status_code == (429 if blocked else 200)
    if blocked:
        assert response.json() == dict(code='API_KEY_DAILY_LIMIT_EXCEEDED', message='当日请求已超出设置最大额度', data=None)

def daily_error():
    return ServiceException(429, '当日请求已超出设置最大额度', ApiKeyService.DAILY_LIMIT_ERROR)

def assert_ws_refusal(ws):
    event = json.loads(ws.sent[-1])
    assert event['status'] == 429 and event['error'] == dict(type='rate_limit_error', code=ApiKeyService.DAILY_LIMIT_ERROR, message='当日请求已超出设置最大额度')
    assert ws.closed[-1][0] == 1008

def candidate():
    channel = Channel(id=7,name='native',base_url='https://upstream.example/v1',api_key='sk-upstream',protocol_type='openai',auth_header_type='authorization',priority=1,enabled=1,passthrough_enabled=1)
    model = SimpleNamespace(id=3, model_name='test',model_type='chat',billing_type='token')
    return PassthroughCandidate(channel,model,'passthrough')

def test_managed_ws_checks_each_turn_before_upstream():
    first = json.dumps(dict(type='response.create', model='test', generate=False, input=[]))
    async def run():
        ws = FakeClientWebSocket(first)
        with (patch('app.services.proxy_service.release_session_connection'), patch.object(ApiKeyService,'assert_current_daily_limit',side_effect=[None,daily_error()]) as check, patch.object(ProxyService,'_resolve_requested_model_or_raise') as upstream):
            assert await ProxyService.handle_responses_websocket(None, SimpleNamespace(id=1), SimpleNamespace(id=1), ws, 'test')
            assert check.call_count == 2
            upstream.assert_not_called()
        assert_ws_refusal(ws)
    asyncio.run(run())

def test_native_ws_first_turn_never_connects_when_limited():
    first = json.dumps(dict(type='response.create', model='test'))
    async def run():
        ws = FakeClientWebSocket(first)
        with patch.object(ApiKeyService,'assert_current_daily_limit',side_effect=daily_error()), patch('websockets.connect',AsyncMock()) as connect:
            await ChannelPassthroughService._relay_websocket(ws,None,SimpleNamespace(id=1),SimpleNamespace(id=1),candidate(),first,json.loads(first),'test')
            connect.assert_not_called()
        assert_ws_refusal(ws)
    asyncio.run(run())

@pytest.mark.parametrize('binary', [False, True])
def test_native_ws_next_turn_rejects_and_cleans_forwarders(binary):
    first = json.dumps(dict(type='response.create', model='test'))
    async def run():
        gate = asyncio.Event()
        class Upstream(FakeUpstreamWebSocket):
            async def __anext__(self):
                if self.events:
                    return self.events.pop()
                await asyncio.Future()
        class Client(FakeClientWebSocket):
            async def receive(self):
                await gate.wait()
                return await super().receive()
        next_turn=json.dumps(dict(type='response.append',input='next'))
        ws=Client(first,[next_turn.encode() if binary else next_turn])
        upstream=Upstream([json.dumps(dict(type='response.completed',response=dict(id='r1',usage=dict(input_tokens=1,output_tokens=1))))])
        route=candidate()
        with (patch.object(ApiKeyService,'assert_current_daily_limit',side_effect=[None,daily_error()]) as check, patch('websockets.connect',AsyncMock(return_value=upstream)), patch('app.services.channel_passthrough_service.release_session_connection'), patch.object(ChannelPassthroughService,'_build_billing',return_value=(None,{})), patch.object(ChannelPassthroughService,'get_candidates',return_value=[route]), patch.object(ChannelPassthroughService,'_finalize',side_effect=lambda *a,**kw: gate.set()) as finalize, patch.object(ProxyService,'_billing_concurrency_lease_ttl_seconds',return_value=7200)):
            await asyncio.wait_for(ChannelPassthroughService._relay_websocket(ws,None,SimpleNamespace(id=1),SimpleNamespace(id=1),route,first,json.loads(first),'test'),timeout=2)
            assert check.call_count == 2 and finalize.call_count == 1
        assert upstream.sent == [first] and upstream.closed
        assert_ws_refusal(ws)
    asyncio.run(run())

def test_video_creator_key_survives_restart_and_query_key_change(keys):
    @contextmanager
    def scope():
        with keys.begin() as db:
            yield db
    video_id='daily-attribution-test'
    with patch('app.services.proxy_service.session_scope',scope), keys() as db:
        ProxyService._store_video_task_route(video_id,user_id=1,user_api_key_id=1,channel_id=10,requested_model='video',actual_model='video',billing_type='request')
        ProxyService._video_task_routes.pop(video_id)
        recovered=ProxyService._load_video_task_route_snapshot(db,db.get(SysUser,1),video_id)
        assert recovered['user_api_key_id']==1
        with (patch.object(ProxyService,'_video_success_log_exists',return_value=False), patch.object(ProxyService,'_resolve_stored_video_route',return_value=(SimpleNamespace(id=10), 'video', 'video')), patch.object(ProxyService,'_resolve_requested_model_or_raise',return_value=SimpleNamespace()), patch('app.services.proxy_service.get_system_config',return_value=1), patch.object(ProxyService,'_log_video_request_success') as billed):
            assert ProxyService._bill_video_route_if_needed(db,db.get(SysUser,1),db.get(UserApiKey,2),video_id,'test',response_time_ms=1)
            assert billed.call_args.args[2].id==1
    ProxyService._video_task_routes.pop(video_id,None)

@pytest.mark.parametrize('creator_id,expected_key', [(1,1), (None,2), (99,None)])
def test_video_completion_real_ledger_charges_creator_or_legacy_fallback(ledger, creator_id, expected_key):
    with ledger.factory.begin() as db:
        VideoTaskBillingSnapshot.__table__.create(db.get_bind())
        db.add(UserApiKey(id=2,user_id=1,name='query',key_hash='query',key_prefix='query',total_cost=0))
    ledger.model.billing_type='request'
    ledger.model.request_price=Decimal('2')
    video_id='real-ledger-video'
    route=dict(ledger.context, user_id=1,user_api_key_id=creator_id,channel_id=70,requested_model='gpt-test',actual_model='gpt-test',billing_type='request',request_id='daily-video',billed=False)
    ProxyService._video_task_routes[video_id]=route
    try:
        with ledger.factory() as db, patch.object(ProxyService,'_video_success_log_exists',return_value=False), patch.object(ProxyService,'_resolve_stored_video_route',return_value=(SimpleNamespace(id=70,name='test-channel',protocol_type='openai'),'gpt-test','gpt-test')), patch.object(ProxyService,'_resolve_requested_model_or_raise',return_value=ledger.model):
            assert ProxyService._bill_video_route_if_needed(db,db.get(SysUser,1),db.get(UserApiKey,2),video_id,'test',response_time_ms=1)
        with ledger.factory() as db:
            record=db.query(ConsumptionRecord).one()
            assert record.total_cost == 3
            assert db.query(RequestLog).one().user_api_key_id == (creator_id or 2)
            for key_id in (1,2):
                assert db.get(UserApiKey,key_id).daily_used_usd == (3 if key_id == expected_key else 0)
    finally:
        ProxyService._video_task_routes.pop(video_id,None)
