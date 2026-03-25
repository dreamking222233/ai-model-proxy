"""Conversation session matching for append-only Anthropic requests."""
from __future__ import annotations

from typing import Any, Optional

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.log import ConversationSession
from app.services.health_service import get_system_config
from app.services.request_body_cache_analyzer import RequestBodyCacheAnalyzer
from app.services.conversation_session_service import ConversationSessionService


class ConversationMatchService:
    """Find the best existing conversation session for a request."""

    EXPLICIT_HEADER_KEYS = (
        "x-relay-session-id",
        "x-conversation-id",
        "x-claude-conversation-id",
    )
    EXPLICIT_BODY_KEYS = (
        "conversation_id",
        "session_id",
        "thread_id",
    )

    @staticmethod
    def _strip_cache_control(value: Any) -> Any:
        """Remove cache metadata so matching is stable across cache strategies."""
        if isinstance(value, list):
            return [ConversationMatchService._strip_cache_control(item) for item in value]
        if not isinstance(value, dict):
            return value
        cleaned = {}
        for key, item in value.items():
            if key == "cache_control":
                continue
            cleaned[key] = ConversationMatchService._strip_cache_control(item)
        return cleaned

    @staticmethod
    def _message_hashes(request_data: dict[str, Any]) -> list[str]:
        """Build stable per-message hashes for append-only detection."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            return []
        hashes: list[str] = []
        for message in messages:
            hashes.append(
                RequestBodyCacheAnalyzer.hash_value(
                    ConversationMatchService._strip_cache_control(message)
                )
            )
        return hashes

    @staticmethod
    def build_request_fingerprint(
        request_data: dict[str, Any],
        request_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Build stable matching fingerprints for one request."""
        normalized_headers = {
            str(key).lower(): value
            for key, value in (request_headers or {}).items()
            if isinstance(key, str)
        }
        explicit_session_id = None
        for key in ConversationMatchService.EXPLICIT_HEADER_KEYS:
            value = normalized_headers.get(key)
            if isinstance(value, str) and value.strip():
                explicit_session_id = value.strip()
                break

        if not explicit_session_id:
            for key in ConversationMatchService.EXPLICIT_BODY_KEYS:
                value = request_data.get(key)
                if isinstance(value, str) and value.strip():
                    explicit_session_id = value.strip()
                    break

        normalized_system = ConversationMatchService._strip_cache_control(
            request_data.get("system")
        )
        normalized_tools = ConversationMatchService._strip_cache_control(
            request_data.get("tools") or []
        )
        message_hashes = ConversationMatchService._message_hashes(request_data)

        return {
            "explicit_session_id": explicit_session_id,
            "system_hash": RequestBodyCacheAnalyzer.hash_value(normalized_system),
            "tools_hash": RequestBodyCacheAnalyzer.hash_value(normalized_tools),
            "message_hashes": message_hashes,
            "message_count": len(message_hashes),
            "last_message_hash": message_hashes[-1] if message_hashes else None,
        }

    @staticmethod
    def _common_prefix_length(previous_hashes: list[str], current_hashes: list[str]) -> int:
        """Return the number of identical hashes from the start of both lists."""
        prefix_len = 0
        for previous_hash, current_hash in zip(previous_hashes, current_hashes):
            if previous_hash != current_hash:
                break
            prefix_len += 1
        return prefix_len

    @staticmethod
    def _compare_hash_lists(
        previous_hashes: list[str],
        current_hashes: list[str],
        *,
        tail_tolerance: int = 0,
        min_shared_prefix: int = 0,
    ) -> dict[str, Any]:
        """Compare two message-hash lists and tolerate small tail rewrites."""
        if not previous_hashes and not current_hashes:
            return {"status": "EXACT", "matched_prefix_len": 0}
        common_prefix_len = ConversationMatchService._common_prefix_length(
            previous_hashes,
            current_hashes,
        )
        if previous_hashes == current_hashes:
            return {"status": "EXACT", "matched_prefix_len": common_prefix_len}
        if len(previous_hashes) < len(current_hashes) and common_prefix_len == len(previous_hashes):
            return {"status": "APPEND", "matched_prefix_len": common_prefix_len}

        allowed_prefix_floor = max(
            min_shared_prefix,
            len(previous_hashes) - max(0, tail_tolerance),
        )
        if (
            previous_hashes
            and len(current_hashes) > common_prefix_len
            and common_prefix_len >= allowed_prefix_floor
        ):
            return {
                "status": "APPEND_TAIL_MUTATION",
                "matched_prefix_len": common_prefix_len,
            }

        return {"status": "RESET", "matched_prefix_len": common_prefix_len}

    @staticmethod
    def find_best_matching_session(
        db: Session,
        *,
        user_id: int,
        requested_model: str,
        protocol_type: str,
        request_data: dict[str, Any],
        request_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Return the best session match for the request."""
        fingerprint = ConversationMatchService.build_request_fingerprint(
            request_data,
            request_headers=request_headers,
        )
        message_hashes = fingerprint["message_hashes"]
        match_window = int(get_system_config(db, "conversation_state_match_window", 20) or 20)
        tail_tolerance = int(
            get_system_config(db, "conversation_state_match_tail_tolerance_messages", 2) or 2
        )
        min_shared_prefix = int(
            get_system_config(db, "conversation_state_match_min_shared_prefix", 8) or 8
        )
        now = datetime.utcnow()

        explicit_session_id = fingerprint.get("explicit_session_id")
        if explicit_session_id:
            session = (
                db.query(ConversationSession)
                .filter(
                    ConversationSession.session_id == explicit_session_id,
                    ConversationSession.user_id == user_id,
                )
                .first()
            )
            if session:
                hot_state = ConversationSessionService.load_hot_state(session.session_id)
                previous_hashes = list(hot_state.get("message_hashes") or [])
                match_result = ConversationMatchService._compare_hash_lists(
                    previous_hashes,
                    message_hashes,
                    tail_tolerance=tail_tolerance,
                    min_shared_prefix=min_shared_prefix,
                )
                return {
                    "session": session,
                    "session_id": session.session_id,
                    "match_status": match_result["status"],
                    "matched_prefix_len": match_result["matched_prefix_len"],
                    "fingerprint": fingerprint,
                    "previous_message_hashes": previous_hashes,
                }
            return {
                "session": None,
                "session_id": explicit_session_id,
                "match_status": "NEW",
                "fingerprint": fingerprint,
                "previous_message_hashes": [],
            }

        candidates = (
            db.query(ConversationSession)
            .filter(
                ConversationSession.user_id == user_id,
                ConversationSession.requested_model == requested_model,
                ConversationSession.protocol_type == protocol_type,
                ConversationSession.system_hash == fingerprint["system_hash"],
                ConversationSession.tools_hash == fingerprint["tools_hash"],
                ConversationSession.status == "active",
            )
            .order_by(ConversationSession.last_active_at.desc(), ConversationSession.id.desc())
            .limit(match_window)
            .all()
        )

        best_match: dict[str, Any] | None = None
        best_prefix_len = -1
        for session in candidates:
            if session.cooldown_until and session.cooldown_until > now:
                continue
            hot_state = ConversationSessionService.load_hot_state(session.session_id)
            previous_hashes = list(hot_state.get("message_hashes") or [])
            match_result = ConversationMatchService._compare_hash_lists(
                previous_hashes,
                message_hashes,
                tail_tolerance=tail_tolerance,
                min_shared_prefix=min_shared_prefix,
            )
            match_status = match_result["status"]
            if match_status == "RESET":
                continue
            prefix_len = int(match_result.get("matched_prefix_len") or 0)
            if prefix_len > best_prefix_len:
                best_prefix_len = prefix_len
                best_match = {
                    "session": session,
                    "session_id": session.session_id,
                    "match_status": match_status,
                    "matched_prefix_len": prefix_len,
                    "fingerprint": fingerprint,
                    "previous_message_hashes": previous_hashes,
                }

        if best_match:
            return best_match

        return {
            "session": None,
            "session_id": None,
            "match_status": "NEW",
            "fingerprint": fingerprint,
            "previous_message_hashes": [],
        }
