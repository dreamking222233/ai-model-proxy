"""Persistence helpers for request-body cache summaries."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.log import RequestCacheSummary

logger = logging.getLogger(__name__)


class RequestCacheSummaryService:
    """Convert cache_info into request-log fields and persist detailed summaries."""

    @staticmethod
    def build_request_log_fields(cache_info: dict[str, Any] | None) -> dict[str, Any]:
        """Build request_log column values from a cache summary."""
        if not cache_info:
            return {
                "cache_status": None,
                "cache_hit_segments": 0,
                "cache_miss_segments": 0,
                "cache_bypass_segments": 0,
                "cache_reused_tokens": 0,
                "cache_new_tokens": 0,
                "cache_reused_chars": 0,
                "cache_new_chars": 0,
                "logical_input_tokens": 0,
                "upstream_input_tokens": 0,
                "upstream_cache_read_input_tokens": 0,
                "upstream_cache_creation_input_tokens": 0,
                "upstream_cache_creation_5m_input_tokens": 0,
                "upstream_cache_creation_1h_input_tokens": 0,
                "upstream_prompt_cache_status": "BYPASS",
                "conversation_session_id": None,
                "conversation_match_status": None,
                "compression_mode": None,
                "compression_status": None,
                "original_estimated_input_tokens": 0,
                "compressed_estimated_input_tokens": 0,
                "compression_saved_estimated_tokens": 0,
                "compression_ratio": 0.0,
                "compression_fallback_reason": None,
                "upstream_session_mode": None,
                "upstream_session_id": None,
            }

        return {
            "cache_status": cache_info.get("cache_status"),
            "cache_hit_segments": int(cache_info.get("hit_segments", 0) or 0),
            "cache_miss_segments": int(cache_info.get("miss_segments", 0) or 0),
            "cache_bypass_segments": int(cache_info.get("bypass_segments", 0) or 0),
            "cache_reused_tokens": int(cache_info.get("reused_estimated_tokens", 0) or 0),
            "cache_new_tokens": int(cache_info.get("new_estimated_tokens", 0) or 0),
            "cache_reused_chars": int(cache_info.get("reused_chars", 0) or 0),
            "cache_new_chars": int(cache_info.get("new_chars", 0) or 0),
            "logical_input_tokens": int(cache_info.get("logical_input_tokens", 0) or 0),
            "upstream_input_tokens": int(cache_info.get("upstream_input_tokens", 0) or 0),
            "upstream_cache_read_input_tokens": int(
                cache_info.get("upstream_cache_read_input_tokens", 0) or 0
            ),
            "upstream_cache_creation_input_tokens": int(
                cache_info.get("upstream_cache_creation_input_tokens", 0) or 0
            ),
            "upstream_cache_creation_5m_input_tokens": int(
                cache_info.get("upstream_cache_creation_5m_input_tokens", 0) or 0
            ),
            "upstream_cache_creation_1h_input_tokens": int(
                cache_info.get("upstream_cache_creation_1h_input_tokens", 0) or 0
            ),
            "upstream_prompt_cache_status": cache_info.get("upstream_prompt_cache_status") or "BYPASS",
            "conversation_session_id": cache_info.get("conversation_session_id"),
            "conversation_match_status": cache_info.get("conversation_match_status"),
            "compression_mode": cache_info.get("compression_mode"),
            "compression_status": cache_info.get("compression_status"),
            "original_estimated_input_tokens": int(
                cache_info.get("original_estimated_input_tokens", 0) or 0
            ),
            "compressed_estimated_input_tokens": int(
                cache_info.get("compressed_estimated_input_tokens", 0) or 0
            ),
            "compression_saved_estimated_tokens": int(
                cache_info.get("compression_saved_estimated_tokens", 0) or 0
            ),
            "compression_ratio": float(cache_info.get("compression_ratio", 0) or 0),
            "compression_fallback_reason": cache_info.get("compression_fallback_reason"),
            "upstream_session_mode": cache_info.get("upstream_session_mode"),
            "upstream_session_id": cache_info.get("upstream_session_id"),
        }

    @staticmethod
    def persist_request_cache_summary(
        db: Session,
        *,
        request_id: str,
        user_id: int | None,
        requested_model: str,
        protocol_type: str | None,
        cache_info: dict[str, Any] | None,
    ) -> None:
        """Persist a per-request cache summary row."""
        if not cache_info:
            return

        try:
            summary = (
                db.query(RequestCacheSummary)
                .filter(RequestCacheSummary.request_id == request_id)
                .first()
            )
            payload = {
                "request_id": request_id,
                "user_id": user_id,
                "requested_model": requested_model,
                "protocol_type": protocol_type,
                "request_format": cache_info.get("request_format"),
                "cache_status": cache_info.get("cache_status") or "BYPASS",
                "hit_segment_count": int(cache_info.get("hit_segments", 0) or 0),
                "miss_segment_count": int(cache_info.get("miss_segments", 0) or 0),
                "bypass_segment_count": int(cache_info.get("bypass_segments", 0) or 0),
                "reused_tokens": int(cache_info.get("reused_estimated_tokens", 0) or 0),
                "new_tokens": int(cache_info.get("new_estimated_tokens", 0) or 0),
                "reused_chars": int(cache_info.get("reused_chars", 0) or 0),
                "new_chars": int(cache_info.get("new_chars", 0) or 0),
                "ttl_seconds": int(cache_info.get("ttl_seconds", 0) or 0),
                "details_json": json.dumps(cache_info.get("details") or {}, ensure_ascii=False),
            }
            if summary:
                for key, value in payload.items():
                    setattr(summary, key, value)
            else:
                db.add(RequestCacheSummary(**payload))
            db.flush()
        except Exception as exc:
            logger.error("Failed to persist request cache summary for %s: %s", request_id, exc)
