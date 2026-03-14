"""Channel management service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.log import HealthCheckLog
from app.core.exceptions import ServiceException


class ChannelService:
    """CRUD and health summary for channels."""

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
            "priority": channel.priority,
            "enabled": channel.enabled,
            "is_healthy": bool(channel.is_healthy),
            "health_score": channel.health_score,
            "failure_count": channel.failure_count,
            "circuit_breaker_until": channel.circuit_breaker_until.isoformat() if channel.circuit_breaker_until else None,
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
        channel = Channel(
            name=d["name"],
            base_url=d["base_url"].rstrip("/"),
            api_key=d["api_key"],
            protocol_type=d.get("protocol_type", "openai"),
            priority=d.get("priority", 10),
            enabled=d.get("enabled", 1),
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
        updatable_fields = [
            "name", "base_url", "api_key", "protocol_type",
            "priority", "enabled", "description",
        ]
        for field in updatable_fields:
            value = d.get(field)
            if value is not None:
                if field == "base_url":
                    value = value.rstrip("/")
                setattr(channel, field, value)

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
        keyword: str | None = None,
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
