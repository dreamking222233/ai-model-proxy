"""Agent-owned open API key lifecycle and tenant authentication."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.agent import Agent, AgentOpenApiKey
from app.models.user import SysUser
from app.services.log_service import LogService


@dataclass(frozen=True)
class AgentOpenApiPrincipal:
    agent_id: int
    key_id: int
    key_prefix: str
    scopes: tuple[str, ...]
    frontend_domain: str | None


class AgentOpenApiKeyService:
    """Issue hashed agent API keys and validate their tenant-bound scopes."""

    SCOPES = frozenset({
        "auth.register",
        "auth.login",
        "user.recharge",
        "user.api_key.create",
        "agent.request_detail",
        "agent.recharge_records",
    })
    MAX_ACTIVE_KEYS = 20
    DEFAULT_EXPIRES_DAYS = 90

    @classmethod
    def _normalize_scopes(cls, scopes) -> list[str]:
        if not isinstance(scopes, (list, tuple)) or not scopes:
            raise ServiceException(400, "至少需要选择一个接口权限", "OPEN_API_SCOPES_REQUIRED")
        normalized = sorted({str(item or "").strip() for item in scopes})
        invalid = [item for item in normalized if item not in cls.SCOPES]
        if invalid:
            raise ServiceException(400, "包含不支持的接口权限", "OPEN_API_SCOPE_INVALID")
        return normalized

    @staticmethod
    def _decode_scopes(raw: str | None) -> tuple[str, ...]:
        try:
            value = json.loads(raw or "[]")
        except (TypeError, ValueError):
            raise ServiceException(401, "API Key 配置无效", "OPEN_API_KEY_INVALID")
        if not isinstance(value, list):
            raise ServiceException(401, "API Key 配置无效", "OPEN_API_KEY_INVALID")
        return tuple(sorted({str(item) for item in value}))

    @staticmethod
    def _safe_payload(key: AgentOpenApiKey) -> dict:
        return {
            "id": int(key.id),
            "name": key.name,
            "key_prefix": key.key_prefix,
            "scopes": list(AgentOpenApiKeyService._decode_scopes(key.scopes_json)),
            "status": key.status,
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
            "created_at": key.created_at.isoformat() if key.created_at else None,
        }

    @staticmethod
    def _audit(db: Session, operator: SysUser, agent_id: int, action: str, key: AgentOpenApiKey) -> None:
        LogService.create_operation_log(
            db,
            int(operator.id),
            str(operator.username),
            action,
            target_type="agent_open_api_key",
            target_id=int(key.id),
            description=json.dumps(
                {"key_prefix": key.key_prefix, "scopes": AgentOpenApiKeyService._decode_scopes(key.scopes_json)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            agent_id=agent_id,
            auto_commit=False,
        )

    @classmethod
    def list_keys(cls, db: Session, agent_id: int) -> list[dict]:
        rows = (
            db.query(AgentOpenApiKey)
            .filter(AgentOpenApiKey.agent_id == int(agent_id))
            .order_by(AgentOpenApiKey.created_at.desc(), AgentOpenApiKey.id.desc())
            .all()
        )
        return [cls._safe_payload(row) for row in rows]

    @classmethod
    def create_key(
        cls,
        db: Session,
        operator: SysUser,
        agent_id: int,
        name: str,
        scopes,
        expires_in_days: int | None = None,
    ) -> dict:
        normalized_name = str(name or "").strip()
        if not normalized_name or len(normalized_name) > 128:
            raise ServiceException(400, "API Key 名称长度应为 1–128 个字符", "OPEN_API_KEY_NAME_INVALID")
        normalized_scopes = cls._normalize_scopes(scopes)
        days = cls.DEFAULT_EXPIRES_DAYS if expires_in_days is None else int(expires_in_days)
        if days < 1 or days > 365:
            raise ServiceException(400, "API Key 有效期必须为 1–365 天", "OPEN_API_KEY_EXPIRY_INVALID")

        # Locking the tenant row serializes concurrent key creation for the 20-key cap.
        agent = (
            db.query(Agent)
            .filter(Agent.id == int(agent_id))
            .with_for_update()
            .first()
        )
        if agent is None or agent.status != "active":
            raise ServiceException(403, "代理已停用或不存在", "AGENT_UNAVAILABLE")
        now = datetime.utcnow()
        active_count = (
            db.query(AgentOpenApiKey.id)
            .filter(
                AgentOpenApiKey.agent_id == int(agent_id),
                AgentOpenApiKey.status == "active",
                AgentOpenApiKey.expires_at > now,
            )
            .count()
        )
        if active_count >= cls.MAX_ACTIVE_KEYS:
            raise ServiceException(400, "代理开放 API Key 数量已达上限", "OPEN_API_KEY_LIMIT_REACHED")

        raw_key = "agk_" + secrets.token_urlsafe(32)
        key = AgentOpenApiKey(
            agent_id=int(agent_id),
            name=normalized_name,
            key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            key_prefix=raw_key[:16],
            scopes_json=json.dumps(normalized_scopes, ensure_ascii=False, separators=(",", ":")),
            status="active",
            created_by_user_id=int(operator.id),
            expires_at=now + timedelta(days=days),
        )
        db.add(key)
        db.flush()
        cls._audit(db, operator, int(agent_id), "agent_open_api_key.create", key)
        db.commit()
        db.refresh(key)
        return {**cls._safe_payload(key), "key": raw_key}

    @classmethod
    def authenticate(cls, db: Session, raw_key: str | None, required_scope: str | None = None) -> AgentOpenApiPrincipal:
        candidate = str(raw_key or "").strip()
        if not candidate.startswith("agk_") or len(candidate) < 40 or len(candidate) > 128:
            raise ServiceException(401, "API Key 无效", "OPEN_API_KEY_INVALID")
        key_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        row = db.query(AgentOpenApiKey).filter(AgentOpenApiKey.key_hash == key_hash).first()
        if row is None or row.status != "active":
            raise ServiceException(401, "API Key 无效或已撤销", "OPEN_API_KEY_INVALID")
        now = datetime.utcnow()
        if row.expires_at is None or row.expires_at <= now:
            raise ServiceException(401, "API Key 已过期", "OPEN_API_KEY_EXPIRED")
        agent = db.query(Agent).filter(Agent.id == row.agent_id).first()
        if agent is None or agent.status != "active":
            raise ServiceException(403, "代理已停用", "AGENT_UNAVAILABLE")
        scopes = cls._decode_scopes(row.scopes_json)
        if required_scope and required_scope not in scopes:
            raise ServiceException(403, "API Key 未开通此接口权限", "OPEN_API_SCOPE_REQUIRED")
        if not row.last_used_at or row.last_used_at <= now - timedelta(minutes=5):
            row.last_used_at = now
            db.commit()
        return AgentOpenApiPrincipal(
            agent_id=int(row.agent_id),
            key_id=int(row.id),
            key_prefix=row.key_prefix,
            scopes=scopes,
            frontend_domain=agent.frontend_domain,
        )

    @classmethod
    def update_scopes(cls, db: Session, operator: SysUser, agent_id: int, key_id: int, scopes) -> dict:
        normalized_scopes = cls._normalize_scopes(scopes)
        row = (
            db.query(AgentOpenApiKey)
            .filter(AgentOpenApiKey.id == int(key_id), AgentOpenApiKey.agent_id == int(agent_id))
            .with_for_update()
            .first()
        )
        if row is None:
            raise ServiceException(404, "API Key 不存在", "OPEN_API_KEY_NOT_FOUND")
        if row.status != "active" or row.expires_at <= datetime.utcnow():
            raise ServiceException(400, "已失效的 API Key 不能修改权限", "OPEN_API_KEY_INACTIVE")
        row.scopes_json = json.dumps(normalized_scopes, ensure_ascii=False, separators=(",", ":"))
        cls._audit(db, operator, int(agent_id), "agent_open_api_key.update_scopes", row)
        db.commit()
        db.refresh(row)
        return cls._safe_payload(row)

    @classmethod
    def revoke_key(cls, db: Session, operator: SysUser, agent_id: int, key_id: int) -> None:
        row = (
            db.query(AgentOpenApiKey)
            .filter(AgentOpenApiKey.id == int(key_id), AgentOpenApiKey.agent_id == int(agent_id))
            .with_for_update()
            .first()
        )
        if row is None:
            raise ServiceException(404, "API Key 不存在", "OPEN_API_KEY_NOT_FOUND")
        if row.status == "active":
            row.status = "revoked"
            row.revoked_at = datetime.utcnow()
            cls._audit(db, operator, int(agent_id), "agent_open_api_key.revoke", row)
            db.commit()
