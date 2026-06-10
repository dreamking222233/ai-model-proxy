"""Request-scoped channel affinity helpers.

The service keeps same-session text requests on the last successful channel
when that channel is still available. It does not cache model responses.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.user import SysUser
from app.services.health_service import get_system_config

logger = logging.getLogger(__name__)


@dataclass
class _AffinityEntry:
    channel_id: int
    expires_at: float
    updated_at: float
    hit_count: int = 0


class ChannelAffinityService:
    """In-memory TTL map from stable conversation keys to channel ids."""

    _cache: dict[str, _AffinityEntry] = {}
    _lock = threading.RLock()
    _MAX_CACHE_SIZE = 20000
    _DEFAULT_TTL_SECONDS = 3600
    _MIN_TTL_SECONDS = 60
    _MAX_TTL_SECONDS = 86400
    _MAX_FINGERPRINT_CHARS = 12000

    @classmethod
    def is_enabled(cls, db: Session) -> bool:
        return bool(get_system_config(db, "channel_affinity_enabled", True))

    @classmethod
    def is_fallback_enabled(cls, db: Session) -> bool:
        return bool(get_system_config(db, "channel_affinity_fallback_enabled", True))

    @classmethod
    def ttl_seconds(cls, db: Session) -> int:
        try:
            configured = int(
                get_system_config(db, "channel_affinity_ttl_seconds", cls._DEFAULT_TTL_SECONDS)
                or cls._DEFAULT_TTL_SECONDS
            )
        except (TypeError, ValueError):
            configured = cls._DEFAULT_TTL_SECONDS
        return max(cls._MIN_TTL_SECONDS, min(configured, cls._MAX_TTL_SECONDS))

    @classmethod
    def prioritize_channels(
        cls,
        db: Session,
        channels: list[tuple[Channel, str]],
        *,
        user: SysUser,
        requested_model: str,
        request_protocol: str,
        request_data: Optional[dict[str, Any]] = None,
        request_headers: Optional[dict[str, str]] = None,
    ) -> list[tuple[Channel, str]]:
        """Move the previously successful channel for this conversation to the front."""
        if not channels or not cls.is_enabled(db):
            return channels

        ttl_seconds = cls.ttl_seconds(db)
        affinity_key = cls.build_affinity_key(
            db,
            user=user,
            requested_model=requested_model,
            request_protocol=request_protocol,
            request_data=request_data,
            request_headers=request_headers,
        )
        if not affinity_key:
            return channels

        now = time.time()
        cls._prune(now)
        available_channel_ids = {
            int(getattr(channel, "id", 0) or 0)
            for channel, _actual_model in channels
            if getattr(channel, "id", None)
        }
        affinity_channel_id: Optional[int] = None
        with cls._lock:
            entry = cls._cache.get(affinity_key)
            if entry and entry.expires_at > now and entry.channel_id in available_channel_ids:
                entry.hit_count += 1
                affinity_channel_id = entry.channel_id
            elif entry and (entry.expires_at <= now or entry.channel_id not in available_channel_ids):
                cls._cache.pop(affinity_key, None)

        for channel, _actual_model in channels:
            setattr(channel, "_runtime_channel_affinity_key", affinity_key)
            setattr(channel, "_runtime_channel_affinity_enabled", True)
            setattr(channel, "_runtime_channel_affinity_ttl_seconds", ttl_seconds)

        if not affinity_channel_id:
            return channels

        logger.info(
            "Channel affinity hit user_id=%s model=%s protocol=%s channel_id=%s",
            getattr(user, "id", None),
            requested_model,
            request_protocol,
            affinity_channel_id,
        )
        return sorted(
            channels,
            key=lambda item: 0 if int(getattr(item[0], "id", 0) or 0) == affinity_channel_id else 1,
        )

    @classmethod
    def record_success(cls, channel: Channel) -> None:
        """Bind this request's affinity key to the successful channel."""
        affinity_key = getattr(channel, "_runtime_channel_affinity_key", None)
        if not affinity_key or not getattr(channel, "_runtime_channel_affinity_enabled", False):
            return

        channel_id = int(getattr(channel, "id", 0) or 0)
        if channel_id <= 0:
            return

        now = time.time()
        try:
            ttl_seconds = int(
                getattr(channel, "_runtime_channel_affinity_ttl_seconds", cls._DEFAULT_TTL_SECONDS)
                or cls._DEFAULT_TTL_SECONDS
            )
        except (TypeError, ValueError):
            ttl_seconds = cls._DEFAULT_TTL_SECONDS
        ttl_seconds = max(cls._MIN_TTL_SECONDS, min(ttl_seconds, cls._MAX_TTL_SECONDS))
        expires_at = now + ttl_seconds
        with cls._lock:
            cls._cache[affinity_key] = _AffinityEntry(
                channel_id=channel_id,
                expires_at=expires_at,
                updated_at=now,
            )
            if len(cls._cache) > cls._MAX_CACHE_SIZE:
                cls._prune_locked(now)

    @classmethod
    def build_affinity_key(
        cls,
        db: Session,
        *,
        user: SysUser,
        requested_model: str,
        request_protocol: str,
        request_data: Optional[dict[str, Any]] = None,
        request_headers: Optional[dict[str, str]] = None,
    ) -> Optional[str]:
        user_id = int(getattr(user, "id", 0) or 0)
        agent_id = int(getattr(user, "agent_id", 0) or 0)
        protocol = str(request_protocol or "").strip().lower() or "unknown"
        model = str(requested_model or "").strip()
        if not user_id or not model:
            return None

        explicit_source = cls._extract_explicit_session_source(request_data, request_headers)
        if explicit_source:
            source_name, source_value = explicit_source
        else:
            if not cls.is_fallback_enabled(db):
                return None
            source_name = "fallback"
            source_value = cls._build_fallback_fingerprint(request_data)
            if not source_value:
                return None

        digest = hashlib.sha256(str(source_value).encode("utf-8", errors="ignore")).hexdigest()
        return f"v1:{protocol}:{model}:agent:{agent_id}:user:{user_id}:{source_name}:{digest}"

    @classmethod
    def _extract_explicit_session_source(
        cls,
        request_data: Optional[dict[str, Any]],
        request_headers: Optional[dict[str, str]],
    ) -> Optional[tuple[str, str]]:
        body = request_data or {}
        for key in ("prompt_cache_key", "session_id", "conversation_id"):
            value = cls._clean_scalar(body.get(key))
            if value:
                return key, value

        metadata = body.get("metadata")
        if isinstance(metadata, dict):
            for key in ("prompt_cache_key", "session_id", "conversation_id", "user_id"):
                value = cls._clean_scalar(metadata.get(key))
                if value:
                    return f"metadata.{key}", value

        headers = {str(k).lower(): v for k, v in (request_headers or {}).items()}
        for key in (
            "x-prompt-cache-key",
            "prompt-cache-key",
            "x-session-id",
            "session-id",
            "session_id",
            "x-conversation-id",
            "conversation-id",
            "conversation_id",
        ):
            value = cls._clean_scalar(headers.get(key))
            if value:
                return f"header.{key}", value

        turn_metadata = headers.get("x-codex-turn-metadata")
        if isinstance(turn_metadata, str) and turn_metadata.strip():
            parsed = cls._loads_json_object(turn_metadata)
            if parsed:
                for key in ("prompt_cache_key", "session_id", "conversation_id", "user_id"):
                    value = cls._clean_scalar(parsed.get(key))
                    if value:
                        return f"codex_turn_metadata.{key}", value
        return None

    @classmethod
    def _build_fallback_fingerprint(cls, request_data: Optional[dict[str, Any]]) -> Optional[str]:
        body = request_data or {}
        messages = body.get("messages") if isinstance(body.get("messages"), list) else []
        first_user = None
        first_system = None
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").lower()
            if role == "system" and first_system is None:
                first_system = message.get("content")
            if role == "user" and first_user is None:
                first_user = message.get("content")
            if first_system is not None and first_user is not None:
                break

        fingerprint_payload = {
            key: value
            for key, value in {
                "system": body.get("system", first_system),
                "tools": body.get("tools"),
                "first_user": first_user,
            }.items()
            if value is not None
        }
        if not fingerprint_payload:
            return None
        serialized = cls._stable_json(fingerprint_payload)
        if serialized in {"{}", "null", ""}:
            return None
        return serialized[: cls._MAX_FINGERPRINT_CHARS]

    @staticmethod
    def _clean_scalar(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (dict, list, tuple, set)):
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _loads_json_object(value: str) -> Optional[dict[str, Any]]:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _stable_json(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _prune(cls, now: Optional[float] = None) -> None:
        now = now or time.time()
        with cls._lock:
            cls._prune_locked(now)

    @classmethod
    def _prune_locked(cls, now: float) -> None:
        expired_keys = [key for key, entry in cls._cache.items() if entry.expires_at <= now]
        for key in expired_keys:
            cls._cache.pop(key, None)
        if len(cls._cache) <= cls._MAX_CACHE_SIZE:
            return
        overflow = len(cls._cache) - cls._MAX_CACHE_SIZE
        oldest_keys = sorted(cls._cache, key=lambda key: cls._cache[key].updated_at)[:overflow]
        for key in oldest_keys:
            cls._cache.pop(key, None)
