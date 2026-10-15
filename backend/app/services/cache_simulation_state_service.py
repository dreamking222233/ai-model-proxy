"""Redis state delivery with short reservations and explicit failure results."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.redis_client import redis_client


def canonical_json(value: Any) -> str:
    def serialize(item):
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError(f"Unsupported snapshot type: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=serialize)


@dataclass(frozen=True)
class StateResult:
    status: str
    state: dict | None = None
    now: float = 0
    reservation: dict | None = None


_LOAD = """
local t = redis.call('TIME')
return {redis.call('GET', KEYS[1]) or '', t[1], t[2]}
"""
_RESERVE = """
local memo = redis.call('GET', KEYS[3])
if memo then return {'duplicate', memo} end
local old = redis.call('GET', KEYS[1])
local rev = 0
local window = ''
if old then
  local state = cjson.decode(old)
  rev = state.revision
  window = state.window_id or ''
end
if rev ~= tonumber(ARGV[1]) then return {'conflict', ''} end
if window ~= ARGV[5] then return {'conflict', ''} end
local existing = redis.call('GET', KEYS[2])
if existing then return {'busy', ''} end
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
if tonumber(ARGV[4]) <= now then return {'expired', ''} end
redis.call('SET', KEYS[2], ARGV[2], 'PX', ARGV[3])
return {'reserved', ''}
"""
_COMMIT = """
local memo = redis.call('GET', KEYS[3])
if memo then
  if cjson.decode(memo).decision_hash == ARGV[2] then return 'committed' end
  return 'conflict'
end
local lease = redis.call('GET', KEYS[2])
if not lease then return 'lost' end
local r = cjson.decode(lease)
if r.fence ~= ARGV[1] or r.proposed_hash ~= ARGV[3] then return 'lost' end
local old = redis.call('GET', KEYS[1])
local rev = 0
local window = ''
if old then
  local state = cjson.decode(old)
  rev = state.revision
  window = state.window_id or ''
end
if rev ~= r.base_revision then return 'lost' end
if window ~= (r.base_window_id or '') then return 'lost' end
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
if tonumber(ARGV[5]) <= now then return 'lost' end
redis.call('SET', KEYS[1], ARGV[4])
redis.call('PEXPIREAT', KEYS[1], math.floor(tonumber(ARGV[5]) * 1000))
redis.call('SET', KEYS[3], cjson.encode({decision_hash=ARGV[2],revision=rev+1}), 'EX', 86400)
redis.call('DEL', KEYS[2])
return 'committed'
"""
_RELEASE = """
local r = redis.call('GET', KEYS[1])
if r and cjson.decode(r).fence == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""
_VALIDATE = """
local lease = redis.call('GET', KEYS[2])
if not lease or redis.call('PTTL', KEYS[2]) <= 0 then return 'expired' end
local r = cjson.decode(lease)
if r.fence ~= ARGV[1] or r.proposed_hash ~= ARGV[2] then return 'conflict' end
local old = redis.call('GET', KEYS[1])
local rev = 0
local window = ''
if old then
  local state = cjson.decode(old)
  rev = state.revision
  window = state.window_id or ''
end
if rev ~= r.base_revision or window ~= (r.base_window_id or '') then return 'conflict' end
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
if tonumber(ARGV[3]) <= now then return 'expired' end
return 'valid'
"""


