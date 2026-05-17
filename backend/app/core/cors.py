"""Dynamic CORS allowlist for shared API and custom agent domains."""
from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.database import session_scope
from app.models.agent import Agent

logger = logging.getLogger(__name__)


def _normalize_host(raw_host: Optional[str]) -> str:
    host = str(raw_host or "").strip().lower()
    if not host or host in {"null", "undefined"}:
        return ""
    if host.startswith("[") and "]" in host:
        host = host[1:].split("]", 1)[0]
        return host
    return host.split(":", 1)[0]


def _extract_host_from_url(raw_value: Optional[str]) -> str:
    value = str(raw_value or "").strip()
    if not value or value.lower() in {"null", "undefined"}:
        return ""
    parsed = urlparse(value if "://" in value else f"//{value}")
    return _normalize_host(parsed.netloc or parsed.path)


def _append_vary_header(response: Response, header_name: str) -> None:
    current = response.headers.get("Vary", "")
    values = [item.strip() for item in current.split(",") if item.strip()]
    if header_name not in values:
        values.append(header_name)
        response.headers["Vary"] = ", ".join(values)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Allow custom agent frontend domains to call the shared API domain."""

    ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    _cached_agent_frontend_domains: set[str] = set()
    _cache_expires_at: float = 0.0

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cached_agent_frontend_domains = set()
        cls._cache_expires_at = 0.0

    @classmethod
    def _matches_static_origin(cls, host: str) -> bool:
        normalized = _normalize_host(host)
        if not normalized:
            return False

        platform_frontends = {_normalize_host(item) for item in settings.PLATFORM_FRONTEND_HOSTS}
        platform_apis = {_normalize_host(item) for item in settings.PLATFORM_API_HOSTS}
        configured_origins = {_extract_host_from_url(item) for item in settings.CORS_ORIGINS}

        if normalized in platform_frontends or normalized in platform_apis or normalized in configured_origins:
            return True

        if normalized in {"localhost", "127.0.0.1"} or normalized.endswith(".localhost") or normalized.endswith(".local"):
            return True

        pattern = str(settings.CORS_ORIGIN_REGEX or "").strip()
        return bool(pattern and re.match(pattern, f"https://{normalized}"))

    @classmethod
    def _load_agent_frontend_domains(cls) -> set[str]:
        with session_scope() as db:
            rows = (
                db.query(Agent.frontend_domain)
                .filter(
                    Agent.status == "active",
                    Agent.frontend_domain.isnot(None),
                    Agent.frontend_domain != "",
                )
                .all()
            )
        return {_normalize_host(row[0]) for row in rows if _normalize_host(row[0])}

    @classmethod
    def _get_cached_agent_frontend_domains(cls) -> set[str]:
        now = time.time()
        if now < cls._cache_expires_at:
            return cls._cached_agent_frontend_domains

        ttl_seconds = max(int(getattr(settings, "DYNAMIC_CORS_CACHE_TTL_SECONDS", 300) or 300), 30)
        try:
            cls._cached_agent_frontend_domains = cls._load_agent_frontend_domains()
        except Exception as exc:
            logger.warning("Failed to refresh dynamic CORS agent domains: %s", exc)
        cls._cache_expires_at = now + ttl_seconds
        return cls._cached_agent_frontend_domains

    @classmethod
    def is_origin_allowed(cls, raw_origin: Optional[str]) -> bool:
        host = _extract_host_from_url(raw_origin)
        if not host:
            return False
        if cls._matches_static_origin(host):
            return True
        return host in cls._get_cached_agent_frontend_domains()

    @classmethod
    def _apply_cors_headers(cls, response: Response, request: Request, origin: str) -> None:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = cls.ALLOW_METHODS
        response.headers["Access-Control-Allow-Headers"] = request.headers.get("Access-Control-Request-Headers", "*")
        response.headers["Access-Control-Max-Age"] = "600"
        _append_vary_header(response, "Origin")

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = str(request.headers.get("Origin") or "").strip()
        is_preflight = request.method.upper() == "OPTIONS" and bool(request.headers.get("Access-Control-Request-Method"))

        if origin and is_preflight:
            if not self.is_origin_allowed(origin):
                return Response(status_code=400)
            response = Response(status_code=204)
            self._apply_cors_headers(response, request, origin)
            return response

        response = await call_next(request)
        if origin and self.is_origin_allowed(origin):
            self._apply_cors_headers(response, request, origin)
        return response


def invalidate_dynamic_origin_cache() -> None:
    DynamicCORSMiddleware.invalidate_cache()
