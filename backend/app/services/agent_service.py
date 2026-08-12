"""Agent tenant resolution and site configuration service."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import ipaddress
import json
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
    origin_url: str = ""
    referer_url: str = ""

    @property
    def agent_id(self) -> Optional[int]:
        return self.agent.id if self.agent else None


@dataclass(frozen=True)
class AgentAuditContext:
    """Operator metadata for agent configuration audit records."""

    user_id: Optional[int]
    username: Optional[str]
    source: str
    ip_address: Optional[str] = None


@dataclass(frozen=True)
class AgentRechargePolicy:
    """Validated recharge rules for one authenticated user's ownership scope."""

    agent_id: Optional[int]
    agent_status: str
    online_recharge_enabled: bool
    subscription_online_recharge_configured: bool
    subscription_online_recharge_enabled: bool
    custom_recharge_rate_enabled: bool
    balance_recharge_rate: Decimal
    image_credit_recharge_rate: Decimal
    balance_agent_settlement_rate: Decimal
    image_credit_agent_settlement_rate: Decimal
    max_custom_recharge_rate: Decimal

    def user_rate_for(self, recharge_type: str) -> Decimal:
        if str(recharge_type or "").strip().lower() == "image_credit":
            return self.image_credit_recharge_rate
        return self.balance_recharge_rate


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
        "api_base_url": "",
    }

    SITE_HINT_SOURCES = ("x_site_host", "origin", "referer")
    RECHARGE_RATE_SCALE = Decimal("0.000001")
    MIN_CUSTOM_RECHARGE_RATE = Decimal("0.01")

    @staticmethod
    def _append_pricing_audit_log(
        db: Session,
        audit_context: Optional[AgentAuditContext],
        agent_id: int,
        action: str,
        details: dict,
    ) -> None:
        if audit_context is None:
            return
        from app.services.log_service import LogService

        LogService.create_operation_log(
            db,
            audit_context.user_id,
            audit_context.username,
            action,
            target_type="agent",
            target_id=agent_id,
            description=json.dumps(
                {"source": audit_context.source, **details},
                ensure_ascii=False,
                sort_keys=True,
            ),
            ip=audit_context.ip_address,
            agent_id=agent_id,
            auto_commit=False,
        )

    @staticmethod
    def _rate_setting(value, error_code: str) -> Decimal:
        try:
            rate = Decimal(str(value))
            normalized = rate.quantize(AgentService.RECHARGE_RATE_SCALE)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(500, "充值比例配置无效", error_code) from exc
        if not rate.is_finite() or rate <= 0 or normalized != rate:
            raise ServiceException(500, "充值比例配置无效", error_code)
        return rate

    @staticmethod
    def _recharge_rate_settings() -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return (
            AgentService._rate_setting(settings.RECHARGE_USER_CNY_TO_USD_RATE, "RECHARGE_USER_RATE_INVALID"),
            AgentService._rate_setting(settings.RECHARGE_IMAGE_CREDIT_USER_CNY_RATE, "RECHARGE_IMAGE_CREDIT_USER_RATE_INVALID"),
            AgentService._rate_setting(settings.RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE, "RECHARGE_AGENT_RATE_INVALID"),
            AgentService._rate_setting(settings.RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE, "RECHARGE_IMAGE_CREDIT_AGENT_RATE_INVALID"),
        )

    @staticmethod
    def get_max_custom_recharge_rate() -> Decimal:
        _, _, balance_agent_rate, image_agent_rate = AgentService._recharge_rate_settings()
        return min(balance_agent_rate, image_agent_rate)

    @staticmethod
    def get_default_custom_recharge_rate() -> Decimal:
        balance_user_rate, _, _, _ = AgentService._recharge_rate_settings()
        return balance_user_rate

    @staticmethod
    def validate_custom_recharge_rate(value, max_rate: Optional[Decimal] = None) -> Decimal:
        try:
            rate = Decimal(str(value))
            normalized = rate.quantize(AgentService.RECHARGE_RATE_SCALE)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "充值比例格式不正确", "AGENT_CUSTOM_RECHARGE_RATE_INVALID") from exc
        if not rate.is_finite() or normalized != rate:
            raise ServiceException(400, "充值比例最多支持 6 位小数", "AGENT_CUSTOM_RECHARGE_RATE_INVALID")
        if rate < AgentService.MIN_CUSTOM_RECHARGE_RATE:
            raise ServiceException(400, "充值比例不能小于 0.01", "AGENT_CUSTOM_RECHARGE_RATE_INVALID")
        resolved_max = max_rate if max_rate is not None else AgentService.get_max_custom_recharge_rate()
        if rate > resolved_max:
            raise ServiceException(
                400,
                f"充值比例不能高于代理结算比例上限 {resolved_max}",
                "AGENT_CUSTOM_RECHARGE_RATE_EXCEEDS_LIMIT",
            )
        return normalized

    @staticmethod
    def _build_recharge_policy(agent: Optional[Agent] = None) -> AgentRechargePolicy:
        balance_user_rate, image_user_rate, balance_agent_rate, image_agent_rate = AgentService._recharge_rate_settings()
        max_custom_rate = min(balance_agent_rate, image_agent_rate)
        if agent is not None and str(agent.status or "") != "active":
            raise ServiceException(403, "所属代理已停用，在线充值不可用", "AGENT_RECHARGE_POLICY_UNAVAILABLE")

        custom_enabled = bool(getattr(agent, "custom_recharge_rate_enabled", 0)) if agent is not None else False
        if custom_enabled:
            custom_rate = AgentService.validate_custom_recharge_rate(
                getattr(agent, "custom_recharge_rate", None),
                max_rate=max_custom_rate,
            )
            balance_user_rate = custom_rate
            image_user_rate = custom_rate

        payment_enabled = bool(settings.ALIPAY_ENABLED or settings.WECHAT_PAY_ENABLED)
        online_enabled = payment_enabled and (agent is None or bool(getattr(agent, "online_recharge_enabled", 1)))
        subscription_configured = agent is None or bool(getattr(agent, "subscription_online_recharge_enabled", 1))
        subscription_enabled = online_enabled and subscription_configured and not custom_enabled
        return AgentRechargePolicy(
            agent_id=int(agent.id) if agent is not None else None,
            agent_status=str(agent.status or "active") if agent is not None else "platform",
            online_recharge_enabled=online_enabled,
            subscription_online_recharge_configured=subscription_configured,
            subscription_online_recharge_enabled=subscription_enabled,
            custom_recharge_rate_enabled=custom_enabled,
            balance_recharge_rate=balance_user_rate,
            image_credit_recharge_rate=image_user_rate,
            balance_agent_settlement_rate=balance_agent_rate,
            image_credit_agent_settlement_rate=image_agent_rate,
            max_custom_recharge_rate=max_custom_rate,
        )

    @staticmethod
    def resolve_user_recharge_policy(db: Session, user) -> AgentRechargePolicy:
        agent_id = getattr(user, "agent_id", None)
        if agent_id is None:
            return AgentService._build_recharge_policy()
        agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
        if not agent:
            raise ServiceException(403, "账号所属代理不存在，在线充值不可用", "AGENT_RECHARGE_POLICY_UNAVAILABLE")
        return AgentService._build_recharge_policy(agent)

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
    def get_shared_api_base_url(db: Optional[Session] = None) -> str:
        if db is not None:
            row = (
                db.query(SystemConfig)
                .filter(SystemConfig.config_key == "api_base_url")
                .first()
            )
            if row and str(row.config_value or "").strip():
                return str(row.config_value).strip().rstrip("/")
        return str(AgentService.PLATFORM_CONFIG_DEFAULTS.get("api_base_url") or "").strip().rstrip("/")

    @staticmethod
    def normalize_api_base_url(
        raw_value: Optional[str],
        db: Optional[Session] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        value = str(raw_value or "").strip()
        if not value or value.lower() in {"null", "undefined"}:
            return None, None
        if any(ch.isspace() for ch in value):
            raise ServiceException(400, "API 地址不能包含空格", "INVALID_AGENT_API_BASE_URL")

        try:
            parsed = urlparse(value)
        except ValueError as exc:
            raise ServiceException(400, "API 地址格式不正确", "INVALID_AGENT_API_BASE_URL") from exc
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ServiceException(400, "API 地址必须是完整的 HTTP 或 HTTPS 地址", "INVALID_AGENT_API_BASE_URL")
        if parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ServiceException(400, "API 地址格式不正确", "INVALID_AGENT_API_BASE_URL")
        if parsed.path not in {"", "/"}:
            raise ServiceException(400, "API 地址不能包含路径", "INVALID_AGENT_API_BASE_URL")

        try:
            hostname = str(parsed.hostname or "").strip().lower()
        except ValueError as exc:
            raise ServiceException(400, "API 地址域名格式不正确", "INVALID_AGENT_API_BASE_URL") from exc
        if not hostname:
            raise ServiceException(400, "API 地址格式不正确", "INVALID_AGENT_API_BASE_URL")
        is_platform_api = AgentService.is_platform_api_host(hostname, db)
        if AgentService.is_platform_frontend_host(hostname) and not is_platform_api:
            raise ServiceException(400, "API 地址不能使用平台站点域名", "INVALID_AGENT_API_BASE_URL")
        if len(hostname) > 253:
            raise ServiceException(400, "API 地址域名过长", "INVALID_AGENT_API_BASE_URL")
        if hostname not in {"localhost", "127.0.0.1"} and not hostname.endswith((".localhost", ".local")):
            try:
                ipaddress.ip_address(hostname)
            except ValueError:
                labels = hostname.split(".")
                if len(labels) < 2 or any(
                    not label
                    or len(label) > 63
                    or label.startswith("-")
                    or label.endswith("-")
                    or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in label)
                    for label in labels
                ):
                    raise ServiceException(400, "API 地址域名格式不正确", "INVALID_AGENT_API_BASE_URL")

        try:
            port = parsed.port
        except ValueError as exc:
            raise ServiceException(400, "API 地址端口格式不正确", "INVALID_AGENT_API_BASE_URL") from exc
        formatted_host = f"[{hostname}]" if ":" in hostname else hostname
        if port is not None:
            formatted_host = f"{formatted_host}:{port}"
        normalized_url = f"{parsed.scheme.lower()}://{formatted_host}"
        api_domain = None if is_platform_api else hostname
        return normalized_url, api_domain

    @staticmethod
    def normalize_shared_api_base_url(db: Session, raw_value: Optional[str]) -> str:
        """Validate a platform API URL without allowing it to claim an agent domain."""
        normalized_url, _ = AgentService.normalize_api_base_url(raw_value)
        hostname = AgentService.extract_host_from_url(normalized_url)
        if not normalized_url or not hostname:
            raise ServiceException(400, "平台共享 API 地址不能为空", "INVALID_SHARED_API_BASE_URL")
        conflicting_agent = (
            db.query(Agent)
            .filter(
                or_(
                    Agent.frontend_domain == hostname,
                    Agent.api_domain == hostname,
                )
            )
            .first()
        )
        if conflicting_agent:
            raise ServiceException(
                400,
                "平台共享 API 域名已被代理使用",
                "SHARED_API_DOMAIN_CONFLICT",
            )
        return normalized_url

    @staticmethod
    def is_platform_frontend_host(host: str) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {AgentService.normalize_host(item) for item in settings.PLATFORM_FRONTEND_HOSTS}

    @staticmethod
    def is_platform_api_host(host: str, db: Optional[Session] = None) -> bool:
        normalized = AgentService.normalize_host(host)
        if AgentService.is_static_platform_api_host(normalized):
            return True
        if db is None:
            return False
        shared_host = AgentService.extract_host_from_url(AgentService.get_shared_api_base_url(db))
        return bool(shared_host and normalized == shared_host)

    @staticmethod
    def is_static_platform_api_host(host: str) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"} or normalized in {
            AgentService.normalize_host(item) for item in settings.PLATFORM_API_HOSTS
        }

    @staticmethod
    def is_local_dev_host(host: Optional[str]) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"}

    @staticmethod
    def _validate_domain_host(normalized: str, *, field_label: str, error_code: str) -> str:
        if not normalized:
            return ""
        if len(normalized) > 253:
            raise ServiceException(400, f"{field_label}过长", error_code)
        if normalized in {AgentService.normalize_host(item) for item in settings.PLATFORM_FRONTEND_HOSTS}:
            raise ServiceException(400, f"{field_label}不能使用平台站点域名", error_code)
        if normalized in {AgentService.normalize_host(item) for item in settings.PLATFORM_API_HOSTS}:
            raise ServiceException(400, f"{field_label}不能使用平台 API 域名", error_code)
        if normalized in {"localhost", "127.0.0.1"} or normalized.endswith(".localhost") or normalized.endswith(".local"):
            return normalized
        try:
            ipaddress.ip_address(normalized)
            return normalized
        except ValueError:
            pass
        labels = normalized.split(".")
        if len(labels) < 2:
            raise ServiceException(400, f"{field_label}格式不正确", error_code)
        for label in labels:
            if not label or len(label) > 63:
                raise ServiceException(400, f"{field_label}格式不正确", error_code)
            if label.startswith("-") or label.endswith("-"):
                raise ServiceException(400, f"{field_label}格式不正确", error_code)
            if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in label):
                raise ServiceException(400, f"{field_label}格式不正确", error_code)
        return normalized

    @staticmethod
    def normalize_domain_input(raw_value: Optional[str], *, field_label: str, error_code: str) -> str:
        value = str(raw_value or "").strip()
        if not value or value.lower() in {"null", "undefined"}:
            return ""
        if any(ch.isspace() for ch in value):
            raise ServiceException(400, f"{field_label}不能包含空格", error_code)
        parsed = urlparse(value if "://" in value else f"//{value}")
        if parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ServiceException(400, f"{field_label}格式不正确", error_code)
        candidate = parsed.netloc or parsed.path
        if parsed.netloc and parsed.path not in {"", "/"}:
            raise ServiceException(400, f"{field_label}不能包含路径", error_code)
        if not parsed.netloc and "/" in parsed.path:
            raise ServiceException(400, f"{field_label}不能包含路径", error_code)
        normalized = AgentService.normalize_host(candidate)
        return AgentService._validate_domain_host(normalized, field_label=field_label, error_code=error_code)

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
    def get_agent_by_api_host(db: Session, host: str) -> Optional[Agent]:
        normalized = AgentService.normalize_host(host)
        if not normalized:
            return None
        return (
            db.query(Agent)
            .filter(
                Agent.status == "active",
                Agent.api_domain == normalized,
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
        return AgentService.get_agent_by_api_host(db, normalized)

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
    def _agent_to_dict(
        agent: Agent,
        balance: Optional[AgentBalance] = None,
        image_balance: Optional[AgentImageBalance] = None,
        shared_api_base_url: str = "",
    ) -> dict:
        balance_user_rate, image_user_rate, _, _ = AgentService._recharge_rate_settings()
        custom_enabled = bool(getattr(agent, "custom_recharge_rate_enabled", 0))
        saved_custom_rate = Decimal(str(getattr(agent, "custom_recharge_rate", None) or balance_user_rate))
        subscription_configured = bool(getattr(agent, "subscription_online_recharge_enabled", 1))
        effective_subscription_enabled = (
            bool(settings.ALIPAY_ENABLED or settings.WECHAT_PAY_ENABLED)
            and bool(agent.online_recharge_enabled)
            and subscription_configured
            and not custom_enabled
        )
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
            "quickstart_api_base_url": agent.quickstart_api_base_url or shared_api_base_url,
            "configured_quickstart_api_base_url": agent.quickstart_api_base_url or "",
            "uses_shared_api_base_url": not bool(agent.quickstart_api_base_url),
            "allow_self_register": bool(agent.allow_self_register),
            "online_recharge_enabled": bool(agent.online_recharge_enabled),
            "subscription_online_recharge_enabled": subscription_configured,
            "subscription_online_recharge_configured": subscription_configured,
            "effective_subscription_online_recharge_enabled": effective_subscription_enabled,
            "custom_recharge_rate_enabled": custom_enabled,
            "custom_recharge_rate": float(saved_custom_rate),
            "max_custom_recharge_rate": float(AgentService.get_max_custom_recharge_rate()),
            "balance_recharge_rate": float(saved_custom_rate if custom_enabled else balance_user_rate),
            "image_credit_recharge_rate": float(saved_custom_rate if custom_enabled else image_user_rate),
            "theme_config_json": agent.theme_config_json,
            "balance": float(balance.balance) if balance else 0.0,
            "image_credit_balance": float(image_balance.balance) if image_balance else 0.0,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }

    @staticmethod
    def is_online_recharge_enabled(context: AgentSiteContext) -> bool:
        if not bool(settings.ALIPAY_ENABLED or settings.WECHAT_PAY_ENABLED):
            return False
        if context.site_scope != "agent" or not context.agent:
            return True
        return bool(getattr(context.agent, "online_recharge_enabled", 1))

    @staticmethod
    def is_subscription_online_recharge_enabled(context: AgentSiteContext) -> bool:
        if not AgentService.is_online_recharge_enabled(context):
            return False
        if context.site_scope != "agent" or not context.agent:
            return True
        return (
            bool(getattr(context.agent, "subscription_online_recharge_enabled", 1))
            and not bool(getattr(context.agent, "custom_recharge_rate_enabled", 0))
        )

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
        direct_host = request_host or resolved_host
        direct_host_agent = (
            AgentService.get_agent_by_host(db, direct_host)
            if resolved_from == "host"
            else None
        )
        if (
            resolved_from == "host"
            and AgentService.is_platform_api_host(direct_host, db)
            and (
                AgentService.is_static_platform_api_host(direct_host)
                or direct_host_agent is None
            )
        ):
            return AgentSiteContext(
                host=resolved_host or request_host,
                site_scope="platform",
                is_api_host=True,
                agent=None,
                request_host=request_host,
                resolved_from=resolved_from,
                origin_url=str(origin or "").strip(),
                referer_url=str(referer or "").strip(),
            )
        if resolved_from in AgentService.SITE_HINT_SOURCES:
            agent = AgentService.get_agent_by_frontend_host(db, resolved_host)
        else:
            # A conflicting database-configured shared host must fail closed to
            # the owning tenant until the configuration is corrected.
            agent = direct_host_agent or AgentService.get_agent_by_host(db, resolved_host)

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
                origin_url=str(origin or "").strip(),
                referer_url=str(referer or "").strip(),
            )

        effective_host = resolved_host or request_host
        return AgentSiteContext(
            host=effective_host,
            site_scope="platform",
            is_api_host=AgentService.is_platform_api_host(request_host or effective_host, db),
            agent=None,
            request_host=request_host,
            resolved_from=resolved_from,
            origin_url=str(origin or "").strip(),
            referer_url=str(referer or "").strip(),
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
        user=None,
    ) -> dict:
        context = AgentService.get_site_context_from_request(
            db,
            host=host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        user_api_agent = None
        if user is not None:
            recharge_policy = AgentService.resolve_user_recharge_policy(db, user)
            user_agent_id = getattr(user, "agent_id", None)
            if user_agent_id is not None:
                user_api_agent = db.query(Agent).filter(Agent.id == int(user_agent_id)).first()
        elif context.agent:
            recharge_policy = AgentService._build_recharge_policy(context.agent)
        else:
            recharge_policy = AgentService._build_recharge_policy()
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
                "quickstart_api_base_url": (
                    (user_api_agent.quickstart_api_base_url if user_api_agent else None)
                    or agent.quickstart_api_base_url
                    or AgentService.get_shared_api_base_url(db)
                ),
                "allow_register": bool(agent.allow_self_register),
                "email_verification_required": bool(settings.EMAIL_VERIFICATION_REQUIRED),
                "online_recharge_enabled": recharge_policy.online_recharge_enabled,
                "subscription_online_recharge_enabled": recharge_policy.subscription_online_recharge_enabled,
                "balance_recharge_rate": float(recharge_policy.balance_recharge_rate),
                "image_credit_recharge_rate": float(recharge_policy.image_credit_recharge_rate),
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
            "quickstart_api_base_url": (
                (user_api_agent.quickstart_api_base_url if user_api_agent else None)
                or config_map["api_base_url"]
            ),
            "allow_register": str(config_map["platform_allow_register"]).lower() in {"1", "true", "yes"},
            "email_verification_required": bool(settings.EMAIL_VERIFICATION_REQUIRED),
            "online_recharge_enabled": recharge_policy.online_recharge_enabled,
            "subscription_online_recharge_enabled": recharge_policy.subscription_online_recharge_enabled,
            "balance_recharge_rate": float(recharge_policy.balance_recharge_rate),
            "image_credit_recharge_rate": float(recharge_policy.image_credit_recharge_rate),
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
            and context.is_api_host
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
        return AgentService.assert_user_matches_context(user, context)

    @staticmethod
    def assert_user_matches_context(user, context: AgentSiteContext) -> AgentSiteContext:
        """Ensure an authenticated user belongs to an already resolved site context."""
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
        shared_api_base_url = AgentService.get_shared_api_base_url(db)
        for agent in items:
            balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent.id).first()
            image_balance = db.query(AgentImageBalance).filter(AgentImageBalance.agent_id == agent.id).first()
            result.append(AgentService._agent_to_dict(agent, balance, image_balance, shared_api_base_url))
        return result, total

    @staticmethod
    def get_agent(db: Session, agent_id: int) -> dict:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")
        balance = db.query(AgentBalance).filter(AgentBalance.agent_id == agent.id).first()
        image_balance = db.query(AgentImageBalance).filter(AgentImageBalance.agent_id == agent.id).first()
        return AgentService._agent_to_dict(
            agent,
            balance,
            image_balance,
            AgentService.get_shared_api_base_url(db),
        )

    @staticmethod
    def _normalize_agent_payload(data: dict, db: Optional[Session] = None) -> dict:
        payload = dict(data)
        if "agent_code" in payload and payload["agent_code"] is not None:
            payload["agent_code"] = str(payload["agent_code"]).strip()
        if "agent_name" in payload and payload["agent_name"] is not None:
            payload["agent_name"] = str(payload["agent_name"]).strip()
        if "owner_username" in payload and payload["owner_username"] is not None:
            payload["owner_username"] = str(payload["owner_username"]).strip()
        if "owner_email" in payload and payload["owner_email"] is not None:
            payload["owner_email"] = str(payload["owner_email"]).strip().lower()
        if "frontend_domain" in payload:
            payload["frontend_domain"] = AgentService.normalize_domain_input(
                payload.get("frontend_domain"),
                field_label="前台域名",
                error_code="INVALID_AGENT_FRONTEND_DOMAIN",
            )
            if payload["frontend_domain"] and AgentService.is_platform_api_host(
                payload["frontend_domain"],
                db,
            ):
                raise ServiceException(
                    400,
                    "前台域名不能使用平台 API 域名",
                    "INVALID_AGENT_FRONTEND_DOMAIN",
                )
        if "api_domain" in payload:
            api_domain = AgentService.normalize_domain_input(
                payload.get("api_domain"),
                field_label="代理 API 域名",
                error_code="INVALID_AGENT_API_DOMAIN",
            )
            payload["api_domain"] = None if AgentService.is_platform_api_host(api_domain, db) else api_domain
        if "quickstart_api_base_url" in payload:
            api_base_url, api_domain = AgentService.normalize_api_base_url(
                payload.get("quickstart_api_base_url"),
                db,
            )
            # Entering the current platform URL is equivalent to leaving the
            # field empty, so later platform URL changes propagate naturally.
            payload["quickstart_api_base_url"] = api_base_url if api_domain else None
            payload["api_domain"] = api_domain
        if "status" in payload and payload.get("status") not in {None, "active", "disabled"}:
            raise ServiceException(400, "代理状态不合法", "INVALID_AGENT_STATUS")
        return payload

    @staticmethod
    def create_agent(
        db: Session,
        data,
        audit_context: Optional[AgentAuditContext] = None,
    ) -> dict:
        payload = AgentService._normalize_agent_payload(
            data if isinstance(data, dict) else data.model_dump(exclude_unset=True),
            db,
        )
        if not payload.get("agent_code"):
            raise ServiceException(400, "代理编码不能为空", "INVALID_AGENT_CODE")
        if not payload.get("agent_name"):
            raise ServiceException(400, "代理名称不能为空", "INVALID_AGENT_NAME")

        duplicate = db.query(Agent).filter(Agent.agent_code == payload["agent_code"]).first()
        if duplicate:
            raise ServiceException(400, "代理编码已存在", "DUPLICATE_AGENT_CODE")
        candidate_domains = {
            value for value in (payload.get("frontend_domain"), payload.get("api_domain")) if value
        }
        if candidate_domains:
            duplicate_domain = (
                db.query(Agent)
                .filter(
                    or_(
                        Agent.frontend_domain.in_(candidate_domains),
                        Agent.api_domain.in_(candidate_domains),
                    )
                )
                .first()
            )
            if duplicate_domain:
                raise ServiceException(400, "代理域名已存在", "DUPLICATE_AGENT_DOMAIN")
        if payload.get("owner_user_id") is not None and payload.get("owner_username"):
            raise ServiceException(400, "不能同时绑定已有代理账号和创建新代理账号", "DUPLICATE_AGENT_OWNER_SOURCE")

        custom_recharge_rate = AgentService.get_default_custom_recharge_rate()
        custom_recharge_rate_enabled = int(payload.get("custom_recharge_rate_enabled", 0) or 0)
        if custom_recharge_rate_enabled:
            custom_recharge_rate = AgentService.validate_custom_recharge_rate(custom_recharge_rate)

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
            quickstart_api_base_url=payload.get("quickstart_api_base_url"),
            allow_self_register=int(payload.get("allow_self_register", 1)),
            online_recharge_enabled=int(payload.get("online_recharge_enabled", 1)),
            subscription_online_recharge_enabled=int(payload.get("subscription_online_recharge_enabled", 1)),
            custom_recharge_rate_enabled=custom_recharge_rate_enabled,
            custom_recharge_rate=custom_recharge_rate,
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
        try:
            if custom_recharge_rate_enabled:
                AgentService._append_pricing_audit_log(
                    db,
                    audit_context,
                    int(agent.id),
                    "update_agent_recharge_pricing_permission",
                    {
                        "event": "create",
                        "custom_recharge_rate_enabled_before": False,
                        "custom_recharge_rate_enabled_after": True,
                        "custom_recharge_rate": float(custom_recharge_rate),
                    },
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        from app.core.cors import invalidate_dynamic_origin_cache
        invalidate_dynamic_origin_cache()
        db.refresh(agent)
        return AgentService.get_agent(db, agent.id)

    @staticmethod
    def update_agent(
        db: Session,
        agent_id: int,
        data,
        audit_context: Optional[AgentAuditContext] = None,
    ) -> dict:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ServiceException(404, "代理不存在", "AGENT_NOT_FOUND")

        payload = AgentService._normalize_agent_payload(
            data if isinstance(data, dict) else data.model_dump(exclude_unset=True),
            db,
        )
        current_custom_enabled = bool(getattr(agent, "custom_recharge_rate_enabled", 0))
        current_custom_rate = Decimal(str(getattr(agent, "custom_recharge_rate", None) or AgentService.get_default_custom_recharge_rate()))
        current_subscription_enabled = bool(getattr(agent, "subscription_online_recharge_enabled", 1))
        resulting_custom_enabled = current_custom_enabled
        if payload.get("custom_recharge_rate_enabled") is not None:
            resulting_custom_enabled = bool(int(payload["custom_recharge_rate_enabled"]))
        custom_rate_supplied = "custom_recharge_rate" in payload and payload.get("custom_recharge_rate") is not None
        if custom_rate_supplied and not resulting_custom_enabled:
            raise ServiceException(403, "当前代理未开通自定义充值比例权限", "AGENT_CUSTOM_RECHARGE_RATE_FORBIDDEN")
        if custom_rate_supplied or (resulting_custom_enabled and not current_custom_enabled):
            candidate_rate = payload.get("custom_recharge_rate") if custom_rate_supplied else getattr(agent, "custom_recharge_rate", None)
            payload["custom_recharge_rate"] = AgentService.validate_custom_recharge_rate(candidate_rate)

        if payload.get("agent_code") and payload["agent_code"] != agent.agent_code:
            duplicate = db.query(Agent).filter(Agent.agent_code == payload["agent_code"]).first()
            if duplicate:
                raise ServiceException(400, "代理编码已存在", "DUPLICATE_AGENT_CODE")

        resulting_domains = {
            value
            for value in (
                payload.get("frontend_domain", agent.frontend_domain),
                payload.get("api_domain", agent.api_domain),
            )
            if value
        }
        if resulting_domains:
            duplicate_domain = (
                db.query(Agent)
                .filter(
                    Agent.id != agent.id,
                    or_(
                        Agent.frontend_domain.in_(resulting_domains),
                        Agent.api_domain.in_(resulting_domains),
                    ),
                )
                .first()
            )
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
        if "online_recharge_enabled" in payload and payload["online_recharge_enabled"] is not None:
            agent.online_recharge_enabled = int(payload["online_recharge_enabled"])
        if "subscription_online_recharge_enabled" in payload and payload["subscription_online_recharge_enabled"] is not None:
            agent.subscription_online_recharge_enabled = int(payload["subscription_online_recharge_enabled"])
        if "custom_recharge_rate_enabled" in payload and payload["custom_recharge_rate_enabled"] is not None:
            agent.custom_recharge_rate_enabled = int(payload["custom_recharge_rate_enabled"])
        if custom_rate_supplied:
            agent.custom_recharge_rate = payload["custom_recharge_rate"]

        if "owner_user_id" in payload and payload.get("owner_user_id") is not None:
            owner = db.query(SysUser).filter(SysUser.id == payload["owner_user_id"]).first()
            if not owner:
                raise ServiceException(404, "代理主账号不存在", "OWNER_USER_NOT_FOUND")
            if owner.role == "admin":
                raise ServiceException(400, "管理员账号不能绑定为代理主账号", "INVALID_AGENT_OWNER")
            owner.role = "agent"
            owner.agent_id = agent.id
            agent.owner_user_id = owner.id

        updated_custom_enabled = bool(getattr(agent, "custom_recharge_rate_enabled", 0))
        updated_custom_rate = Decimal(str(getattr(agent, "custom_recharge_rate", None) or AgentService.get_default_custom_recharge_rate()))
        updated_subscription_enabled = bool(getattr(agent, "subscription_online_recharge_enabled", 1))
        try:
            if audit_context is not None and audit_context.source == "admin" and current_custom_enabled != updated_custom_enabled:
                AgentService._append_pricing_audit_log(
                    db,
                    audit_context,
                    int(agent.id),
                    "update_agent_recharge_pricing_permission",
                    {
                        "custom_recharge_rate_enabled_before": current_custom_enabled,
                        "custom_recharge_rate_enabled_after": updated_custom_enabled,
                        "custom_recharge_rate": float(updated_custom_rate),
                    },
                )
            elif audit_context is not None and audit_context.source == "agent":
                changes = {}
                if current_custom_rate != updated_custom_rate:
                    changes["custom_recharge_rate"] = {
                        "before": float(current_custom_rate),
                        "after": float(updated_custom_rate),
                    }
                if current_subscription_enabled != updated_subscription_enabled:
                    changes["subscription_online_recharge_enabled"] = {
                        "before": current_subscription_enabled,
                        "after": updated_subscription_enabled,
                    }
                if changes:
                    AgentService._append_pricing_audit_log(
                        db,
                        audit_context,
                        int(agent.id),
                        "update_agent_recharge_pricing",
                        {"changes": changes},
                    )
            db.commit()
        except Exception:
            db.rollback()
            raise
        from app.core.cors import invalidate_dynamic_origin_cache
        invalidate_dynamic_origin_cache()
        db.refresh(agent)
        return AgentService.get_agent(db, agent.id)

    @staticmethod
    def update_agent_site_config(
        db: Session,
        agent_id: int,
        data,
        audit_context: Optional[AgentAuditContext] = None,
    ) -> dict:
        allowed_fields = {
            "site_title",
            "site_subtitle",
            "announcement_title",
            "announcement_content",
            "support_wechat",
            "support_qq",
            "allow_self_register",
            "subscription_online_recharge_enabled",
            "custom_recharge_rate",
            "theme_config_json",
        }
        raw_payload = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        payload = {key: value for key, value in raw_payload.items() if key in allowed_fields}
        return AgentService.update_agent(db, agent_id, payload, audit_context=audit_context)

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