class CacheSimulationStateService:
    LEASE_MS = 30000
    INDEX_LIMIT = 64

    def __init__(self, client=None):
        self.client = client if client is not None else redis_client.client

    @staticmethod
    def keys(digest: str, request_id: str = "") -> list[str]:
        root = "cache_sim:v1:{" + digest + "}:"
        return [root + "state", root + "reservation", root + "memo:" + request_id]

    def load(self, digest: str) -> StateResult:
        if self.client is None:
            return StateResult("unavailable")
        try:
            raw, seconds, micros = self.client.eval(_LOAD, 1, self.keys(digest)[0])
            state = json.loads(raw) if raw else None
            return StateResult("ok" if state else "missing", state, int(seconds) + int(micros) / 1000000)
        except Exception:
            return StateResult("unavailable")

    def reserve(self, digest: str, request_id: str, expected_revision: int, proposed: dict,
                *, expected_window_id: str | None = None) -> StateResult:
        proposed_json = canonical_json(proposed)
        reservation = {"request_id": request_id, "fence": str(uuid.uuid4()),
                       "base_revision": expected_revision,
                       "base_window_id": expected_window_id or "",
                       "proposed_hash": hashlib.sha256(proposed_json.encode()).hexdigest()}
        if self.client is None:
            return StateResult("unavailable")
        try:
            status, _ = self.client.eval(_RESERVE, 3, *self.keys(digest, request_id),
                                        expected_revision, canonical_json(reservation), self.LEASE_MS,
                                        proposed["expires_at"], expected_window_id or "")
            return StateResult(status, reservation=reservation if status == "reserved" else None)
        except Exception:
            return StateResult("unavailable")

    def commit(self, digest: str, request_id: str, reservation: dict,
               proposed: dict, decision_hash: str) -> str:
        if self.client is None:
            return "unavailable"
        try:
            return self.client.eval(_COMMIT, 3, *self.keys(digest, request_id),
                                    reservation["fence"], decision_hash, reservation["proposed_hash"],
                                    canonical_json(proposed), proposed["expires_at"])
        except Exception:
            return "unavailable"

    def release(self, digest: str, reservation: dict | None) -> None:
        if self.client is not None and reservation:
            try:
                self.client.eval(_RELEASE, 1, self.keys(digest)[1], reservation["fence"])
            except Exception:
                pass

    def validate_reservation(self, digest: str, reservation: dict, proposed: dict) -> str:
        """Validate the live fence and window immediately before freezing prepared."""
        if self.client is None:
            return "unavailable"
        try:
            return self.client.eval(_VALIDATE, 2, *self.keys(digest)[:2],
                                    reservation["fence"], reservation["proposed_hash"], proposed["expires_at"])
        except Exception:
            return "unavailable"

    def reservation_status(self, digest: str) -> str:
        if self.client is None:
            return "unavailable"
        try:
            return "live" if self.client.exists(self.keys(digest)[1]) else "missing"
        except Exception:
            return "unavailable"

    def candidates(self, scope: str) -> list[str] | None:
        if self.client is None:
            return None
        try:
            return self.client.zrevrange("cache_sim:v1:index:" + scope, 0, self.INDEX_LIMIT)
        except Exception:
            return None

    def index(self, scope: str, digest: str, expires_at: float) -> None:
        if self.client is None:
            return
        try:
            key = "cache_sim:v1:index:" + scope
            now = float(self.client.time()[0])
            with self.client.pipeline() as pipe:
                pipe.zremrangebyscore(key, "-inf", now)
                pipe.zadd(key, {digest: expires_at})
                # Keep one overflow sentinel; matching a truncated candidate set is unsafe.
                pipe.zremrangebyrank(key, 0, -self.INDEX_LIMIT - 2)
                # This is an index, not the session's fixed cache window.
                pipe.expire(key, 86460)
                pipe.execute()
        except Exception:
            pass

    def parent(self, scope: str, parent_digest: str) -> dict | None:
        if self.client is None:
            return None
        try:
            raw = self.client.get("cache_sim:v1:response:" + scope + ":" + parent_digest)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def remember_response(self, scope: str, response_digest: str, digest: str, revision: int,
                          fingerprint: str, expires_at: float, window_id: str) -> None:
        if self.client is None:
            return
        try:
            now = float(self.client.time()[0])
            remaining = int(expires_at - now)
            if remaining > 0:
                self.client.set("cache_sim:v1:response:" + scope + ":" + response_digest,
                                canonical_json({"digest": digest, "revision": revision,
                                                "window_id": window_id, "fingerprint": fingerprint}), ex=remaining)
        except Exception:
            pass
