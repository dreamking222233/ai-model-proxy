"""Shadow-mode conversation compaction analysis for Anthropic requests."""
from __future__ import annotations

from typing import Any, Optional

from app.services.conversation_match_service import ConversationMatchService
from app.services.health_service import get_system_config
from app.services.history_compaction_service import HistoryCompactionService
from app.services.request_body_cache_analyzer import RequestBodyCacheAnalyzer


class ConversationShadowService:
    """Compute session match and theoretical compaction savings without changing requests."""

    @staticmethod
    def is_enabled(db) -> bool:
        return bool(get_system_config(db, "conversation_state_compaction_enabled", False))

    @staticmethod
    def _build_bypass(
        *,
        reason: str,
        original_estimated_input_tokens: int,
    ) -> dict[str, Any]:
        return {
            "conversation_session_id": None,
            "conversation_match_status": "BYPASS",
            "compression_mode": "shadow",
            "compression_status": "BYPASS",
            "original_estimated_input_tokens": original_estimated_input_tokens,
            "compressed_estimated_input_tokens": original_estimated_input_tokens,
            "compression_saved_estimated_tokens": 0,
            "compression_ratio": 0.0,
            "compression_fallback_reason": None,
            "upstream_session_mode": "stateless",
            "upstream_session_id": None,
            "details": {
                "enabled": False,
                "reason": reason,
                "stage": None,
            },
            "_conversation_shadow_commit": None,
            "_conversation_compacted_request": None,
            "_conversation_stage": None,
        }

    @staticmethod
    def analyze_request(
        db,
        *,
        user_id: int,
        requested_model: str,
        protocol_type: str,
        request_data: dict[str, Any],
        request_headers: Optional[dict[str, str]] = None,
        is_stream: bool = False,
    ) -> dict[str, Any]:
        """Analyze conversation state and theoretical compaction savings."""
        original_tokens = HistoryCompactionService.estimate_anthropic_input_tokens(request_data)
        if not ConversationShadowService.is_enabled(db):
            return ConversationShadowService._build_bypass(
                reason="disabled",
                original_estimated_input_tokens=original_tokens,
            )

        stage = str(get_system_config(db, "conversation_state_compaction_stage", "shadow") or "shadow")
        if stage == "off":
            return ConversationShadowService._build_bypass(
                reason="stage_off",
                original_estimated_input_tokens=original_tokens,
            )

        if is_stream and stage not in {"shadow", "stream_shadow", "stream_active"}:
            return ConversationShadowService._build_bypass(
                reason="stream_stage_disabled",
                original_estimated_input_tokens=original_tokens,
            )

        match_result = ConversationMatchService.find_best_matching_session(
            db,
            user_id=user_id,
            requested_model=requested_model,
            protocol_type=protocol_type,
            request_data=request_data,
            request_headers=request_headers,
        )
        fingerprint = match_result["fingerprint"]
        match_status = str(match_result.get("match_status") or "BYPASS")
        session = match_result.get("session")
        session_id = match_result.get("session_id")

        if match_status == "NEW":
            compression_status = "SHADOW_BYPASS_NEW_SESSION"
            compressed_tokens = original_tokens
            saved_tokens = 0
            ratio = 0.0
            checkpoint = None
            details = {
                "enabled": True,
                "stage": stage,
                "reason": "new_session",
                "match_status": match_status,
            }
            compacted_request = None
        elif match_status == "RESET":
            compression_status = "SHADOW_BYPASS_RESET"
            compressed_tokens = original_tokens
            saved_tokens = 0
            ratio = 0.0
            checkpoint = None
            details = {
                "enabled": True,
                "stage": stage,
                "reason": "history_reset",
                "match_status": match_status,
            }
            compacted_request = None
        else:
            recent_turns = int(get_system_config(db, "conversation_state_compaction_recent_turns", 6) or 6)
            trigger_tokens = int(get_system_config(db, "conversation_state_compaction_trigger_tokens", 12000) or 12000)
            summary_max_tokens = int(get_system_config(db, "conversation_state_compaction_summary_max_tokens", 1500) or 1500)
            history_split = HistoryCompactionService.split_history_windows(
                request_data,
                recent_turns=recent_turns,
            )
            frozen_groups = history_split["frozen_groups"]
            if original_tokens < trigger_tokens or not frozen_groups:
                compression_status = "SHADOW_BYPASS_THRESHOLD"
                compressed_tokens = original_tokens
                saved_tokens = 0
                ratio = 0.0
                checkpoint = None
                details = {
                    "enabled": True,
                    "stage": stage,
                    "reason": "below_threshold_or_no_frozen_history",
                    "match_status": match_status,
                    "trigger_tokens": trigger_tokens,
                    "recent_turns": recent_turns,
                    "frozen_group_count": len(frozen_groups),
                }
                compacted_request = None
            else:
                summary_payload = HistoryCompactionService.build_checkpoint_summary(
                    frozen_groups,
                    max_summary_tokens=summary_max_tokens,
                )
                compacted_request = HistoryCompactionService.rebuild_compacted_anthropic_request(
                    request_data,
                    summary_payload=summary_payload,
                    recent_messages=history_split["recent_messages"],
                )
                compressed_tokens = HistoryCompactionService.estimate_anthropic_input_tokens(
                    compacted_request
                )
                saved_tokens = max(0, original_tokens - compressed_tokens)
                ratio = round((saved_tokens / original_tokens), 4) if original_tokens > 0 else 0.0
                compression_status = "SHADOW_READY"
                checkpoint = {
                    "source_turn_start": 1,
                    "source_turn_end": len(frozen_groups),
                    "source_hash": RequestBodyCacheAnalyzer.hash_value(
                        history_split["frozen_messages"]
                    ),
                    "summary": summary_payload,
                    "summary_token_estimate": RequestBodyCacheAnalyzer.estimate_tokens(
                        summary_payload.get("summary_text", "")
                    ),
                }
                details = {
                    "enabled": True,
                    "stage": stage,
                    "reason": None,
                    "match_status": match_status,
                    "trigger_tokens": trigger_tokens,
                    "recent_turns": recent_turns,
                    "frozen_group_count": len(frozen_groups),
                    "recent_group_count": len(history_split["recent_groups"]),
                    "checkpoint_preview": RequestBodyCacheAnalyzer.build_preview(
                        summary_payload.get("summary_text", "")
                    ),
                }

        session_id_value = session_id or (session.session_id if session else None)
        return {
            "conversation_session_id": session_id_value,
            "conversation_match_status": match_status,
            "compression_mode": "shadow",
            "compression_status": compression_status,
            "original_estimated_input_tokens": original_tokens,
            "compressed_estimated_input_tokens": compressed_tokens,
            "compression_saved_estimated_tokens": saved_tokens,
            "compression_ratio": ratio,
            "compression_fallback_reason": None,
            "upstream_session_mode": "stateless",
            "upstream_session_id": None,
            "details": details,
            "_conversation_shadow_commit": {
                "session_row_id": session.id if session else None,
                "session_id": session_id_value,
                "fingerprint": fingerprint,
                "message_hashes": fingerprint["message_hashes"],
                "message_count": fingerprint["message_count"],
                "last_message_hash": fingerprint["last_message_hash"],
                "compression_mode": "shadow",
                "upstream_session_mode": "stateless",
                "upstream_session_id": None,
                "compression_saved_estimated_tokens": saved_tokens,
                "checkpoint": checkpoint,
            },
            "_conversation_compacted_request": compacted_request,
            "_conversation_stage": stage,
        }

    @staticmethod
    def merge_into_cache_info(
        cache_info: dict[str, Any] | None,
        shadow_info: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Merge shadow compaction analysis into the shared cache_info payload."""
        if not shadow_info:
            return cache_info
        merged = dict(cache_info or {})
        details = dict(merged.get("details") or {})
        details["conversation_state_compaction"] = shadow_info.get("details") or {}
        merged["details"] = details
        for key in (
            "conversation_session_id",
            "conversation_match_status",
            "compression_mode",
            "compression_status",
            "original_estimated_input_tokens",
            "compressed_estimated_input_tokens",
            "compression_saved_estimated_tokens",
            "compression_ratio",
            "compression_fallback_reason",
            "upstream_session_mode",
            "upstream_session_id",
        ):
            merged[key] = shadow_info.get(key)
        merged["_conversation_shadow_commit"] = shadow_info.get("_conversation_shadow_commit")
        merged["_conversation_mark_cooldown"] = shadow_info.get("_conversation_mark_cooldown")
        return merged
