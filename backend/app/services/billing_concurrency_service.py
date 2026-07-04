"""Per-user billing concurrency guards for low-asset requests."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.core.exceptions import ServiceException
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BillingAdmissionDecision:
    """Request admission metadata used to decide whether a concurrency lease is needed."""

    user_id: int
    limited: bool
    limit: int = 3
    reason: Optional[str] = None
    balance: Decimal = Decimal("0")
    active_subscription_id: Optional[int] = None
    quota_metric: Optional[str] = None
    quota_remaining_amount: Optional[Decimal] = None


@dataclass(frozen=True)
class BillingConcurrencyLease:
    """Acquired Redis lease for one in-flight request."""

    user_id: int
    request_id: str
    key: str
    limit: int


class BillingConcurrencyService:
    """Redis-backed per-user concurrency limiter for requests that need billing protection."""

    DEFAULT_LIMIT = 3
    DEFAULT_TTL_SECONDS = 7200
    KEY_PREFIX = "billing_concurrency:user"

    _ACQUIRE_SCRIPT = """
local key = KEYS[1]
local member = ARGV[1]
local now = tonumber(ARGV[2])
local expires_at = tonumber(ARGV[3])
local limit = tonumber(ARGV[4])
local key_ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
local current = redis.call('ZCARD', key)
if current >= limit then
    return {0, current}
end
redis.call('ZADD', key, expires_at, member)
redis.call('EXPIRE', key, key_ttl)
return {1, current + 1}
"""

    @classmethod
    def _key(cls, user_id: int) -> str:
        return f"{cls.KEY_PREFIX}:{int(user_id)}"

    @classmethod
    def acquire(
        cls,
        *,
        user_id: int,
        request_id: str,
        limit: int = DEFAULT_LIMIT,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> BillingConcurrencyLease:
        """Acquire one concurrency slot or raise when the user is already at the limit."""
        normalized_limit = max(1, int(limit or cls.DEFAULT_LIMIT))
        normalized_ttl = max(30, int(ttl_seconds or cls.DEFAULT_TTL_SECONDS))
        client = getattr(redis_client, "client", None)
        if not client:
            raise ServiceException(
                503,
                "计费并发保护暂不可用，请稍后重试",
                "BILLING_CONCURRENCY_UNAVAILABLE",
            )

        key = cls._key(user_id)
        now = int(time.time())
        expires_at = now + normalized_ttl
        try:
            acquired, current = client.eval(
                cls._ACQUIRE_SCRIPT,
                1,
                key,
                str(request_id),
                now,
                expires_at,
                normalized_limit,
                normalized_ttl + 60,
            )
        except ServiceException:
            raise
        except Exception as exc:
            logger.warning(
                "Billing concurrency acquire failed: user_id=%s request_id=%s error=%s",
                user_id,
                request_id,
                exc,
            )
            raise ServiceException(
                503,
                "计费并发保护暂不可用，请稍后重试",
                "BILLING_CONCURRENCY_UNAVAILABLE",
            ) from exc

        if int(acquired or 0) != 1:
            logger.info(
                "Billing concurrency limited: user_id=%s request_id=%s active=%s limit=%s",
                user_id,
                request_id,
                current,
                normalized_limit,
            )
            raise ServiceException(
                429,
                "当前余额或套餐额度较低，同时请求较多，请等待前面的请求完成后重试",
                "BILLING_CONCURRENCY_LIMITED",
            )

        return BillingConcurrencyLease(
            user_id=int(user_id),
            request_id=str(request_id),
            key=key,
            limit=normalized_limit,
        )

    @classmethod
    def acquire_if_needed(
        cls,
        decision: Optional[BillingAdmissionDecision],
        request_id: str,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Optional[BillingConcurrencyLease]:
        """Acquire a lease only when admission decision requires low-asset limiting."""
        if not decision or not decision.limited:
            return None
        return cls.acquire(
            user_id=decision.user_id,
            request_id=request_id,
            limit=decision.limit,
            ttl_seconds=ttl_seconds,
        )

    @classmethod
    def release(cls, lease: Optional[BillingConcurrencyLease]) -> None:
        """Release a previously acquired lease."""
        if not lease:
            return
        client = getattr(redis_client, "client", None)
        if not client:
            logger.warning(
                "Billing concurrency release skipped because Redis is unavailable: user_id=%s request_id=%s",
                lease.user_id,
                lease.request_id,
            )
            return
        try:
            client.zrem(lease.key, lease.request_id)
        except Exception as exc:
            logger.warning(
                "Billing concurrency release failed: user_id=%s request_id=%s error=%s",
                lease.user_id,
                lease.request_id,
                exc,
            )
