"""HTTP contract for the privileged cache simulation administration API."""
import asyncio
from datetime import datetime
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.admin.cache_simulation import router
from app.api.admin.system import router as system_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.database import Base, get_db
from app.models.cache_simulation import CacheSimulationDecision, CacheSimulationRule
from app.models.log import SystemConfig
from app.models.model import ModelGroup
from app.models.user import SysUser
from app.services.cache_simulation_service import CacheSimulationService as Service
from app.services.cache_simulation_state_service import canonical_json


@pytest.fixture
def admin_api(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_SIMULATION_HMAC_KEY", "admin-test-key-" * 4)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[x.__table__ for x in (
        SysUser, ModelGroup, SystemConfig, CacheSimulationRule, CacheSimulationDecision)])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        for user_id, role in ((1, "admin"), (2, "user")):
            db.add(SysUser(id=user_id, username=role, role=role, email=role + "@example.test",
                           password_hash="test", status=1, token_version=1))
        db.add(ModelGroup(id=11, model_series="claude", code="claude-aws", name="AWS", enabled=1))
        db.add(ModelGroup(id=12, model_series="claude", code="disabled", name="Disabled", enabled=0))
        db.add(SystemConfig(id=1, config_key=Service.CONFIG_KEY, config_value=canonical_json(Service.DEFAULT_CONFIG), config_type="json"))
        buckets = {"input": 1000, "output": 100, "read": 9000, "creation": 0}
        usage = canonical_json({key: buckets for key in ("raw", "effective", "baseline", "billed")})
        for n, outcome, status in ((1, "simulated", "settled"), (2, "skipped", "pending")):
            db.add(CacheSimulationDecision(request_id=f"request-{n}", decision_id=f"decision-{n}",
                user_id=2, user_api_key_id=1, group_id=11, unified_model_id=7, username_snapshot="user",
                group_name_snapshot="AWS", requested_model="claude-test", protocol="anthropic", rule_id=1,
                rule_generation=1, config_version=1, enable_epoch=1, identity_source="session_id",
                identity_confidence="strong", usage_source="upstream", decision_status="prepared",
                accounting_status=status, outcome=outcome, total_tokens=10100, context_tokens=10000,
                usage_json=usage, snapshot_json='{"prices":{},"cache_info":{}}',
                created_at=datetime(2026, 10, 15, 0, n), settled_at=datetime(2026, 10, 14, 16, n),
                window_started_at=datetime(2026, 10, 14, 16), window_expires_at=datetime(2026, 10, 14, 16, 5)))
    app = FastAPI()
    app.include_router(router); app.include_router(system_router)
    register_exception_handlers(app)
    def database():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = database
    def claims(token):
        return {"sub": "1" if token == "admin" else "2", "iat": 1, "jti": "test-claim", "tv": 1}
    with (patch("app.core.dependencies.verify_token", side_effect=claims),
          patch("app.core.dependencies.AuthTokenRevocationService.is_revoked", return_value=False),
          patch("app.core.dependencies.AgentService.assert_user_matches_site", return_value=None)):
        yield app
    engine.dispose()


def test_authentication_admin_access_and_configuration_contract(admin_api):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_api), base_url="http://test") as client:
            path = "/api/admin/cache-simulation/config"
            assert (await client.get(path)).status_code == 401
            assert (await client.get(path, headers={"Authorization": "Bearer user"})).status_code == 403
            client.headers["Authorization"] = "Bearer admin"
            current = (await client.get(path)).json()["data"]
            assert current["ttl_minutes"] == 5 and not current["enabled"]
            data = {"enabled": True, "ttl_minutes": 30, "version": current["version"]}
            saved = await client.put(path, json=data)
            assert saved.status_code == 200 and saved.json()["data"]["ttl_seconds"] == 1800
            assert (await client.put(path, json=data)).status_code == 409
            for invalid in (0, 1441, 5.1, True, "5"):
                assert (await client.put(path, json={**data, "ttl_minutes": invalid})).status_code == 422
            assert (await client.put(path, json={**data, "enabled": "true"})).status_code == 422
            assert (await client.put("/api/admin/system/configs/1", json={"config_value": "{}"})).status_code == 400
    asyncio.run(run())


