"""Safety guards for conversation-state compaction."""
from __future__ import annotations

from typing import Any


class CompressionGuardService:
    """Guard decisions for active conversation compaction."""

    @staticmethod
    def should_apply_non_stream_compaction(
        conversation_shadow_info: dict[str, Any] | None,
        *,
        is_stream: bool,
    ) -> bool:
        """Return whether a request should attempt active non-stream compaction."""
        if is_stream or not conversation_shadow_info:
            return False
        stage = str(conversation_shadow_info.get("_conversation_stage") or "")
        if stage != "non_stream_active":
            return False
        if str(conversation_shadow_info.get("compression_status") or "") != "SHADOW_READY":
            return False
        return bool(conversation_shadow_info.get("_conversation_compacted_request"))

    @staticmethod
    def should_apply_stream_compaction(
        conversation_shadow_info: dict[str, Any] | None,
    ) -> bool:
        """Return whether a request should attempt active stream compaction."""
        if not conversation_shadow_info:
            return False
        stage = str(conversation_shadow_info.get("_conversation_stage") or "")
        if stage != "stream_active":
            return False
        if str(conversation_shadow_info.get("compression_status") or "") != "SHADOW_READY":
            return False
        return bool(conversation_shadow_info.get("_conversation_compacted_request"))

    @staticmethod
    def should_fallback_to_full_request(
        *,
        status_code: int,
        response_text: str,
    ) -> bool:
        """Return whether a compacted request should fallback to the full request."""
        if status_code != 200:
            return True
        lowered = (response_text or "").lower()
        if "invalid_request" in lowered or "improperly formed request" in lowered:
            return True
        return False

    @staticmethod
    def can_retry_stream_before_first_byte() -> bool:
        """Flow-control placeholder for future stream-active support."""
        return True
