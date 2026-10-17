"""Focused contracts for agent open API permissions, pricing and payment state."""
from decimal import Decimal
from datetime import datetime, timedelta
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.responses import Response

from app.database import Base
from app.core.dependencies import OpenApiUserPrincipal, require_open_api_user_for_agent
from app.models.agent import Agent, AgentOpenApiIdempotency, AgentOpenApiKey
from app.models.payment import PaymentRechargeOrder
from app.schemas.user import ApiKeyCreateRequest, ApiKeyDailyLimitUpdate, ApiKeyGroupBindingUpdate, RegisterRequest
from app.models.user import SysUser
from app.models.model import ModelGroup
from app.services.agent_open_api_key_service import AgentOpenApiKeyService, AgentOpenApiPrincipal
from app.services.agent_open_api_service import AgentOpenApiService
from app.services.agent_service import AgentService
from app.services.agent_cash_service import AgentCashService
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService
from app.services.api_key_service import ApiKeyService
from app.services.log_service import LogService
from app.api.agent.open_v1 import open_api_create_user_api_key, open_api_register
from app.core.security import hash_secret
from app.services.payment_service import PaymentService


def test_scope_contract_rejects_unknown_scope():
    assert "user.api_key.create" in AgentOpenApiKeyService._normalize_scopes(["user.api_key.create"])
    with pytest.raises(Exception) as exc:
        AgentOpenApiKeyService._normalize_scopes(["admin.all"])
    assert getattr(exc.value, "error_code", None) == "OPEN_API_SCOPE_INVALID"


@pytest.fixture
def open_api_key_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[Agent.__table__, AgentOpenApiKey.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([
            Agent(id=7, agent_code="agent-7", agent_name="Agent 7", status="active", frontend_domain="agent.test"),
            Agent(id=8, agent_code="agent-8", agent_name="Agent 8", status="active", frontend_domain="other.test"),
        ])
    monkeypatch.setattr(AgentOpenApiKeyService, "_audit", staticmethod(lambda *args, **kwargs: None))
    yield factory
    engine.dispose()


def test_open_api_key_lifecycle_hashes_secret_and_revokes_immediately(open_api_key_db):
    actor = SimpleNamespace(id=99, username="agent-admin")
    with open_api_key_db() as db:
        created = AgentOpenApiKeyService.create_key(db, actor, 7, "desktop", ["auth.login"], expires_in_days=30)
        raw_key = created["key"]
        assert raw_key.startswith("agk_")
        row = db.query(AgentOpenApiKey).filter_by(id=created["id"]).one()
        assert row.key_hash == hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        assert raw_key not in row.key_hash
        listed = AgentOpenApiKeyService.list_keys(db, 7)
        assert "key" not in listed[0]
        principal = AgentOpenApiKeyService.authenticate(db, raw_key)
        assert (principal.agent_id, principal.key_id, principal.scopes) == (7, created["id"], ("auth.login",))
        AgentOpenApiKeyService.revoke_key(db, actor, 7, created["id"])
        with pytest.raises(Exception) as exc:
            AgentOpenApiKeyService.authenticate(db, raw_key)
        assert getattr(exc.value, "error_code", None) == "OPEN_API_KEY_INVALID"


def test_open_api_key_admin_operations_are_tenant_scoped(open_api_key_db):
    actor = SimpleNamespace(id=99, username="agent-admin")
    with open_api_key_db() as db:
        created = AgentOpenApiKeyService.create_key(db, actor, 7, "desktop", ["auth.login"])
        with pytest.raises(Exception) as exc:
            AgentOpenApiKeyService.update_scopes(db, actor, 8, created["id"], ["agent.request_detail"])
        assert getattr(exc.value, "error_code", None) == "OPEN_API_KEY_NOT_FOUND"
        row = db.query(AgentOpenApiKey).filter_by(id=created["id"]).one()
        assert AgentOpenApiKeyService._decode_scopes(row.scopes_json) == ("auth.login",)


def test_open_api_key_expiry_and_agent_deactivation_invalidate_key(open_api_key_db):
    actor = SimpleNamespace(id=99, username="agent-admin")
    with open_api_key_db() as db:
        created = AgentOpenApiKeyService.create_key(db, actor, 7, "desktop", ["auth.login"])
        row = db.query(AgentOpenApiKey).filter_by(id=created["id"]).one()
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        with pytest.raises(Exception) as exc:
            AgentOpenApiKeyService.authenticate(db, created["key"])
        assert getattr(exc.value, "error_code", None) == "OPEN_API_KEY_EXPIRED"

        active_key = AgentOpenApiKeyService.create_key(db, actor, 7, "desktop-2", ["auth.login"])
        db.query(Agent).filter_by(id=7).update({"status": "inactive"})
        db.commit()
        with pytest.raises(Exception) as exc:
            AgentOpenApiKeyService.authenticate(db, active_key["key"])
        assert getattr(exc.value, "error_code", None) == "AGENT_UNAVAILABLE"


def test_open_api_user_principal_is_bound_to_key_agent(open_api_key_db):
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=3, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    user = OpenApiUserPrincipal(user_id=11, agent_id=7, role="user", username="alice", token_version=0)
    assert require_open_api_user_for_agent(user, principal) is user
    with pytest.raises(Exception) as exc:
        require_open_api_user_for_agent(
            OpenApiUserPrincipal(user_id=12, agent_id=8, role="user", username="bob", token_version=0),
            principal,
        )
    assert getattr(exc.value, "error_code", None) == "AGENT_SITE_MISMATCH"


def test_open_api_login_rejects_valid_credentials_for_another_agent(monkeypatch):
    user = SimpleNamespace(
        id=12, username="bob", email="bob@example.test", password_hash="stored",
        status=1, role="user", agent_id=8, last_login_at=None, last_login_ip=None, token_version=0,
    )

    class Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return user

    class Db:
        committed = False

        def query(self, *_args, **_kwargs):
            return Query()

        def commit(self):
            self.committed = True

    db = Db()
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda *_: True)
    with pytest.raises(Exception) as exc:
        AuthService.login(db, "bob", "valid-password", trusted_agent_id=7, request_host="spoofed.example")
    assert getattr(exc.value, "error_code", None) == "AUTH_FAILED"
    assert db.committed is False
    assert user.last_login_at is None


