"""Channel management service."""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.log import HealthCheckLog
from app.core.exceptions import ServiceException


class ChannelService:
    """CRUD and health summary for channels."""

    PROVIDER_VARIANT_DEFAULT = "default"
    PROVIDER_VARIANT_GOOGLE_OFFICIAL = "google-official"
    PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE = "google-vertex-image"

    @staticmethod
    def _normalize_health_check_model(value: Optional[str]) -> Optional[str]:
        """Normalize the stored health-check model name."""
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _resolve_default_auth_header_type(protocol_type: Optional[str]) -> str:
        """Choose the recommended upstream auth header for a protocol."""
        protocol = (protocol_type or "openai").lower()
        if protocol == "openai":
            return "authorization"
        if protocol == "anthropic":
            return "anthropic-api-key"
        if protocol == "google":
            return "x-goog-api-key"
        return "x-api-key"

    @staticmethod
    def _resolve_default_health_check_enabled(
        protocol_type: Optional[str],
        provider_variant: Optional[str],
    ) -> int:
        protocol = (protocol_type or "openai").lower()
        normalized_variant = ChannelService._normalize_provider_variant(
            protocol,
            provider_variant,
        )
        if protocol == "google" and normalized_variant in {
            ChannelService.PROVIDER_VARIANT_GOOGLE_OFFICIAL,
            ChannelService.PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE,
        }:
            return 0
        return 1

    @staticmethod
    def _normalize_provider_variant(
        protocol_type: Optional[str],
        provider_variant: Optional[str],
    ) -> str:
        protocol = (protocol_type or "openai").lower()
        raw_variant = str(provider_variant or "").strip().lower()
        if protocol == "google":
            if raw_variant in {
                ChannelService.PROVIDER_VARIANT_GOOGLE_OFFICIAL,
                ChannelService.PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE,
            }:
                return raw_variant
            return ChannelService.PROVIDER_VARIANT_GOOGLE_OFFICIAL
        return ChannelService.PROVIDER_VARIANT_DEFAULT

    @staticmethod
    def _channel_to_dict(channel: Channel) -> dict:
        """Convert a Channel ORM instance to a serializable dict."""
        api_key = channel.api_key or ""
        masked_key = api_key[:8] + "****" + api_key[-4:] if len(api_key) > 12 else "****"
        return {
            "id": channel.id,
            "name": channel.name,
            "base_url": channel.base_url,
            "api_key_display": masked_key,
            "protocol_type": channel.protocol_type,
            "provider_variant": ChannelService._normalize_provider_variant(
                channel.protocol_type,
                getattr(channel, "provider_variant", None),
            ),
            "auth_header_type": (
                getattr(channel, "auth_header_type", None)
                or ChannelService._resolve_default_auth_header_type(channel.protocol_type)
            ),
            "priority": channel.priority,
            "enabled": channel.enabled,
            "health_check_enabled": int(getattr(channel, "health_check_enabled", 1) or 0),
            "is_healthy": bool(channel.is_healthy),
            "health_score": channel.health_score,
            "failure_count": channel.failure_count,
            "circuit_breaker_until": channel.circuit_breaker_until.isoformat() if channel.circuit_breaker_until else None,
            "health_check_model": ChannelService._normalize_health_check_model(channel.health_check_model),
            "last_health_check_at": channel.last_health_check_at.isoformat() if channel.last_health_check_at else None,
            "last_success_at": channel.last_success_at.isoformat() if channel.last_success_at else None,
            "last_failure_at": channel.last_failure_at.isoformat() if channel.last_failure_at else None,
            "description": channel.description,
            "created_at": channel.created_at.isoformat() if channel.created_at else None,
            "updated_at": channel.updated_at.isoformat() if channel.updated_at else None,
        }

    @staticmethod
    def create_channel(db: Session, data) -> dict:
        """
        Create a new channel.

        Args:
            data: ChannelCreate schema or dict.

        Returns:
            The created Channel ORM instance.
        """
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        protocol_value = d.get("protocol_type", "openai")
        provider_variant = ChannelService._normalize_provider_variant(
            protocol_value,
            d.get("provider_variant"),
        )
        channel = Channel(
            name=d["name"],
            base_url=d["base_url"].rstrip("/"),
            api_key=d["api_key"],
            protocol_type=protocol_value,
            provider_variant=provider_variant,
            auth_header_type=(
                d.get("auth_header_type")
                or ChannelService._resolve_default_auth_header_type(protocol_value)
            ),
            health_check_model=ChannelService._normalize_health_check_model(d.get("health_check_model")),
            priority=d.get("priority", 10),
            enabled=d.get("enabled", 1),
            health_check_enabled=d.get(
                "health_check_enabled",
                ChannelService._resolve_default_health_check_enabled(protocol_value, provider_variant),
            ),
            description=d.get("description"),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return ChannelService._channel_to_dict(channel)

    @staticmethod
    def update_channel(db: Session, channel_id: int, data) -> dict:
        """
        Update an existing channel.

        Args:
            data: ChannelUpdate schema or dict.

        Returns:
            The updated Channel ORM instance.

        Raises:
            ServiceException: if channel not found.
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        protocol_value = d.get("protocol_type", channel.protocol_type)
        updatable_fields = [
            "name", "base_url", "api_key", "protocol_type", "auth_header_type",
            "priority", "enabled", "health_check_enabled", "description",
        ]
        for field in updatable_fields:
            value = d.get(field)
            if value is not None:
                if field == "base_url":
                    value = value.rstrip("/")
                setattr(channel, field, value)

        if "health_check_model" in d:
            channel.health_check_model = ChannelService._normalize_health_check_model(
                d.get("health_check_model")
            )

        if "protocol_type" in d or "provider_variant" in d:
            channel.provider_variant = ChannelService._normalize_provider_variant(
                protocol_value,
                d.get("provider_variant", getattr(channel, "provider_variant", None)),
            )

        if (
            "health_check_enabled" not in d
            and ("protocol_type" in d or "provider_variant" in d)
        ):
            channel.health_check_enabled = ChannelService._resolve_default_health_check_enabled(
                protocol_value,
                channel.provider_variant,
            )

        if "protocol_type" in d and "auth_header_type" not in d:
            channel.auth_header_type = ChannelService._resolve_default_auth_header_type(protocol_value)

        db.commit()
        db.refresh(channel)
        return ChannelService._channel_to_dict(channel)

    @staticmethod
    def update_channel_health_check_model(
        db: Session,
        channel_id: int,
        health_check_model: Optional[str],
    ) -> dict:
        """Update only the persisted health-check model for a channel."""
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        channel.health_check_model = ChannelService._normalize_health_check_model(
            health_check_model
        )

        db.commit()
        db.refresh(channel)
        return ChannelService._channel_to_dict(channel)

    @staticmethod
    def delete_channel(db: Session, channel_id: int) -> None:
        """
        Delete a channel by id.

        Raises:
            ServiceException: if channel not found.
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        db.delete(channel)
        db.commit()

    @staticmethod
    def get_channel(db: Session, channel_id: int) -> dict:
        """
        Get a single channel by id.

        Raises:
            ServiceException: if channel not found.
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")
        return ChannelService._channel_to_dict(channel)

    @staticmethod
    def list_channels(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        List channels with pagination and optional keyword search.

        Returns:
            Tuple of (list of Channel, total count).
        """
        query = db.query(Channel)

        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    Channel.name.like(like_pattern),
                    Channel.base_url.like(like_pattern),
                    Channel.description.like(like_pattern),
                )
            )

        total = query.count()
        channels = (
            query.order_by(Channel.priority.asc(), Channel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [ChannelService._channel_to_dict(ch) for ch in channels], total

    @staticmethod
    def get_channel_health_summary(db: Session) -> dict:
        """
        Return an aggregated health summary for all enabled channels.

        Returns:
            dict with ``total``, ``healthy``, ``unhealthy``, and ``channels`` keys.
        """
        channels = db.query(Channel).filter(Channel.enabled == 1).all()

        healthy_count = 0
        unhealthy_count = 0
        channel_details = []

        for ch in channels:
            is_healthy = bool(ch.is_healthy)
            if is_healthy:
                healthy_count += 1
            else:
                unhealthy_count += 1

            # Fetch most recent health check log
            last_log = (
                db.query(HealthCheckLog)
                .filter(HealthCheckLog.channel_id == ch.id)
                .order_by(HealthCheckLog.checked_at.desc())
                .first()
            )

            channel_details.append({
                "id": ch.id,
                "name": ch.name,
                "is_healthy": is_healthy,
                "health_score": ch.health_score,
                "failure_count": ch.failure_count,
                "circuit_breaker_until": (
                    ch.circuit_breaker_until.isoformat() if ch.circuit_breaker_until else None
                ),
                "last_health_check_at": (
                    ch.last_health_check_at.isoformat() if ch.last_health_check_at else None
                ),
                "last_check_status": last_log.status if last_log else None,
                "last_check_response_ms": last_log.response_time_ms if last_log else None,
                "last_check_error": last_log.error_message if last_log else None,
            })

        return {
            "total": len(channels),
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "channels": channel_details,
        }
