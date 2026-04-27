"""Agent tenant resolution and site configuration service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent import Agent, AgentBalance, AgentImageBalance
from app.models.agent import AgentSubscriptionInventory
from app.models.log import SystemConfig
from app.models.user import SysUser
from app.models.log import SubscriptionPlan
from app.core.exceptions import ServiceException
from app.core.security import hash_password


@dataclass
class AgentSiteContext:
    """Resolved site context for the current request host."""

    host: str
    site_scope: str
    is_api_host: bool
    agent: Optional[Agent] = None
    request_host: str = ""
    resolved_from: str = "host"

    @property
    def agent_id(self) -> Optional[int]:
        return self.agent.id if self.agent else None


class AgentService:
    """Resolve tenant/site context and build public site config payloads."""

    PLATFORM_CONFIG_DEFAULTS = {
        "platform_site_name": settings.PLATFORM_SITE_NAME,
        "platform_site_subtitle": settings.PLATFORM_SITE_SUBTITLE,
        "platform_announcement_title": settings.PLATFORM_ANNOUNCEMENT_TITLE,
        "platform_announcement_content": settings.PLATFORM_ANNOUNCEMENT_CONTENT,
        "platform_support_wechat": settings.PLATFORM_SUPPORT_WECHAT,
        "platform_support_qq": settings.PLATFORM_SUPPORT_QQ,
        "platform_allow_register": "true" if settings.PLATFORM_ALLOW_REGISTER else "false",
        "api_base_url": "https://api.xiaoleai.team",
    }

    SITE_HINT_SOURCES = ("x_site_host", "origin", "referer")

    @staticmethod
    def normalize_host(raw_host: Optional[str]) -> str:
        host = str(raw_host or "").strip().lower()
        if not host or host in {"null", "undefined"}:
            return ""
        if host.startswith("[") and "]" in host:
            host = host[1:].split("]", 1)[0]
            return host
        return host.split(":", 1)[0]

    @staticmethod
    def extract_host_from_url(raw_value: Optional[str]) -> str:
        value = str(raw_value or "").strip()
        if not value or value.lower() in {"null", "undefined"}:
            return ""
        parsed = urlparse(value if "://" in value else f"//{value}")
        return AgentService.normalize_host(parsed.netloc or parsed.path)

    @staticmethod
    def get_shared_api_base_url() -> str:
        return str(AgentService.PLATFORM_CONFIG_DEFAULTS.get("api_base_url") or "https://api.xiaoleai.team").rstrip("/")

    @staticmethod
    def is_platform_frontend_host(host: str) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {AgentService.normalize_host(item) for item in settings.PLATFORM_FRONTEND_HOSTS}

    @staticmethod
    def is_platform_api_host(host: str) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {AgentService.normalize_host(item) for item in settings.PLATFORM_API_HOSTS}

    @staticmethod
    def is_local_dev_host(host: Optional[str]) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"}

    @staticmethod
    def get_agent_by_frontend_host(db: Session, host: str) -> Optional[Agent]:
        normalized = AgentService.normalize_host(host)
        if not normalized:
            return None
        return (
            db.query(Agent)
            .filter(
                Agent.status == "active",
                Agent.frontend_domain == normalized,
            )
            .first()
        )

    @staticmethod
    def get_agent_by_host(db: Session, host: str) -> Optional[Agent]:
        normalized = AgentService.normalize_host(host)
        if not normalized:
            return None
        agent = AgentService.get_agent_by_frontend_host(db, normalized)
        if agent:
            return agent
        return (
            db.query(Agent)
            .filter(
                Agent.status == "active",
                Agent.api_domain == normalized,
            )
            .first()
        )

    @staticmethod
    def resolve_request_site_host(
        host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> tuple[str, str]:
        candidates = (
            ("x_site_host", AgentService.normalize_host(x_site_host)),
            ("origin", AgentService.extract_host_from_url(origin)),
            ("referer", AgentService.extract_host_from_url(referer)),
            ("host", AgentService.normalize_host(host)),
        )
        for source, candidate in candidates:
            if candidate:
                return candidate, source
        return "", "host"

    @staticmethod
    def _agent_to_dict(agent: Agent, balance: Optional[AgentBalance] = None, image_balance: Optional[AgentImageBalance] = None) -> dict:
        return {
            "id": agent.id,
            "agent_code": agent.agent_code,
            "agent_name": agent.agent_name,
            "owner_user_id": agent.owner_user_id,
            "status": agent.status,
            "frontend_domain": agent.frontend_domain,
            "api_domain": agent.api_domain,
            "site_title": agent.site_title,
            "site_subtitle": agent.site_subtitle,
            "announcement_title": agent.announcement_title,
            "announcement_content": agent.announcement_content,
            "support_wechat": agent.support_wechat,
            "support_qq": agent.support_qq,
            "quickstart_api_base_url": agent.quickstart_api_base_url or AgentService.get_shared_api_base_url(),
            "allow_self_register": bool(agent.allow_self_register),
            "theme_config_json": agent.theme_config_json,
            "balance": float(balance.balance) if balance else 0.0,
            "image_credit_balance": float(image_balance.balance) if image_balance else 0.0,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }

    @staticmethod
    def get_site_context(
        db: Session,
        host: Optional[str],
    ) -> AgentSiteContext:
        return AgentService.get_site_context_from_request(db, host=host)

    @staticmethod
    def get_site_context_from_request(
        db: Session,
        host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> AgentSiteContext:
        request_host = AgentService.normalize_host(host)
        resolved_host, resolved_from = AgentService.resolve_request_site_host(
            host=host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        if resolved_from in AgentService.SITE_HINT_SOURCES:
            agent = AgentService.get_agent_by_frontend_host(db, resolved_host)
        else:
            agent = AgentService.get_agent_by_host(db, resolved_host)

        if agent:
            api_host = request_host or resolved_host
            is_api_host = api_host == AgentService.normalize_host(agent.api_domain)
            return AgentSiteContext(
                host=resolved_host,
                site_scope="agent",
                is_api_host=is_api_host,
                agent=agent,
                request_host=request_host,
                resolved_from=resolved_from,
            )

        effective_host = resolved_host or request_host
        return AgentSiteContext(
            host=effective_host,
            site_scope="platform",
            is_api_host=AgentService.is_platform_api_host(request_host or effective_host),
            agent=None,
            request_host=request_host,
            resolved_from=resolved_from,
        )

    @staticmethod
    def _get_platform_config_map(db: Session) -> dict[str, str]:
        keys = list(AgentService.PLATFORM_CONFIG_DEFAULTS.keys())
        rows = db.query(SystemConfig).filter(SystemConfig.config_key.in_(keys)).all()
        config_map = dict(AgentService.PLATFORM_CONFIG_DEFAULTS)
        for row in rows:
            config_map[row.config_key] = row.config_value
        return config_map

    @staticmethod
    def build_public_site_config(
        db: Session,
        host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> dict:
        context = AgentService.get_site_context_from_request(
            db,
            host=host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        if context.agent:
            agent = context.agent
            return {
                "site_scope": "agent",
                "agent_id": agent.id,
                "agent_code": agent.agent_code,
                "site_name": agent.site_title or agent.agent_name,
                "site_subtitle": agent.site_subtitle or "",
                "announcement_title": agent.announcement_title or "平台公告",
                "announcement_content": agent.announcement_content or "",
                "support_wechat": agent.support_wechat or "",
                "support_qq": agent.support_qq or "",
                "quickstart_api_base_url": agent.quickstart_api_base_url or AgentService.get_shared_api_base_url(),
                "allow_register": bool(agent.allow_self_register),
                "theme_config": agent.theme_config_json,
                "frontend_domain": agent.frontend_domain,
                "api_domain": agent.api_domain,
            }

        config_map = AgentService._get_platform_config_map(db)
        return {
            "site_scope": "platform",
            "agent_id": None,
            "agent_code": None,
            "site_name": config_map["platform_site_name"],
            "site_subtitle": config_map["platform_site_subtitle"],
            "announcement_title": config_map["platform_announcement_title"],
            "announcement_content": config_map["platform_announcement_content"],
            "support_wechat": config_map["platform_support_wechat"],
            "support_qq": config_map["platform_support_qq"],
            "quickstart_api_base_url": config_map["api_base_url"],
            "allow_register": str(config_map["platform_allow_register"]).lower() in {"1", "true", "yes"},
            "theme_config": None,
            "frontend_domain": None,
            "api_domain": None,
        }

    @staticmethod
    def is_self_register_allowed(
        db: Session,
        host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> bool:
        context = AgentService.get_site_context_from_request(
            db,
            host=host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        if context.agent:
            return bool(context.agent.allow_self_register)
        config_map = AgentService._get_platform_config_map(db)
        return str(config_map["platform_allow_register"]).lower() in {"1", "true", "yes"}

    @staticmethod
    def is_shared_api_direct_context(context: AgentSiteContext) -> bool:
        return (
            context.resolved_from == "host"
            and context.site_scope == "platform"
            and AgentService.is_platform_api_host(context.request_host or context.host)
        )

    @staticmethod
    def assert_user_matches_site(
        db: Session,
        user,
        host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> AgentSiteContext:
        """Ensure the authenticated user is accessing the correct site/domain."""
        context = AgentService.get_site_context_from_request(
            db,
            host=host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        if AgentService.is_local_dev_host(context.host or context.request_host):
            return context
        if str(getattr(user, "role", "") or "") == "admin":
            if context.site_scope != "platform":
                raise ServiceException(403, "管理员只能访问平台站点", "AGENT_SITE_MISMATCH")
            return context

        user_agent_id = getattr(user, "agent_id", None)
        if user_agent_id is None:
            if context.site_scope != "platform":
                raise ServiceException(403, "平台直营用户不能访问代理站点", "AGENT_SITE_MISMATCH")
            return context

        if AgentService.is_shared_api_direct_context(context):
            return context

        if context.site_scope != "agent" or int(user_agent_id) != int(context.agent_id or 0):
            raise ServiceException(403, "当前代理域名与账号归属不匹配", "AGENT_DOMAIN_MISMATCH")
        return context

    @staticmethod
    def list_agents(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        query = db.query(Agent)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    Agent.agent_code.like(like),
                    Agent.agent_name.like(like),
                    Agent.frontend_domain.like(like),
                    Agent.api_domain.like(like),
                )
            )
        total = query.count()
        items = (
            query.order_by(Agent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        result: list[dict] = []
        for agent in items:
            balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent.id).first()
            image_balance = db.query(AgentImageBalance).filter(AgentImageBalance.agent_id == agent.id).first()
            result.append(AgentService._agent_to_dict(agent, balance, image_balance))
        return result, total

    @staticmethod
    def get_agent(db: Session, agent_id: int) -> dict:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")
        balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent.id).first()
        image_balance = db.query(AgentImageBalance).filter(AgentImageBalance.agent_id == agent.id).first()
        return AgentService._agent_to_dict(agent, balance, image_balance)

    @staticmethod
    def _normalize_agent_payload(data: dict) -> dict:
        payload = dict(data)
        if "agent_code" in payload and payload["agent_code"] is not None:
            payload["agent_code"] = str(payload["agent_code"]).strip()
        if "agent_name" in payload and payload["agent_name"] is not None:
            payload["agent_name"] = str(payload["agent_name"]).strip()
        if "owner_username" in payload and payload["owner_username"] is not None:
            payload["owner_username"] = str(payload["owner_username"]).strip()
        if "owner_email" in payload and payload["owner_email"] is not None:
            payload["owner_email"] = str(payload["owner_email"]).strip().lower()
        for key in ("frontend_domain", "api_domain"):
            if key in payload:
                payload[key] = AgentService.normalize_host(payload.get(key))
        if payload.get("api_domain") and AgentService.is_platform_api_host(payload.get("api_domain")):
            payload["api_domain"] = None
        if "quickstart_api_base_url" in payload and payload.get("quickstart_api_base_url"):
            payload["quickstart_api_base_url"] = str(payload["quickstart_api_base_url"]).strip().rstrip("/")
        elif "quickstart_api_base_url" in payload:
            payload["quickstart_api_base_url"] = AgentService.get_shared_api_base_url()
        if "status" in payload and payload.get("status") not in {None, "active", "disabled"}:
            raise ServiceException(400, "代理状态不合法", "INVALID_AGENT_STATUS")
        return payload

    @staticmethod
    def create_agent(db: Session, data) -> dict:
        payload = AgentService._normalize_agent_payload(data if isinstance(data, dict) else data.model_dump(exclude_unset=True))
        if not payload.get("agent_code"):
            raise ServiceException(400, "代理编码不能为空", "INVALID_AGENT_CODE")
        if not payload.get("agent_name"):
            raise ServiceException(400, "代理名称不能为空", "INVALID_AGENT_NAME")

        duplicate_filters = [Agent.agent_code == payload["agent_code"]]
        if payload.get("frontend_domain"):
            duplicate_filters.append(Agent.frontend_domain == payload["frontend_domain"])
        if payload.get("api_domain"):
            duplicate_filters.append(Agent.api_domain == payload["api_domain"])

        duplicate = db.query(Agent).filter(or_(*duplicate_filters)).first()
        if duplicate:
            raise ServiceException(400, "代理编码或域名已存在", "DUPLICATE_AGENT")
        if payload.get("owner_user_id") is not None and payload.get("owner_username"):
            raise ServiceException(400, "不能同时绑定已有代理账号和创建新代理账号", "DUPLICATE_AGENT_OWNER_SOURCE")

        agent = Agent(
            agent_code=payload["agent_code"],
            agent_name=payload["agent_name"],
            owner_user_id=payload.get("owner_user_id"),
            status=payload.get("status") or "active",
            frontend_domain=payload.get("frontend_domain") or None,
            api_domain=payload.get("api_domain") or None,
            site_title=payload.get("site_title") or payload["agent_name"],
            site_subtitle=payload.get("site_subtitle"),
            announcement_title=payload.get("announcement_title"),
            announcement_content=payload.get("announcement_content"),
            support_wechat=payload.get("support_wechat"),
            support_qq=payload.get("support_qq"),
            quickstart_api_base_url=payload.get("quickstart_api_base_url") or AgentService.get_shared_api_base_url(),
            allow_self_register=int(payload.get("allow_self_register", 1)),
            theme_config_json=payload.get("theme_config_json"),
        )
        db.add(agent)
        db.flush()

        if payload.get("owner_user_id") is not None:
            owner = db.query(SysUser).filter(SysUser.id == payload["owner_user_id"]).first()
            if not owner:
                raise ServiceException(404, "代理主账号不存在", "OWNER_USER_NOT_FOUND")
            if owner.role == "admin":
                raise ServiceException(400, "管理员账号不能绑定为代理主账号", "INVALID_AGENT_OWNER")
            owner.role = "agent"
            owner.agent_id = agent.id
            agent.owner_user_id = owner.id
        elif payload.get("owner_username") or payload.get("owner_password"):
            if not payload.get("owner_username"):
                raise ServiceException(400, "代理登录账号不能为空", "INVALID_AGENT_OWNER_USERNAME")
            if not payload.get("owner_password"):
                raise ServiceException(400, "代理登录密码不能为空", "INVALID_AGENT_OWNER_PASSWORD")
            if db.query(SysUser).filter(SysUser.username == payload["owner_username"]).first():
                raise ServiceException(400, "代理登录账号已存在", "DUPLICATE_AGENT_OWNER_USERNAME")
            owner_email = payload.get("owner_email") or f"{payload['owner_username']}@{payload['agent_code']}.agent.local"
            if db.query(SysUser).filter(SysUser.email == owner_email).first():
                raise ServiceException(400, "代理登录邮箱已被使用", "DUPLICATE_AGENT_OWNER_EMAIL")
            owner = SysUser(
                username=payload["owner_username"],
                email=owner_email,
                password_hash=hash_password(payload["owner_password"]),
                role="agent",
                agent_id=agent.id,
                source_domain=agent.frontend_domain,
                status=1,
            )
            db.add(owner)
            db.flush()
            agent.owner_user_id = owner.id

        db.add(AgentBalance(agent_id=agent.id, balance=0, total_recharged=0, total_allocated=0, total_reclaimed=0))
        db.add(AgentImageBalance(agent_id=agent.id, balance=0, total_recharged=0, total_allocated=0, total_reclaimed=0))
        db.commit()
        db.refresh(agent)
        return AgentService.get_agent(db, agent.id)

    @staticmethod
    def update_agent(db: Session, agent_id: int, data) -> dict:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")

        payload = AgentService._normalize_agent_payload(data if isinstance(data, dict) else data.model_dump(exclude_unset=True))
        if payload.get("agent_code") and payload["agent_code"] != agent.agent_code:
            duplicate = db.query(Agent).filter(Agent.agent_code == payload["agent_code"]).first()
            if duplicate:
                raise ServiceException(400, "代理编码已存在", "DUPLICATE_AGENT_CODE")

        for domain_key in ("frontend_domain", "api_domain"):
            domain_value = payload.get(domain_key)
            if domain_value and domain_value != getattr(agent, domain_key):
                duplicate_domain = db.query(Agent).filter(getattr(Agent, domain_key) == domain_value, Agent.id != agent.id).first()
                if duplicate_domain:
                    raise ServiceException(400, "代理域名已存在", "DUPLICATE_AGENT_DOMAIN")

        for field in (
            "agent_code",
            "agent_name",
            "owner_user_id",
            "status",
            "frontend_domain",
            "api_domain",
            "site_title",
            "site_subtitle",
            "announcement_title",
            "announcement_content",
            "support_wechat",
            "support_qq",
            "quickstart_api_base_url",
            "theme_config_json",
        ):
            if field in payload:
                value = payload.get(field)
                if field in {"frontend_domain", "api_domain"}:
                    value = value or None
                setattr(agent, field, value)

        if "allow_self_register" in payload and payload["allow_self_register"] is not None:
            agent.allow_self_register = int(payload["allow_self_register"])

        if "owner_user_id" in payload and payload.get("owner_user_id") is not None:
            owner = db.query(SysUser).filter(SysUser.id == payload["owner_user_id"]).first()
            if not owner:
                raise ServiceException(404, "代理主账号不存在", "OWNER_USER_NOT_FOUND")
            if owner.role == "admin":
                raise ServiceException(400, "管理员账号不能绑定为代理主账号", "INVALID_AGENT_OWNER")
            owner.role = "agent"
            owner.agent_id = agent.id
            agent.owner_user_id = owner.id

        db.commit()
        db.refresh(agent)
        return AgentService.get_agent(db, agent.id)

    @staticmethod
    def list_agent_subscription_inventory(db: Session, agent_id: int) -> list[dict]:
        rows = (
            db.query(AgentSubscriptionInventory, SubscriptionPlan.plan_name, SubscriptionPlan.plan_code)
            .outerjoin(SubscriptionPlan, SubscriptionPlan.id == AgentSubscriptionInventory.plan_id)
            .filter(AgentSubscriptionInventory.agent_id == agent_id)
            .order_by(AgentSubscriptionInventory.id.asc())
            .all()
        )
        return [
            {
                "id": inventory.id,
                "agent_id": inventory.agent_id,
                "plan_id": inventory.plan_id,
                "plan_name": plan_name,
                "plan_code": plan_code,
                "total_granted": int(inventory.total_granted or 0),
                "total_used": int(inventory.total_used or 0),
                "remaining_count": int(inventory.remaining_count or 0),
                "created_at": inventory.created_at.isoformat() if inventory.created_at else None,
                "updated_at": inventory.updated_at.isoformat() if inventory.updated_at else None,
            }
            for inventory, plan_name, plan_code in rows
        ]