def test_open_api_site_context_uses_saved_agent_domain(open_api_key_db):
    with open_api_key_db() as db:
        context = AgentService.get_open_api_site_context(db, 7, require_register=True)
        assert context.host == "agent.test"
        assert context.resolved_from == "agent_open_api_key"


def test_register_code_storage_is_agent_scoped_and_one_time(monkeypatch):
    from app.config import settings

    email = "alice@example.test"
    code = "123456"
    cache_key_7 = EmailVerificationService._cache_key(email, "register", 7)
    cache_key_8 = EmailVerificationService._cache_key(email, "register", 8)
    assert cache_key_7 != cache_key_8
    memory = {
        cache_key_7: (
            '{"hash":"' + hash_secret(code, salt=email) + '","expires_at":9999999999}',
            9999999999,
        ),
    }
    monkeypatch.setattr(settings, "EMAIL_VERIFICATION_REQUIRED", True)
    monkeypatch.setattr("app.services.email_verification_service.redis_client.get", lambda _key: None)
    monkeypatch.setattr(EmailVerificationService, "_memory_codes", memory)
    with pytest.raises(Exception) as exc:
        EmailVerificationService.verify_code(email, code, purpose="register", agent_id=8)
    assert getattr(exc.value, "error_code", None) == "EMAIL_CODE_INVALID"
    EmailVerificationService.verify_code(email, code, purpose="register", agent_id=7)
    with pytest.raises(Exception) as exc:
        EmailVerificationService.verify_code(email, code, purpose="register", agent_id=7)
    assert getattr(exc.value, "error_code", None) == "EMAIL_CODE_INVALID"


