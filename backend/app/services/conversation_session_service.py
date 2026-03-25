"""Conversation session persistence and Redis hot-state helpers."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.redis_client import redis_client
from app.models.log import ConversationSession, ConversationCheckpoint
from app.services.health_service import get_system_config

logger = logging.getLogger(__name__)


class ConversationSessionService:
    """Create, update, and persist conversation session state."""

    KEY_PREFIX = "conv-state:v1"

    @staticmethod
    def _build_meta_key(session_id: str) -> str:
        return f"{ConversationSessionService.KEY_PREFIX}:session:{session_id}:meta"

    @staticmethod
    def load_hot_state(session_id: str) -> dict[str, Any]:
        """Load hot session state from Redis."""
        if not session_id:
            return {}
        raw = redis_client.get(ConversationSessionService._build_meta_key(session_id))
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @staticmethod
    def save_hot_state(session_id: str, state: dict[str, Any], ttl_seconds: int) -> None:
        """Save hot session state to Redis."""
        if not session_id or not redis_client.client:
            return
        redis_client.set(
            ConversationSessionService._build_meta_key(session_id),
            json.dumps(state, ensure_ascii=False),
            ex=ttl_seconds,
        )

    @staticmethod
    def _next_checkpoint_seq(db: Session, session_id: str) -> int:
        """Return the next checkpoint sequence id for a session."""
        last = (
            db.query(ConversationCheckpoint)
            .filter(ConversationCheckpoint.session_id == session_id)
            .order_by(ConversationCheckpoint.checkpoint_seq.desc(), ConversationCheckpoint.id.desc())
            .first()
        )
        if not last:
            return 1
        return int(last.checkpoint_seq or 0) + 1

    @staticmethod
    def mark_session_cooldown(
        db: Session,
        session: ConversationSession | None,
    ) -> None:
        """Mark a session in cooldown after a compression failure."""
        if not session:
            return
        cooldown_seconds = int(
            get_system_config(db, "conversation_state_failure_cooldown_seconds", 600) or 600
        )
        session.cooldown_until = datetime.utcnow() + timedelta(seconds=cooldown_seconds)
        db.flush()

    @staticmethod
    def mark_session_cooldown_by_session_id(
        db: Session,
        session_id: str | None,
    ) -> None:
        """Mark cooldown for a session by session_id."""
        if not session_id:
            return
        session = (
            db.query(ConversationSession)
            .filter(ConversationSession.session_id == session_id)
            .first()
        )
        ConversationSessionService.mark_session_cooldown(db, session)

    @staticmethod
    def commit_success_state(
        db: Session,
        *,
        user_id: int,
        requested_model: str,
        protocol_type: str,
        channel_id: int | None,
        shadow_commit: dict[str, Any] | None,
    ) -> str | None:
        """Persist or update a conversation session after a successful request."""
        if not shadow_commit:
            return None

        session_id = str(shadow_commit.get("session_id") or "") or str(uuid.uuid4())
        fingerprint = shadow_commit.get("fingerprint") or {}
        message_hashes = list(shadow_commit.get("message_hashes") or [])
        message_count = int(shadow_commit.get("message_count") or len(message_hashes))
        last_message_hash = shadow_commit.get("last_message_hash")
        last_shadow_saved_tokens = int(shadow_commit.get("compression_saved_estimated_tokens") or 0)
        compression_mode = str(shadow_commit.get("compression_mode") or "shadow")
        upstream_session_mode = str(shadow_commit.get("upstream_session_mode") or "stateless")

        session = None
        session_row_id = shadow_commit.get("session_row_id")
        if session_row_id:
            session = db.query(ConversationSession).filter(ConversationSession.id == session_row_id).first()
        if not session:
            session = (
                db.query(ConversationSession)
                .filter(ConversationSession.session_id == session_id)
                .first()
            )

        if not session:
            session = ConversationSession(
                session_id=session_id,
                user_id=user_id,
                requested_model=requested_model,
                protocol_type=protocol_type,
                channel_id=channel_id,
                system_hash=str(fingerprint.get("system_hash") or ""),
                tools_hash=str(fingerprint.get("tools_hash") or ""),
                message_count=message_count,
                last_message_hash=last_message_hash,
                compression_mode=compression_mode,
                upstream_session_mode=upstream_session_mode,
                upstream_session_id=shadow_commit.get("upstream_session_id"),
                state_version=1,
                status="active",
                last_shadow_saved_tokens=last_shadow_saved_tokens,
                cooldown_until=None,
                last_active_at=datetime.utcnow(),
            )
            db.add(session)
            db.flush()
            logger.info(
                "Conversation session created: session_id=%s user_id=%s requested_model=%s message_count=%s compression_mode=%s",
                session_id,
                user_id,
                requested_model,
                message_count,
                compression_mode,
            )
        else:
            session.channel_id = channel_id
            session.message_count = message_count
            session.last_message_hash = last_message_hash
            session.compression_mode = compression_mode
            session.upstream_session_mode = upstream_session_mode
            session.upstream_session_id = shadow_commit.get("upstream_session_id")
            session.state_version = int(session.state_version or 0) + 1
            session.status = "active"
            session.last_shadow_saved_tokens = last_shadow_saved_tokens
            session.cooldown_until = None
            session.last_active_at = datetime.utcnow()
            db.flush()
            logger.info(
                "Conversation session updated: session_id=%s user_id=%s requested_model=%s message_count=%s compression_mode=%s",
                session_id,
                user_id,
                requested_model,
                message_count,
                compression_mode,
            )

        ttl_seconds = int(
            get_system_config(db, "conversation_state_session_ttl_seconds", 86400) or 86400
        )
        ConversationSessionService.save_hot_state(
            session_id,
            {
                "session_id": session_id,
                "user_id": user_id,
                "requested_model": requested_model,
                "protocol_type": protocol_type,
                "system_hash": str(fingerprint.get("system_hash") or ""),
                "tools_hash": str(fingerprint.get("tools_hash") or ""),
                "message_hashes": message_hashes,
                "message_count": message_count,
                "last_message_hash": last_message_hash,
                "updated_at": datetime.utcnow().isoformat(),
            },
            ttl_seconds,
        )

        checkpoint_payload = shadow_commit.get("checkpoint")
        if checkpoint_payload:
            checkpoint = ConversationCheckpoint(
                session_id=session_id,
                checkpoint_seq=ConversationSessionService._next_checkpoint_seq(db, session_id),
                source_turn_start=int(checkpoint_payload.get("source_turn_start", 0) or 0),
                source_turn_end=int(checkpoint_payload.get("source_turn_end", 0) or 0),
                source_hash=str(checkpoint_payload.get("source_hash") or ""),
                summary_json=json.dumps(checkpoint_payload.get("summary") or {}, ensure_ascii=False),
                summary_token_estimate=int(
                    checkpoint_payload.get("summary_token_estimate", 0) or 0
                ),
            )
            db.add(checkpoint)
            db.flush()

        return session_id
