"""JWT revocation helpers for single-token logout."""
from __future__ import annotations

import time

from app.core.redis_client import redis_client


class AuthTokenRevocationService:
    """Track revoked JWT ``jti`` values until their original expiry."""

    _memory_revoked: dict[str, float] = {}

    @staticmethod
    def _key(jti: str) -> str:
        return f"jwt_revoked:{jti}"

    @classmethod
    def revoke(cls, jti: str | None, expires_at: int | float | None) -> None:
        normalized_jti = str(jti or "").strip()
        if not normalized_jti:
            return

        now = time.time()
        expire_ts = float(expires_at or now)
        ttl = max(int(expire_ts - now), 1)
        key = cls._key(normalized_jti)
        if redis_client.set(key, "1", ex=ttl):
            cls._memory_revoked.pop(key, None)
            return
        cls._memory_revoked[key] = now + ttl

    @classmethod
    def is_revoked(cls, jti: str | None) -> bool:
        normalized_jti = str(jti or "").strip()
        if not normalized_jti:
            return False

        key = cls._key(normalized_jti)
        if redis_client.exists(key):
            return True

        expires_at = cls._memory_revoked.get(key)
        if not expires_at:
            return False
        if expires_at <= time.time():
            cls._memory_revoked.pop(key, None)
            return False
        return True
