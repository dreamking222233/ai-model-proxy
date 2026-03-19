"""Channel health check service."""
from __future__ import annotations

from typing import Optional

import asyncio
import logging
import time

import httpx
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.model import ModelChannelMapping
from app.models.log import HealthCheckLog, SystemConfig
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


def get_system_config(db: Session, key: str, default=None):
    """Read a typed value from the system_config table."""
    config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if not config:
        return default
    if config.config_type == "number":
        try:
            return int(config.config_value)
        except ValueError:
            return default
    if config.config_type == "boolean":
        return config.config_value.lower() in ("true", "1", "yes")
    return config.config_value


class HealthService:
    """Concurrent health checks for all enabled channels."""

    @staticmethod
    async def check_all_channels(db: Session) -> list[dict]:
        """
        Check all enabled channels concurrently.

        For each channel, pick the first mapped model to use as a test model.
        Updates channel health state and writes HealthCheckLog entries.

        Returns:
            List of dicts with check results per channel.
        """
        channels = db.query(Channel).filter(Channel.enabled == 1).all()
        if not channels:
            return []

        tasks = []
        for channel in channels:
            # Find a model name to test with
            mapping = (
                db.query(ModelChannelMapping)
                .filter(
                    ModelChannelMapping.channel_id == channel.id,
                    ModelChannelMapping.enabled == 1,
                )
                .first()
            )
            actual_model_name = mapping.actual_model_name if mapping else None
            tasks.append(HealthService._check_and_record(db, channel, actual_model_name))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results -- gather may return exceptions for individual tasks
        output = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Health check task failed for channel %s: %s",
                    channels[i].name,
                    result,
                )
                output.append({
                    "channel_id": channels[i].id,
                    "channel_name": channels[i].name,
                    "is_healthy": False,
                    "error": str(result),
                })
            else:
                output.append(result)

        return output

    @staticmethod
    async def check_single_channel(db: Session, channel_id: int) -> dict:
        """
        Run a health check on a single channel.

        Raises:
            ServiceException: if channel not found.
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        mapping = (
            db.query(ModelChannelMapping)
            .filter(
                ModelChannelMapping.channel_id == channel_id,
                ModelChannelMapping.enabled == 1,
            )
            .first()
        )
        actual_model_name = mapping.actual_model_name if mapping else None

        return await HealthService._check_and_record(db, channel, actual_model_name)

    @staticmethod
    async def _check_and_record(
        db: Session, channel: Channel, actual_model_name: Optional[str]
    ) -> dict:
        """
        Perform the actual health check, update the channel, and log the result.
        """
        if not actual_model_name:
            # No model mapped -- just try a lightweight request
            actual_model_name = "gpt-3.5-turbo"

        success, response_time_ms, error_msg = await HealthService._do_health_check(
            channel, actual_model_name
        )

        now = datetime.utcnow()

        # Update channel health state
        channel.last_health_check_at = now
        if success:
            channel.is_healthy = 1
            channel.failure_count = 0
            channel.last_success_at = now
            # Increase health score (max 100)
            channel.health_score = min(100, channel.health_score + 10)
            channel.circuit_breaker_until = None
        else:
            channel.failure_count += 1
            channel.last_failure_at = now
            # Decrease health score (min 0)
            channel.health_score = max(0, channel.health_score - 20)

            threshold = get_system_config(db, "circuit_breaker_threshold", 5)
            if channel.failure_count >= threshold:
                recovery = get_system_config(db, "circuit_breaker_recovery", 600)
                from datetime import timedelta
                channel.circuit_breaker_until = now + timedelta(seconds=recovery)
                channel.is_healthy = 0

        # Write health check log
        log = HealthCheckLog(
            channel_id=channel.id,
            channel_name=channel.name,
            model_name=actual_model_name,
            status="success" if success else "fail",
            response_time_ms=response_time_ms,
            error_message=error_msg,
        )
        db.add(log)
        db.commit()

        return {
            "channel_id": channel.id,
            "channel_name": channel.name,
            "is_healthy": success,
            "response_time_ms": response_time_ms,
            "error": error_msg,
            "health_score": channel.health_score,
            "failure_count": channel.failure_count,
        }

    @staticmethod
    async def _do_health_check(
        channel: Channel, actual_model_name: str
    ) -> tuple:
        """
        Send a small test request to a channel.

        Returns:
            Tuple of (success, response_time_ms, error_message).
        """
        base_url = channel.base_url.rstrip("/")
        protocol = channel.protocol_type

        if protocol == "openai":
            url = f"{base_url}/chat/completions"
            payload = {
                "model": actual_model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "stream": False,
            }
        elif protocol == "anthropic":
            url = f"{base_url}/messages"
            payload = {
                "model": actual_model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
        else:
            return False, None, f"Unsupported protocol type: {protocol}"

        # Build headers using channel auth_header_type (same logic as proxy_service)
        auth_header_type = getattr(channel, "auth_header_type", None)
        if not auth_header_type:
            auth_header_type = "authorization" if protocol == "openai" else "x-api-key"

        headers: dict = {"Content-Type": "application/json"}
        if auth_header_type == "authorization":
            headers["Authorization"] = f"Bearer {channel.api_key}"
        elif auth_header_type == "anthropic-api-key":
            headers["anthropic-api-key"] = channel.api_key
            if protocol == "anthropic":
                headers["anthropic-version"] = "2023-06-01"
        else:  # x-api-key
            headers["x-api-key"] = channel.api_key
            if protocol == "anthropic":
                headers["anthropic-version"] = "2023-06-01"

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                return True, elapsed_ms, None
            else:
                error_body = resp.text[:500]
                return False, elapsed_ms, f"HTTP {resp.status_code}: {error_body}"

        except httpx.TimeoutException:
            elapsed_ms = int((time.time() - start) * 1000)
            return False, elapsed_ms, "Request timed out"
        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            return False, elapsed_ms, str(e)

    @staticmethod
    def get_health_status(db: Session) -> list[dict]:
        """
        Get current health status for all channels.

        Returns:
            List of dicts with channel health information.
        """
        channels = db.query(Channel).filter(Channel.enabled == 1).all()

        result = []
        for ch in channels:
            last_log = (
                db.query(HealthCheckLog)
                .filter(HealthCheckLog.channel_id == ch.id)
                .order_by(HealthCheckLog.checked_at.desc())
                .first()
            )
            last_check_time = ch.last_health_check_at.isoformat() if ch.last_health_check_at else None
            result.append({
                "channel_id": ch.id,
                "channel_name": ch.name,
                "protocol_type": ch.protocol_type,
                "is_healthy": bool(ch.is_healthy),
                "health_score": ch.health_score,
                "failure_count": ch.failure_count,
                "circuit_breaker_until": (
                    ch.circuit_breaker_until.isoformat() if ch.circuit_breaker_until else None
                ),
                "last_health_check_at": last_check_time,
                "last_check_time": last_check_time,  # Alias for frontend compatibility
                "last_success_at": (
                    ch.last_success_at.isoformat() if ch.last_success_at else None
                ),
                "last_failure_at": (
                    ch.last_failure_at.isoformat() if ch.last_failure_at else None
                ),
                "last_check_status": last_log.status if last_log else None,
                "last_check_response_ms": last_log.response_time_ms if last_log else None,
                "last_check_error": last_log.error_message if last_log else None,
            })
        return result

    @staticmethod
    def get_health_logs(
        db: Session,
        channel_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List health check logs with pagination, optionally filtered by channel_id.

        Returns:
            Tuple of (list of log dicts, total count).
        """
        query = db.query(HealthCheckLog)
        if channel_id is not None:
            query = query.filter(HealthCheckLog.channel_id == channel_id)

        total = query.count()
        logs = (
            query.order_by(HealthCheckLog.checked_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = [
            {
                "id": log.id,
                "channel_id": log.channel_id,
                "channel_name": log.channel_name,
                "model": log.model_name,  # Alias for frontend compatibility
                "model_name": log.model_name,
                "status": log.status,
                "response_time_ms": log.response_time_ms,
                "response_time": log.response_time_ms,  # Alias for frontend compatibility
                "error_message": log.error_message,
                "checked_at": log.checked_at.isoformat() if log.checked_at else None,
            }
            for log in logs
        ]
        return result, total
