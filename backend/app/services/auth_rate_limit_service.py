"""Rate limiting helpers for authentication endpoints."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.exceptions import ServiceException
from app.core.redis_client import redis_client


class AuthRateLimitService:
    """Small fixed-window limiter backed by Redis with in-process fallback."""

    _memory_buckets: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _normalize_part(value: str | None) -> str:
        return str(value or "").strip().lower()[:128] or "unknown"

    @classmethod
    def build_key(cls, action: str, client_ip: str | None, subject: str | None = None) -> str:
        parts = [
            cls._normalize_part(action),
            cls._normalize_part(client_ip),
            cls._normalize_part(subject),
        ]
        return ":".join(parts)

    @classmethod
    def check(cls, key: str, *, limit: int, window_seconds: int) -> None:
        if limit <= 0 or window_seconds <= 0:
            return
        redis_key = f"auth_rate:{key}"
        client = getattr(redis_client, "client", None)
        if client:
            try:
                current = int(client.incr(redis_key))
                if current == 1:
                    client.expire(redis_key, window_seconds)
                if current > limit:
                    raise ServiceException(429, "请求过于频繁，请稍后再试", "RATE_LIMITED")
                return
            except ServiceException:
                raise
            except Exception:
                pass

        now = time.time()
        bucket = cls._memory_buckets[redis_key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise ServiceException(429, "请求过于频繁，请稍后再试", "RATE_LIMITED")
        bucket.append(now)
