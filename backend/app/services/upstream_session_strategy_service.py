"""Upstream session strategy abstraction.

Current Anthropic relay channels are stateless; this service centralizes that
decision so future stateful upstreams can be introduced without rewriting the
main proxy flow.
"""
from __future__ import annotations

from app.models.channel import Channel


class UpstreamSessionStrategyService:
    """Resolve upstream session strategy for a channel."""

    @staticmethod
    def get_session_mode(channel: Channel | None) -> str:
        """Return the upstream session mode for the given channel."""
        if not channel:
            return "stateless"
        return "stateless"

    @staticmethod
    def supports_incremental(channel: Channel | None) -> bool:
        """Return whether the channel supports true incremental session sends."""
        return UpstreamSessionStrategyService.get_session_mode(channel) == "upstream_stateful"