def test_open_api_register_uses_key_agent_not_request_site_headers(monkeypatch, open_api_key_db):
    from starlette.requests import Request

    principal = AgentOpenApiPrincipal(agent_id=7, key_id=3, key_prefix="agk_test", scopes=("auth.register",), frontend_domain="agent.test")
    captured = {}

    def register(*args, **kwargs):
        captured.update(kwargs)
        return {"token": "jwt", "user": {"agent_id": 7}}

    monkeypatch.setattr(AuthService, "register", register)
    monkeypatch.setattr("app.api.agent.open_v1._rate_limit", lambda *args, **kwargs: None)
    request = Request({
        "type": "http", "method": "POST", "path": "/auth/register", "headers": [
            (b"x-site-host", b"other.test"), (b"origin", b"https://other.test"),
            (b"referer", b"https://other.test/register"),
        ], "client": ("127.0.0.1", 12345), "server": ("api.test", 443),
        "scheme": "https", "query_string": b"",
    })
    data = RegisterRequest(username="alice", email="alice@example.com", password="password123", email_code="123456")
    response = Response()
    result = open_api_register(data, request, response, db=MagicMock(), principal=principal)
    assert captured["trusted_agent_id"] == 7
    assert "request_host" not in captured and "x_site_host" not in captured
    assert result.data["user"]["agent_id"] == 7
    assert response.headers["Cache-Control"] == "no-store"


def test_open_api_user_key_create_checks_scope_and_uses_verified_user(monkeypatch):
    from app.core.exceptions import ServiceException

    db = MagicMock()
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=3, key_prefix="agk_test", scopes=("user.api_key.create",), frontend_domain="agent.test")
    user = OpenApiUserPrincipal(user_id=11, agent_id=7, role="user", username="alice", token_version=0)
    data = ApiKeyCreateRequest(name="desktop", group_mode="special", group_model_series="gpt", group_id=12)
    captured = {}

    def create_api_key(*args):
        captured["args"] = args
        return {"id": 5, "key": "sk-once"}

    monkeypatch.setattr(ApiKeyService, "create_api_key", create_api_key)
    response = Response()
    result = open_api_create_user_api_key(data, response, db, principal, user)
    assert captured["args"][1:] == (11, "desktop", "special", "gpt", 12, None)
    assert result.data["key"] == "sk-once"
    assert response.headers["Cache-Control"] == "no-store"

    denied_principal = AgentOpenApiPrincipal(agent_id=7, key_id=3, key_prefix="agk_test", scopes=("auth.login",), frontend_domain="agent.test")
    with pytest.raises(ServiceException) as exc:
        open_api_create_user_api_key(data, Response(), db, denied_principal, user)
    assert exc.value.error_code == "OPEN_API_SCOPE_REQUIRED"


