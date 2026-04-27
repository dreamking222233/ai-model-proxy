"""FastAPI dependencies for authentication and authorization."""
from __future__ import annotations

from typing import Optional

import hashlib
from datetime import datetime

from fastapi import Depends, Header, Request
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser, UserApiKey
from app.core.security import verify_token
from app.core.exceptions import ServiceException
from app.services.agent_service import AgentService, AgentSiteContext


def get_request_site_kwargs(request: Request) -> dict:
    """Collect request headers used for tenant/site resolution."""
    return {
        "host": request.headers.get("host"),
        "x_site_host": request.headers.get("X-Site-Host"),
        "origin": request.headers.get("Origin"),
        "referer": request.headers.get("Referer"),
    }


def get_current_user(
    request: Request,
    authorization: str = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> SysUser:
    """
    Extract and validate JWT token from the Authorization header.
    Expected format: "Bearer <token>"
    Returns the authenticated SysUser.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise ServiceException(status_code=401, detail="缺少授权信息或授权头格式错误", error_code="UNAUTHORIZED")

    token = authorization[7:]

    # If it looks like an API key, reject it here - use verify_api_key instead
    if token.startswith("sk-"):
        raise ServiceException(status_code=401, detail="当前接口不接受 API Key，请使用登录后的 JWT", error_code="UNAUTHORIZED")

    try:
        payload = verify_token(token)
    except JWTError:
        raise ServiceException(status_code=401, detail="登录凭证无效或已过期", error_code="UNAUTHORIZED")

    user_id = payload.get("sub")
    if user_id is None:
        raise ServiceException(status_code=401, detail="登录凭证内容无效", error_code="UNAUTHORIZED")

    user = db.query(SysUser).filter(SysUser.id == int(user_id)).first()
    if user is None:
        raise ServiceException(status_code=401, detail="用户不存在", error_code="UNAUTHORIZED")

    if user.status != 1:
        raise ServiceException(status_code=403, detail="账号已被禁用", error_code="FORBIDDEN")

    context = AgentService.assert_user_matches_site(db, user, **get_request_site_kwargs(request))
    request.state.agent_site_context = context

    return user


def require_admin(
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    """Ensure the current user has admin role."""
    if current_user.role != "admin":
        raise ServiceException(status_code=403, detail="需要管理员权限", error_code="FORBIDDEN")
    return current_user


def require_platform_admin(
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    """Compatibility alias for platform admin-only endpoints."""
    return require_admin(current_user)


def get_current_agent_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AgentSiteContext:
    """Resolve the current site/agent from the request host."""
    cached = getattr(request.state, "agent_site_context", None)
    if cached is not None:
        return cached
    context = AgentService.get_site_context_from_request(db, **get_request_site_kwargs(request))
    request.state.agent_site_context = context
    return context


def require_agent_user(
    current_user: SysUser = Depends(get_current_user),
    agent_context: AgentSiteContext = Depends(get_current_agent_context),
) -> SysUser:
    """Require a user that belongs to the current agent site."""
    if agent_context.site_scope != "agent" or not agent_context.agent_id:
        raise ServiceException(status_code=403, detail="当前站点不是代理站点", error_code="AGENT_SITE_REQUIRED")
    if not current_user.agent_id or int(current_user.agent_id) != int(agent_context.agent_id):
        raise ServiceException(status_code=403, detail="代理归属与当前站点不匹配", error_code="AGENT_SITE_MISMATCH")
    return current_user


def require_agent_admin(
    current_user: SysUser = Depends(get_current_user),
    agent_context: AgentSiteContext = Depends(get_current_agent_context),
) -> SysUser:
    """Require an agent operator on the current agent site."""
    if current_user.role != "agent":
        raise ServiceException(status_code=403, detail="需要代理权限", error_code="FORBIDDEN")
    return require_agent_user(current_user, agent_context)


def assert_user_in_agent_scope(user: SysUser, agent_id: Optional[int]) -> None:
    """Assert the target user belongs to the expected agent."""
    if agent_id is None:
        raise ServiceException(status_code=403, detail="缺少代理上下文", error_code="AGENT_SITE_REQUIRED")
    if int(user.agent_id or 0) != int(agent_id):
        raise ServiceException(status_code=403, detail="目标用户不在当前代理范围内", error_code="AGENT_SCOPE_VIOLATION")


def _extract_api_key_value(
    authorization: Optional[str],
    x_api_key: Optional[str],
    anthropic_api_key: Optional[str] = None,
) -> Optional[str]:
    """Extract an ``sk-`` API key from supported header values."""
    api_key_value: Optional[str] = None

    # Check anthropic-api-key header first (standard Anthropic format)
    if anthropic_api_key and anthropic_api_key.startswith("sk-"):
        api_key_value = anthropic_api_key

    # Check X-API-Key header
    if not api_key_value and x_api_key and x_api_key.startswith("sk-"):
        api_key_value = x_api_key

    # Fallback to Authorization: Bearer sk-xxx
    if not api_key_value:
        if authorization and authorization.startswith("Bearer sk-"):
            api_key_value = authorization[7:]

    return api_key_value


def verify_api_key_from_headers(
    db: Session,
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    host: Optional[str] = None,
    x_site_host: Optional[str] = None,
    origin: Optional[str] = None,
    referer: Optional[str] = None,
) -> tuple[SysUser, UserApiKey]:
    """
    Verify an API key from header values.

    Checks ``anthropic-api-key``, ``Authorization: Bearer sk-xxx``, and ``X-API-Key: sk-xxx``
    headers and returns the owning user plus the API key record.
    """
    api_key_value = _extract_api_key_value(authorization, x_api_key, anthropic_api_key)

    if not api_key_value:
        import logging
        _log = logging.getLogger(__name__)
        _log.warning("verify_api_key: no sk- key found. Authorization=%r X-API-Key=%r anthropic-api-key=%r",
                     authorization or "", x_api_key or "", anthropic_api_key or "")
        raise ServiceException(status_code=401, detail="缺少 API Key", error_code="UNAUTHORIZED")

    # Look up by SHA256 hash
    key_hash = hashlib.sha256(api_key_value.encode("utf-8")).hexdigest()
    api_key_record = db.query(UserApiKey).filter(UserApiKey.key_hash == key_hash).first()

    if api_key_record is None:
        raise ServiceException(status_code=401, detail="API Key 无效", error_code="UNAUTHORIZED")

    if api_key_record.status != "active":
        raise ServiceException(status_code=401, detail="API Key 未启用", error_code="UNAUTHORIZED")

    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        raise ServiceException(status_code=401, detail="API Key 已过期", error_code="UNAUTHORIZED")

    # Look up the owning user
    user = db.query(SysUser).filter(SysUser.id == api_key_record.user_id).first()
    if user is None:
        raise ServiceException(status_code=401, detail="API Key 所属用户不存在", error_code="UNAUTHORIZED")

    if user.status != 1:
        raise ServiceException(status_code=403, detail="账号已被禁用", error_code="FORBIDDEN")

    AgentService.assert_user_matches_site(
        db,
        user,
        host=host,
        x_site_host=x_site_host,
        origin=origin,
        referer=referer,
    )

    # Refresh cached subscription state before the request layer makes balance/quota decisions.
    if user.subscription_type in {"unlimited", "quota"} or bool(user.subscription_expires_at):
        from app.services.subscription_service import SubscriptionService

        SubscriptionService.refresh_user_subscription_state(
            db,
            user.id,
            SubscriptionService.get_current_time(),
        )
        db.commit()
        db.refresh(user)

    return user, api_key_record


async def verify_api_key(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[SysUser, UserApiKey]:
    """
    Verify an API key from request headers.
    Checks "anthropic-api-key", "Authorization: Bearer sk-xxx", and "X-API-Key: sk-xxx" headers.
    Returns the owning SysUser and the UserApiKey record.
    """
    return verify_api_key_from_headers(
        db,
        authorization=request.headers.get("Authorization"),
        x_api_key=request.headers.get("X-API-Key"),
        anthropic_api_key=request.headers.get("anthropic-api-key"),
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
