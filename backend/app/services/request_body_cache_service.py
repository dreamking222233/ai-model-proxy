"""Redis-backed request-body segment cache analysis service."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.core.redis_client import redis_client
from app.services.health_service import get_system_config
from app.services.request_body_cache_analyzer import RequestBodyCacheAnalyzer

logger = logging.getLogger(__name__)


class RequestBodyCacheService:
    """Analyze request payload segments and record Redis cache reads/creates."""

    KEY_PREFIX = "req-body-cache:v1"

    @staticmethod
    def _get_request_format_aliases(request_format: str) -> set[str]:
        """Return equivalent config aliases for a request format."""
        aliases = {request_format}
        if request_format == "anthropic_messages":
            aliases.add("anthropic")
        elif request_format == "openai_chat":
            aliases.add("openai")
        return aliases

    @staticmethod
    def _parse_enabled_formats(value: Any) -> set[str]:
        """Parse comma-separated request format config."""
        if not value:
            return set()
        return {
            str(item).strip()
            for item in str(value).split(",")
            if str(item).strip()
        }

    @staticmethod
    def _build_segment_cache_key(
        user_id: int,
        request_format: str,
        segment_type: str,
        segment_hash: str,
    ) -> str:
        """Build a Redis key for one cache segment."""
        return (
            f"{RequestBodyCacheService.KEY_PREFIX}:user:{user_id}:"
            f"format:{request_format}:segment:{segment_type}:{segment_hash}"
        )

    @staticmethod
    def _build_bypass_info(
        request_format: str,
        reason: str,
        *,
        user_visible: bool = False,
    ) -> dict[str, Any]:
        """Return a normalized bypass summary."""
        return {
            "cache_enabled": False,
            "user_visible": bool(user_visible),
            "request_format": request_format,
            "cache_status": "BYPASS",
            "reason": reason,
            "hit_segments": 0,
            "miss_segments": 0,
            "bypass_segments": 0,
            "reused_estimated_tokens": 0,
            "new_estimated_tokens": 0,
            "reused_chars": 0,
            "new_chars": 0,
            "ttl_seconds": 0,
            "details": {
                "reason": reason,
                "request_format": request_format,
            },
        }

    @staticmethod
    def analyze_request(
        db: Session,
        user_id: int,
        request_body: dict[str, Any],
        request_format: str,
        requested_model: str,
    ) -> dict[str, Any]:
        """Analyze request segments and create/read Redis entries without changing payload."""
        user_visible = bool(get_system_config(db, "request_body_cache_user_visible", False))
        enabled = bool(get_system_config(db, "request_body_cache_enabled", False))
        if not enabled:
            return RequestBodyCacheService._build_bypass_info(
                request_format,
                "disabled",
                user_visible=user_visible,
            )

        enabled_formats = RequestBodyCacheService._parse_enabled_formats(
            get_system_config(
                db,
                "request_body_cache_formats",
                "anthropic_messages,openai_chat,responses",
            )
        )
        format_aliases = RequestBodyCacheService._get_request_format_aliases(request_format)
        if enabled_formats and enabled_formats.isdisjoint(format_aliases):
            return RequestBodyCacheService._build_bypass_info(
                request_format,
                "format_not_enabled",
                user_visible=user_visible,
            )

        if not redis_client.client:
            return RequestBodyCacheService._build_bypass_info(
                request_format,
                "redis_unavailable",
                user_visible=user_visible,
            )

        ttl_seconds = int(get_system_config(db, "request_body_cache_ttl_seconds", 1800) or 1800)
        min_chars = int(get_system_config(db, "request_body_cache_min_chars", 256) or 256)
        segments = RequestBodyCacheAnalyzer.extract_segments(request_body, request_format)
        if not segments:
            return RequestBodyCacheService._build_bypass_info(
                request_format,
                "no_segments",
                user_visible=user_visible,
            )

        hit_segments = 0
        miss_segments = 0
        bypass_segments = 0
        reused_tokens = 0
        new_tokens = 0
        reused_chars = 0
        new_chars = 0
        by_type: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "hit_segments": 0,
                "miss_segments": 0,
                "bypass_segments": 0,
                "reused_tokens": 0,
                "new_tokens": 0,
                "reused_chars": 0,
                "new_chars": 0,
            }
        )
        segment_samples = []
        now_ts = int(time.time())

        for segment in segments:
            segment_type = str(segment["segment_type"])
            segment_size_chars = int(segment["size_chars"])
            segment_tokens = int(segment["estimated_tokens"])
            status = "BYPASS"

            if segment_size_chars < min_chars:
                bypass_segments += 1
                by_type[segment_type]["bypass_segments"] += 1
            else:
                redis_key = RequestBodyCacheService._build_segment_cache_key(
                    user_id,
                    request_format,
                    segment_type,
                    str(segment["hash"]),
                )
                cached_value = redis_client.get(redis_key)
                if cached_value:
                    status = "HIT"
                    hit_segments += 1
                    reused_tokens += segment_tokens
                    reused_chars += segment_size_chars
                    by_type[segment_type]["hit_segments"] += 1
                    by_type[segment_type]["reused_tokens"] += segment_tokens
                    by_type[segment_type]["reused_chars"] += segment_size_chars
                else:
                    status = "MISS"
                    miss_segments += 1
                    new_tokens += segment_tokens
                    new_chars += segment_size_chars
                    by_type[segment_type]["miss_segments"] += 1
                    by_type[segment_type]["new_tokens"] += segment_tokens
                    by_type[segment_type]["new_chars"] += segment_size_chars
                    payload = {
                        "segment_type": segment_type,
                        "request_format": request_format,
                        "requested_model": requested_model,
                        "payload": segment["payload"],
                        "size_chars": segment_size_chars,
                        "estimated_tokens": segment_tokens,
                        "created_at": now_ts,
                    }
                    if not redis_client.set(
                        redis_key,
                        json.dumps(payload, ensure_ascii=False),
                        ex=ttl_seconds,
                    ):
                        logger.warning("Failed to save request body cache segment: %s", redis_key)

            if len(segment_samples) < 12:
                segment_samples.append(
                    {
                        "segment_type": segment_type,
                        "scope": segment["scope"],
                        "status": status,
                        "size_chars": segment_size_chars,
                        "estimated_tokens": segment_tokens,
                        "preview": segment["preview"],
                    }
                )

        if hit_segments > 0 and miss_segments == 0:
            cache_status = "HIT"
        elif hit_segments > 0 and miss_segments > 0:
            cache_status = "PARTIAL"
        elif miss_segments > 0:
            cache_status = "MISS"
        else:
            cache_status = "BYPASS"

        duplicate_analysis = RequestBodyCacheAnalyzer.summarize_duplicate_segments(segments)
        details = {
            "request_format": request_format,
            "requested_model": requested_model,
            "segment_count": len(segments),
            "min_chars": min_chars,
            "ttl_seconds": ttl_seconds,
            "duplicate_analysis": duplicate_analysis,
            "by_type": dict(by_type),
            "segment_samples": segment_samples,
        }

        logger.info(
            "Request body cache analyzed: user=%s format=%s status=%s hits=%s misses=%s bypass=%s reused_tokens=%s new_tokens=%s",
            user_id,
            request_format,
            cache_status,
            hit_segments,
            miss_segments,
            bypass_segments,
            reused_tokens,
            new_tokens,
        )

        return {
            "cache_enabled": True,
            "user_visible": user_visible,
            "request_format": request_format,
            "cache_status": cache_status,
            "reason": None,
            "hit_segments": hit_segments,
            "miss_segments": miss_segments,
            "bypass_segments": bypass_segments,
            "reused_estimated_tokens": reused_tokens,
            "new_estimated_tokens": new_tokens,
            "reused_chars": reused_chars,
            "new_chars": new_chars,
            "ttl_seconds": ttl_seconds,
            "details": details,
        }