def test_model_key_special_group_is_revalidated_against_series_and_enabled_state():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[ModelGroup.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([
            ModelGroup(id=12, model_series="gpt", code="gpt-main", name="GPT", multiplier=1, enabled=1),
            ModelGroup(id=13, model_series="gpt", code="gpt-off", name="Disabled", multiplier=1, enabled=0),
        ])
    try:
        with factory() as db:
            binding = ApiKeyService._normalize_binding(db, "special", "gpt", 12)
            assert binding[:3] == ("special", "gpt", 12)
            with pytest.raises(Exception) as exc:
                ApiKeyService._normalize_binding(db, "special", "claude", 12)
            assert getattr(exc.value, "error_code", None) == "MODEL_GROUP_SERIES_MISMATCH"
            with pytest.raises(Exception) as exc:
                ApiKeyService._normalize_binding(db, "special", "gpt", 13)
            assert getattr(exc.value, "error_code", None) == "MODEL_GROUP_DISABLED"
    finally:
        engine.dispose()


def test_open_api_read_wrappers_force_tenant_filter(monkeypatch):
    db = MagicMock()
    list_orders = MagicMock(return_value=([], 0))
    monkeypatch.setattr(AgentCashService, "list_recharge_orders", list_orders)
    assert AgentCashService.list_agent_open_api_recharge_orders(db, agent_id=7) == ([], 0)
    assert list_orders.call_args.kwargs["agent_id"] == 7

    list_logs = MagicMock(return_value=([{"request_id": "request-7"}], 1))
    monkeypatch.setattr(LogService, "list_request_logs", list_logs)
    monkeypatch.setattr(LogService, "build_agent_visible_request_log_items", lambda items: items)
    assert LogService.get_agent_request_detail(db, "request-7", 7) == {"request_id": "request-7"}
    assert list_logs.call_args.kwargs["agent_id"] == 7
    assert list_logs.call_args.kwargs["request_id"] == "request-7"


def test_user_api_key_group_schema_matches_page_payload_and_rejects_unified_overrides():
    assert ApiKeyCreateRequest.model_validate({
        "name": "desktop",
        "group_mode": "unified",
        "group_model_series": None,
        "group_id": None,
    }).group_mode == "unified"
    assert ApiKeyCreateRequest.model_validate({
        "name": "desktop",
        "group_mode": "special",
        "group_model_series": "openai",
        "group_id": 12,
    }).group_id == 12
    with pytest.raises(Exception):
        ApiKeyCreateRequest.model_validate({"name": "desktop", "group_mode": "unified", "group_id": 12})
    with pytest.raises(Exception):
        ApiKeyCreateRequest.model_validate({"name": "desktop", "group_mode": "special", "group_model_series": "openai"})
    assert ApiKeyCreateRequest.model_validate({"name": "desktop", "daily_limit_usd": None}).daily_limit_usd is None
    assert ApiKeyDailyLimitUpdate.model_validate({"daily_limit_usd": None}).daily_limit_usd is None
    with pytest.raises(Exception):
        ApiKeyGroupBindingUpdate.model_validate({"group_mode": "unified", "group_id": 12})


@pytest.mark.parametrize("code,expected", [("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5), ("f", 6), ("g", 7)])
def test_recharge_rate_codes_represent_usd_per_cny(code, expected):
    assert AgentOpenApiService._check_rate_code(code, Decimal("7"), True) == Decimal(expected)


def test_recharge_rate_permission_and_settlement_cap():
    with pytest.raises(Exception) as exc:
        AgentOpenApiService._check_rate_code("a", Decimal("7"), False)
    assert getattr(exc.value, "error_code", None) == "AGENT_CUSTOM_RECHARGE_RATE_DISABLED"
    with pytest.raises(Exception) as exc:
        AgentOpenApiService._check_rate_code("g", Decimal("5"), True)
    assert getattr(exc.value, "error_code", None) == "AGENT_CUSTOM_RECHARGE_RATE_EXCEEDS_SETTLEMENT"


def test_open_api_recharge_pricing_uses_user_rate_and_agent_settlement_snapshot():
    credited_usd, image_credits, settlement_rate, profit_cny = PaymentService._calculate_amounts(
        Decimal("100.00"),
        agent_id=7,
        recharge_type="balance",
        user_recharge_rate=Decimal("1"),
        agent_settlement_rate=Decimal("7"),
    )
    assert credited_usd == Decimal("100.000000")
    assert image_credits == Decimal("0.000")
    assert settlement_rate == Decimal("7")
    assert profit_cny == Decimal("85.71")


def test_alipay_success_payload_requires_matching_amount_and_order(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ALIPAY_APP_ID", "test-app")
    order = SimpleNamespace(
        order_no="order-1", payment_channel="alipay", amount_cny=Decimal("10.00"),
        alipay_trade_no=None, buyer_logon_id=None, buyer_user_id=None,
    )
    with pytest.raises(Exception) as exc:
        PaymentService._validate_paid_payload(MagicMock(), order, {
            "app_id": "test-app", "out_trade_no": "order-1", "trade_status": "TRADE_SUCCESS",
        }, "notify")
    assert getattr(exc.value, "error_code", None) == "ALIPAY_AMOUNT_MISSING"

    with pytest.raises(Exception) as exc:
        PaymentService._validate_paid_payload(MagicMock(), order, {
            "app_id": "test-app", "out_trade_no": "order-1", "trade_status": "TRADE_SUCCESS", "total_amount": "9.99",
        }, "notify")
    assert getattr(exc.value, "error_code", None) == "ALIPAY_AMOUNT_MISMATCH"

    with pytest.raises(Exception) as exc:
        PaymentService._validate_paid_payload(MagicMock(), order, {
            "out_trade_no": "order-1", "trade_status": "TRADE_SUCCESS", "total_amount": "10.00",
        }, "notify")
    assert getattr(exc.value, "error_code", None) == "ALIPAY_APP_ID_MISMATCH"

    with pytest.raises(Exception) as exc:
        PaymentService._validate_paid_payload(MagicMock(), order, {
            "app_id": "test-app", "out_trade_no": "other-order", "trade_status": "TRADE_SUCCESS", "total_amount": "10.00",
        }, "notify")
    assert getattr(exc.value, "error_code", None) == "ALIPAY_ORDER_NO_MISMATCH"

    accepted = PaymentService._validate_paid_payload(MagicMock(), order, {
        "app_id": "test-app", "out_trade_no": "order-1", "trade_status": "TRADE_SUCCESS", "total_amount": "10.00",
    }, "notify")
    assert accepted["trade_status"] == "TRADE_SUCCESS"


def test_closed_order_can_be_upgraded_to_paid_with_settlement_lock(monkeypatch):
    order = SimpleNamespace(
        id=1,
        order_no="order-closed",
        status="closed",
        payment_channel="alipay",
        trade_status="TRADE_CLOSED",
        alipay_trade_no=None,
        buyer_logon_id=None,
        buyer_user_id=None,
        wechat_transaction_id=None,
        paid_at=None,
        notify_raw=None,
        return_raw=None,
    )
    db = MagicMock()
    monkeypatch.setattr(PaymentService, "_get_order_for_update", lambda *_: order)
    monkeypatch.setattr(PaymentService, "_validate_paid_payload", lambda *_: {
        "trade_status": "TRADE_SUCCESS", "alipay_trade_no": "provider-1",
        "buyer_logon_id": "", "buyer_user_id": "",
    })
    monkeypatch.setattr(PaymentService, "_claim_recharge_settlement", lambda *_: None)
    monkeypatch.setattr(PaymentService, "serialize_order", lambda row: {"order_no": row.order_no, "status": row.status})

    result = PaymentService._apply_paid_order(db, order.order_no, {}, source="query")

    assert order.status == "paid"
    assert result == {"order_no": "order-closed", "status": "paid"}
    db.commit.assert_called_once()


def test_closed_wechat_order_is_not_replaced_without_provider_confirmation(monkeypatch):
    order = SimpleNamespace(
        order_no="wechat-closed", payment_channel="wechat", status="closed", wechat_code_url=None,
    )
    states = iter([{"trade_state": "USERPAYING"}, {"trade_state": "USERPAYING"}])
    query = MagicMock(side_effect=lambda *_: next(states))
    close = MagicMock(return_value=True)
    monkeypatch.setattr(PaymentService, "query_wechat_order", query)
    monkeypatch.setattr(PaymentService, "close_wechat_order", close)

    with pytest.raises(Exception) as exc:
        AgentOpenApiService._recover_existing_order(order, allow_reserved_order_replacement=True)

    assert getattr(exc.value, "error_code", None) == "WECHAT_CLOSE_UNCERTAIN"
    assert query.call_count == 2
    close.assert_called_once_with("wechat-closed")


def test_closed_wechat_order_replacement_requires_confirmed_provider_state(monkeypatch):
    order = SimpleNamespace(
        order_no="wechat-closed", payment_channel="wechat", status="closed", wechat_code_url=None,
    )
    monkeypatch.setattr(PaymentService, "query_wechat_order", lambda *_: {"trade_state": "CLOSED"})
    result = AgentOpenApiService._recover_existing_order(order, allow_reserved_order_replacement=True)
    assert result == {"_replace_reserved_order": True}

    with pytest.raises(Exception) as exc:
        AgentOpenApiService._replace_reserved_order_no(1, 2, "hash", "wechat-closed", provider_closed_confirmed=False)
    assert getattr(exc.value, "error_code", None) == "WECHAT_CLOSE_UNCERTAIN"


@pytest.fixture
def idempotency_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[
        Agent.__table__,
        SysUser.__table__,
        PaymentRechargeOrder.__table__,
        AgentOpenApiIdempotency.__table__,
    ])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add(Agent(id=7, agent_code="agent-7", agent_name="Agent 7", status="active", frontend_domain="agent.test"))
        db.add(SysUser(id=11, username="alice", email="alice@example.test", password_hash="test", role="user", agent_id=7, status=1))
    monkeypatch.setattr("app.services.agent_open_api_service.SessionLocal", factory)
    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.agent_open_api_service.AgentService.get_open_api_site_context", lambda *args, **kwargs: SimpleNamespace(host="agent.test"))
    monkeypatch.setattr("app.services.agent_open_api_service.AgentService.resolve_user_recharge_policy", lambda *args, **kwargs: SimpleNamespace(
        online_recharge_enabled=True,
        balance_agent_settlement_rate=Decimal("7"),
        custom_recharge_rate_enabled=True,
    ))
    monkeypatch.setattr(PaymentService, "_generate_order_no", lambda _channel: "reserved-order-1")
    monkeypatch.setattr(AgentOpenApiService, "_provision_order", lambda **kwargs: {"order_no": kwargs["order_no"], "status": "pending"})
    yield factory
    engine.dispose()


def test_same_idempotency_key_cannot_change_recharge_parameters(idempotency_db):
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    AgentOpenApiService.create_recharge_order(
        principal=principal,
        user_id=11,
        amount_cny=Decimal("20.00"),
        payment_channel="alipay",
        recharge_rate_code="a",
        idempotency_key="desktop-0001",
        request_ip="127.0.0.1",
    )
    with pytest.raises(Exception) as exc:
        AgentOpenApiService.create_recharge_order(
            principal=principal,
            user_id=11,
            amount_cny=Decimal("21.00"),
            payment_channel="alipay",
            recharge_rate_code="a",
            idempotency_key="desktop-0001",
            request_ip="127.0.0.1",
        )
    assert getattr(exc.value, "error_code", None) == "IDEMPOTENCY_CONFLICT"


def test_in_progress_idempotency_response_includes_retry_after(idempotency_db):
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    AgentOpenApiService.create_recharge_order(
        principal=principal,
        user_id=11,
        amount_cny=Decimal("20.00"),
        payment_channel="alipay",
        recharge_rate_code="a",
        idempotency_key="desktop-0002",
        request_ip="127.0.0.1",
    )
    with idempotency_db() as db:
        reservation = db.query(AgentOpenApiIdempotency).filter_by(key_id=21, user_id=11).one()
        reservation.status = "provisioning"
        reservation.lease_until = datetime.utcnow() + timedelta(seconds=45)
        db.commit()

    with pytest.raises(Exception) as exc:
        AgentOpenApiService.create_recharge_order(
            principal=principal,
            user_id=11,
            amount_cny=Decimal("20.00"),
            payment_channel="alipay",
            recharge_rate_code="a",
            idempotency_key="desktop-0002",
            request_ip="127.0.0.1",
        )

    assert getattr(exc.value, "error_code", None) == "IDEMPOTENCY_IN_PROGRESS"
    assert 1 <= int(exc.value.headers["Retry-After"]) <= 45


def test_failed_reservation_retries_using_saved_business_snapshot(idempotency_db, monkeypatch):
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    attempts = []
    order_numbers = iter(["reserved-first", "reserved-retry"])
    monkeypatch.setattr(PaymentService, "_generate_order_no", lambda _channel: next(order_numbers))

    def provision(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("simulated failure before local order persistence")
        return {"order_no": kwargs["order_no"], "status": "pending"}

    monkeypatch.setattr(AgentOpenApiService, "_provision_order", provision)
    arguments = {
        "principal": principal,
        "user_id": 11,
        "amount_cny": Decimal("20.00"),
        "payment_channel": "alipay",
        "recharge_rate_code": "a",
        "idempotency_key": "desktop-retry-1",
        "request_ip": "127.0.0.1",
    }

    with pytest.raises(RuntimeError):
        AgentOpenApiService.create_recharge_order(**arguments)

    with idempotency_db() as db:
        reservation = db.query(AgentOpenApiIdempotency).filter_by(key_id=21, user_id=11).one()
        assert reservation.status == "retryable_failed"
        assert reservation.order_no == "reserved-first"
        saved_snapshot = reservation.request_json

    response = AgentOpenApiService.create_recharge_order(**arguments)

    assert response["order_no"] == "reserved-retry"
    assert attempts[0]["request_document"] == attempts[1]["request_document"]
    assert attempts[0]["request_document"]["user_recharge_rate"] == "1"
    with idempotency_db() as db:
        reservation = db.query(AgentOpenApiIdempotency).filter_by(key_id=21, user_id=11).one()
        assert reservation.request_json == saved_snapshot
        assert reservation.status == "ready"


def test_failure_after_local_order_persisted_keeps_reservation_recoverable(idempotency_db):
    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    with idempotency_db.begin() as db:
        reservation = AgentOpenApiIdempotency(
            agent_id=7,
            key_id=21,
            user_id=11,
            idempotency_hash=AgentOpenApiService._sha256("desktop-crash-1"),
            request_fingerprint="fingerprint",
            request_json='{"amount_cny":"20.00","payment_channel":"alipay","recharge_rate_code":"e","user_recharge_rate":"5","agent_settlement_rate":"7"}',
            user_recharge_rate_code="e",
            user_recharge_rate=Decimal("5"),
            agent_settlement_rate=Decimal("7"),
            order_no="persisted-before-provider",
            status="provisioning",
            lease_until=datetime.utcnow() + timedelta(minutes=10),
            attempts=1,
        )
        order = PaymentRechargeOrder(
            id=9101,
            order_no="persisted-before-provider",
            payment_channel="alipay",
            recharge_type="balance",
            user_id=11,
            agent_id=7,
            site_scope="agent",
            amount_cny=Decimal("20"),
            credited_usd=Decimal("100"),
            user_recharge_rate=Decimal("5"),
            user_recharge_rate_code="e",
            agent_settlement_rate=Decimal("7"),
            agent_income_cny=Decimal("2.86"),
            status="pending",
            subject="recharge",
        )
        db.add_all([reservation, order])

    AgentOpenApiService._mark_reservation_failure(
        principal.key_id,
        11,
        AgentOpenApiService._sha256("desktop-crash-1"),
        "persisted-before-provider",
    )

    with idempotency_db() as db:
        reservation = db.query(AgentOpenApiIdempotency).one()
        assert reservation.status == "provisioning"
        assert reservation.order_no == "persisted-before-provider"
        assert reservation.lease_until > datetime.utcnow()
        assert db.query(PaymentRechargeOrder).filter_by(order_no=reservation.order_no).one().status == "pending"


def test_wait_deadline_prevents_new_provider_calls(monkeypatch):
    import asyncio

    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    calls = []
    async def run_provider_call(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("provider/local work must not start after the wait deadline")

    monkeypatch.setattr(AgentOpenApiService, "WAIT_SECONDS", 0)
    monkeypatch.setattr(AgentOpenApiService, "_run_provider_call", run_provider_call)
    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", lambda *args, **kwargs: None)
    result = asyncio.run(AgentOpenApiService.wait_for_recharge(
        principal=principal, user_id=11, order_no="order-1", request_ip="127.0.0.1",
    ))

    assert result == {
        "wait_result": "wait_timeout", "close_result": "not_attempted",
        "order_status": "pending", "order_no": "order-1",
    }
    assert calls == []


def test_wait_rate_limit_runs_off_the_async_event_loop(monkeypatch):
    import asyncio
    import threading

    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    event_loop_thread = threading.get_ident()
    limiter_threads = []

    def check(*_args, **_kwargs):
        limiter_threads.append(threading.get_ident())

    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", check)
    deadline = time.monotonic() + 2
    asyncio.run(AgentOpenApiService._check_wait_rate_limit("test-key", deadline=deadline))

    assert limiter_threads
    assert limiter_threads[0] != event_loop_thread


def test_wait_rate_limit_propagates_limiter_rejection(monkeypatch):
    import asyncio
    from app.core.exceptions import ServiceException

    def reject(*_args, **_kwargs):
        raise ServiceException(429, "limited", "RATE_LIMITED")

    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", reject)
    with pytest.raises(ServiceException) as exc:
        asyncio.run(AgentOpenApiService._check_wait_rate_limit(
            "test-key", deadline=time.monotonic() + 2,
        ))

    assert exc.value.error_code == "RATE_LIMITED"


def test_wait_returns_paid_and_updated_balance(monkeypatch):
    import asyncio

    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    paid_order = {"order_no": "order-1", "status": "paid", "paid_at": "2026-10-18T00:00:00"}
    monkeypatch.setattr(AgentOpenApiService, "_read_wait_order", staticmethod(lambda *_: paid_order))
    monkeypatch.setattr(AgentOpenApiService, "_read_balance", staticmethod(lambda *_: 18.25))
    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", lambda *args, **kwargs: None)

    async def run(function, *args, **kwargs):
        return function(*args)

    monkeypatch.setattr(AgentOpenApiService, "_run_provider_call", run)
    result = asyncio.run(AgentOpenApiService.wait_for_recharge(
        principal=principal, user_id=11, order_no="order-1", request_ip="127.0.0.1",
    ))

    assert result == {
        "wait_result": "paid", "close_result": "not_attempted", "order_status": "paid",
        "order_no": "order-1", "paid_at": "2026-10-18T00:00:00", "balance": 18.25,
    }


def test_paid_wait_result_keeps_paid_status_if_balance_misses_response_budget():
    import asyncio

    paid_order = {"order_no": "order-1", "status": "paid", "paid_at": "2026-10-18T00:00:00"}
    result = asyncio.run(AgentOpenApiService._paid_wait_result(
        paid_order,
        user_id=11,
        deadline=AgentOpenApiService.WAIT_RESPONSE_BUDGET_SECONDS,
    ))

    assert result["wait_result"] == "paid"
    assert result["order_status"] == "paid"
    assert result["balance"] is None


def test_wait_closes_only_after_provider_confirms_terminal_state(monkeypatch):
    import asyncio

    principal = AgentOpenApiPrincipal(agent_id=7, key_id=21, key_prefix="agk_test", scopes=("user.recharge",), frontend_domain="agent.test")
    pending_order = {"order_no": "order-1", "status": "pending", "payment_channel": "wechat"}
    monkeypatch.setattr(AgentOpenApiService, "_read_wait_order", staticmethod(lambda *_: pending_order))
    monkeypatch.setattr(AgentOpenApiService, "WAIT_CLOSE_TRIGGER_SECONDS", 120)
    monkeypatch.setattr("app.services.agent_open_api_service.AuthRateLimitService.check", lambda *args, **kwargs: None)
    provider_calls = []

    async def run(function, *args, **kwargs):
        provider_calls.append(function.__name__)
        if function.__name__ == "_close_order":
            return True, {"order_no": "order-1", "status": "closed"}
        return function(*args)

    monkeypatch.setattr(AgentOpenApiService, "_run_provider_call", run)
    result = asyncio.run(AgentOpenApiService.wait_for_recharge(
        principal=principal, user_id=11, order_no="order-1", request_ip="127.0.0.1",
    ))

    assert result == {
        "wait_result": "closed", "close_result": "confirmed",
        "order_status": "closed", "order_no": "order-1",
    }
    assert provider_calls == ["<lambda>", "_close_order"]