def test_exact_pair_rule_uniqueness_and_generation(admin_api):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_api), base_url="http://test",
                                    headers={"Authorization": "Bearer admin"}) as client:
            path = "/api/admin/cache-simulation/rules"
            assert (await client.post(path, json={"user_id": 999, "group_id": 11})).status_code == 400
            assert (await client.post(path, json={"user_id": 2, "group_id": 12})).status_code == 400
            saved = (await client.post(path, json={"user_id": 2, "group_id": 11})).json()["data"]
            assert saved["user_id"] == 2 and saved["group_id"] == 11
            assert (await client.post(path, json={"user_id": 2, "group_id": 11})).status_code == 409
            off = await client.put(f'{path}/{saved["id"]}', json={"enabled": False, "generation": 1})
            assert off.json()["data"]["generation"] == 2
            assert (await client.put(f'{path}/{saved["id"]}', json={"enabled": True, "generation": 1})).status_code == 409
            assert (await client.put(f'{path}/{saved["id"]}', json={"enabled": True, "generation": 2})).json()["data"]["generation"] == 3
            assert (await client.get(path)).json()["data"]["total"] == 1
            assert (await client.get(path, params={"page_size": 101})).status_code == 422
    asyncio.run(run())


def test_audit_defaults_filters_detail_and_time_boundaries(admin_api):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_api), base_url="http://test",
                                    headers={"Authorization": "Bearer admin"}) as client:
            path = "/api/admin/cache-simulation/records"
            result = (await client.get(path)).json()["data"]
            assert result["total"] == 1 and result["items"][0]["request_id"] == "request-1"
            all_records = {"outcome": "all", "accounting_status": "all"}
            assert (await client.get(path, params=all_records)).json()["data"]["total"] == 2
            assert (await client.get(path, params={**all_records, "user_id": 1})).json()["data"]["total"] == 0
            assert (await client.get(path, params={**all_records, "group_id": 12})).json()["data"]["total"] == 0
            assert (await client.get(path, params={**all_records, "model": "other"})).json()["data"]["total"] == 0
            result = await client.get(path, params={**all_records, "start": "2026-10-15T00:01:30+08:00", "end": "2026-10-15T00:03:00+08:00"})
            assert result.json()["data"]["total"] == 1 and result.json()["data"]["items"][0]["request_id"] == "request-2"
            assert (await client.get(path, params={"start": "2026-10-16", "end": "2026-10-15"})).status_code == 400
            assert (await client.get(path, params={"outcome": "invalid"})).status_code == 422
            detail = (await client.get(path + "/request-1")).json()["data"]
            assert set(detail["usage"]) == {"raw", "effective", "baseline", "billed"}
            assert detail["created_at"] == "2026-10-15T00:01:00+08:00"
            assert detail["settled_at"] == "2026-10-14T16:01:00Z"
            assert detail["window_started_at"] == "2026-10-14T16:00:00Z"
            assert detail["window_expires_at"] == "2026-10-14T16:05:00Z"
            assert datetime.fromisoformat(detail["created_at"]) == datetime.fromisoformat(detail["settled_at"].replace("Z", "+00:00"))
            assert (await client.get(path + "/missing")).status_code == 404
    asyncio.run(run())


@pytest.mark.parametrize("start,end", [
    ("2026-10-15T00:02:00+08:00", "2026-10-15T00:02:00+08:00"),
    ("2026-10-14T16:01:30Z", "2026-10-14T16:03:00Z"),
    ("2026-10-14T09:01:30-07:00", "2026-10-14T09:03:00-07:00"),
    ("2026-10-15T00:01:30", "2026-10-15T00:03:00"),
])
def test_record_filters_match_beijing_storage_across_timezones(admin_api, start, end):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_api), base_url="http://test",
                                    headers={"Authorization": "Bearer admin"}) as client:
            result = await client.get("/api/admin/cache-simulation/records", params={
                "outcome": "all", "accounting_status": "all", "start": start, "end": end})
            assert result.status_code == 200
            data = result.json()["data"]
            assert data["total"] == 1 and data["items"][0]["request_id"] == "request-2"
            assert data["items"][0]["created_at"] == "2026-10-15T00:02:00+08:00"
    asyncio.run(run())
