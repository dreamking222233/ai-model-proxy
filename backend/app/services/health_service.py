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
from app.models.model import ModelChannelMapping, UnifiedModel
from app.models.log import HealthCheckLog, SystemConfig
from app.core.exceptions import ServiceException
from app.services.channel_service import ChannelService
from app.services.google_vertex_image_service import GoogleVertexImageService

logger = logging.getLogger(__name__)
_UPSTREAM_DEFAULT_USER_AGENT = "Mozilla/5.0"
_DEFAULT_GOOGLE_HEALTH_CHECK_MODEL = "gemini-2.5-flash"
_IMAGE_CHANNEL_HEALTH_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


def _normalize_health_check_model(value: Optional[str]) -> Optional[str]:
    """Normalize an optional health-check model name."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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


def _resolve_health_target(channel: Channel, actual_model_name: str) -> tuple[str, str]:
    """Resolve mapping directives for health checks."""
    raw_target = str(actual_model_name or "")
    prefix, separator, remainder = raw_target.partition(":")
    if separator and prefix == "responses" and remainder:
        return remainder, "responses"

    protocol = str(getattr(channel, "protocol_type", "openai") or "openai")
    if protocol == "anthropic":
        return raw_target, "anthropic_messages"
    if protocol == "openai":
        provider_variant = ChannelService._normalize_provider_variant(
            protocol,
            getattr(channel, "provider_variant", None),
        )
        if provider_variant == ChannelService.PROVIDER_VARIANT_OPENAI_IMAGE_COMPATIBLE:
            return raw_target, "openai_image_generation"
        return raw_target, "openai_chat"
    if protocol == "google":
        provider_variant = ChannelService._normalize_provider_variant(
            protocol,
            getattr(channel, "provider_variant", None),
        )
        if provider_variant == ChannelService.PROVIDER_VARIANT_GOOGLE_VERTEX_IMAGE:
            return raw_target, "google_vertex_sdk"
        return raw_target, "google_generate_content"
    return raw_target, "openai_chat"


def _select_health_check_model(db: Session, channel: Channel) -> Optional[str]:
    """Choose a stable mapped model for channel health checks."""
    explicit_model = _normalize_health_check_model(getattr(channel, "health_check_model", None))
    if explicit_model:
        return explicit_model

    mappings = (
        db.query(ModelChannelMapping)
        .filter(
            ModelChannelMapping.channel_id == channel.id,
            ModelChannelMapping.enabled == 1,
        )
        .all()
    )
    if not mappings:
        return None

    actual_model_names = [
        str(mapping.actual_model_name or "").strip()
        for mapping in mappings
        if str(mapping.actual_model_name or "").strip()
    ]
    if not actual_model_names:
        return None

    protocol = str(getattr(channel, "protocol_type", "openai") or "openai")
    if protocol == "google":
        non_image_targets = [
            actual_model_name
            for actual_model_name in actual_model_names
            if not GoogleVertexImageService.looks_like_image_model(
                GoogleVertexImageService.parse_model_candidates(actual_model_name)[0]
                if GoogleVertexImageService.parse_model_candidates(actual_model_name)
                else actual_model_name
            )
        ]
        if non_image_targets:
            return non_image_targets[0]
        # Google image-only channels should still be checked with a lightweight text model
        # unless an explicit health_check_model is configured on the channel.
        return _DEFAULT_GOOGLE_HEALTH_CHECK_MODEL

    preferred_exact_targets = (
        "responses:gpt-5.4",
        "responses:gpt-oss-120b-medium",
        "responses:gpt-5.3-codex-spark",
        "responses:gpt-5.4-mini",
        "responses:gpt-5.3-codex",
        "responses:gpt-5.2",
        "gpt-4o-mini",
        "claude-sonnet-4.5",
        "claude-haiku-4.5",
    )
    for preferred_target in preferred_exact_targets:
        if preferred_target in actual_model_names:
            return preferred_target

    non_codex_targets = [
        actual_model_name
        for actual_model_name in actual_model_names
        if "codex" not in actual_model_name.lower()
    ]
    if non_codex_targets:
        return non_codex_targets[0]

    return actual_model_names[0]


def _is_image_only_channel(db: Session, channel: Channel) -> bool:
    """Return True when all enabled mappings on the channel target image models."""
    mapped_models = (
        db.query(UnifiedModel.model_type)
        .join(ModelChannelMapping, ModelChannelMapping.unified_model_id == UnifiedModel.id)
        .filter(
            ModelChannelMapping.channel_id == channel.id,
            ModelChannelMapping.enabled == 1,
            UnifiedModel.enabled == 1,
        )
        .all()
    )
    if not mapped_models:
        return False
    return all(str(model_type or "") == "image" for model_type, in mapped_models)


def _should_skip_scheduled_check(db: Session, channel: Channel, now: datetime) -> bool:
    """Image-only channels are checked much less frequently to avoid noisy probes."""
    if not _is_image_only_channel(db, channel):
        return False

    interval_seconds = get_system_config(
        db,
        "image_channel_health_check_interval",
        _IMAGE_CHANNEL_HEALTH_CHECK_INTERVAL_SECONDS,
    )
    last_checked = channel.last_health_check_at
    if last_checked is None:
        return False
    return (now - last_checked).total_seconds() < int(interval_seconds)


class HealthService:
    """Concurrent health checks for all enabled channels."""

    @staticmethod
    def _list_health_monitored_channels(db: Session) -> list[Channel]:
        return (
            db.query(Channel)
            .filter(
                Channel.enabled == 1,
                Channel.health_check_enabled == 1,
            )
            .all()
        )

    @staticmethod
    async def check_all_channels(db: Session) -> list[dict]:
        """
        Check all enabled channels concurrently.

        For each channel, pick the first mapped model to use as a test model.
        Updates channel health state and writes HealthCheckLog entries.

        Returns:
            List of dicts with check results per channel.
        """
        channels = HealthService._list_health_monitored_channels(db)
        if not channels:
            return []

        tasks = []
        task_channels: list[Channel] = []
        output: list[dict] = []
        now = datetime.utcnow()
        for channel in channels:
            if _should_skip_scheduled_check(db, channel, now):
                logger.info(
                    "Skipping scheduled health check for image-only channel %s (%d); last checked at %s",
                    channel.name,
                    channel.id,
                    channel.last_health_check_at.isoformat() if channel.last_health_check_at else None,
                )
                output.append({
                    "channel_id": channel.id,
                    "channel_name": channel.name,
                    "is_healthy": bool(channel.is_healthy),
                    "response_time_ms": None,
                    "error": None,
                    "health_score": channel.health_score,
                    "failure_count": channel.failure_count,
                    "skipped": True,
                })
                continue
            actual_model_name = _select_health_check_model(db, channel)
            tasks.append(HealthService._check_and_record(db, channel, actual_model_name))
            task_channels.append(channel)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results -- gather may return exceptions for individual tasks
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Health check task failed for channel %s: %s",
                    task_channels[i].name,
                    result,
                )
                output.append({
                    "channel_id": task_channels[i].id,
                    "channel_name": task_channels[i].name,
                    "is_healthy": False,
                    "error": str(result),
                })
            else:
                output.append(result)

        return output

    @staticmethod
    async def check_single_channel(
        db: Session,
        channel_id: int,
        override_model_name: Optional[str] = None,
    ) -> dict:
        """
        Run a health check on a single channel.

        Raises:
            ServiceException: if channel not found.
        """
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        actual_model_name = (
            _normalize_health_check_model(override_model_name)
            or _select_health_check_model(db, channel)
        )

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
        upstream_model_name, upstream_api = _resolve_health_target(channel, actual_model_name)
        if upstream_api == "anthropic_messages":
            header_protocol = "anthropic"
        elif upstream_api == "openai_image_generation":
            header_protocol = "openai"
        elif upstream_api == "google_vertex_sdk":
            header_protocol = "google"
        elif upstream_api == "google_generate_content":
            header_protocol = "google"
        else:
            header_protocol = "openai"

        if upstream_api == "google_vertex_sdk":
            start = time.time()
            try:
                await GoogleVertexImageService.health_check(channel.api_key, upstream_model_name)
                elapsed_ms = int((time.time() - start) * 1000)
                return True, elapsed_ms, None
            except Exception as exc:
                elapsed_ms = int((time.time() - start) * 1000)
                return False, elapsed_ms, str(exc)
        if upstream_api == "responses":
            url = f"{base_url}/responses"
            payload = {
                "model": upstream_model_name,
                "input": "Hi",
                "max_output_tokens": 5,
                "stream": False,
                "store": False,
            }
        elif upstream_api == "openai_image_generation":
            url = (
                f"{base_url}/images/generations"
                if base_url.endswith("/v1")
                else f"{base_url}/v1/images/generations"
            )
            payload = {
                "model": upstream_model_name,
                "prompt": "生成一张包含字母 OK 的简单测试图片",
                "n": 1,
                "response_format": "b64_json",
            }
        elif protocol == "openai":
            url = f"{base_url}/chat/completions"
            payload = {
                "model": upstream_model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
                "stream": False,
            }
        elif protocol == "anthropic":
            url = f"{base_url}/messages"
            payload = {
                "model": upstream_model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
        elif protocol == "google":
            url = f"{base_url}/v1beta/models/{upstream_model_name}:generateContent"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Reply with OK only."}]}],
                "generationConfig": {"maxOutputTokens": 5},
            }
        else:
            return False, None, f"Unsupported protocol type: {protocol}"

        # Build headers using channel auth_header_type (same logic as proxy_service)
        auth_header_type = getattr(channel, "auth_header_type", None)
        if not auth_header_type:
            auth_header_type = "authorization" if header_protocol == "openai" else "x-api-key"

        headers: dict = {
            "Content-Type": "application/json",
            "User-Agent": _UPSTREAM_DEFAULT_USER_AGENT,
        }
        if header_protocol == "anthropic":
            headers["anthropic-version"] = "2023-06-01"

        if header_protocol == "google" and auth_header_type in {"x-goog-api-key", "x-api-key"}:
            headers["x-goog-api-key"] = channel.api_key
        elif auth_header_type == "authorization":
            headers["Authorization"] = f"Bearer {channel.api_key}"
        elif header_protocol == "openai" and auth_header_type == "x-api-key":
            headers["x-api-key"] = channel.api_key
            headers["Authorization"] = f"Bearer {channel.api_key}"
        elif header_protocol == "anthropic" and auth_header_type in {"x-api-key", "anthropic-api-key"}:
            headers["x-api-key"] = channel.api_key
            headers["anthropic-api-key"] = channel.api_key
        elif auth_header_type == "anthropic-api-key":
            headers["anthropic-api-key"] = channel.api_key
        else:  # x-api-key
            headers["x-api-key"] = channel.api_key

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
        channels = HealthService._list_health_monitored_channels(db)

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
                "health_check_enabled": bool(ch.health_check_enabled),
                "is_healthy": bool(ch.is_healthy),
                "health_score": ch.health_score,
                "failure_count": ch.failure_count,
                "health_check_model": _normalize_health_check_model(ch.health_check_model),
                "effective_health_check_model": _select_health_check_model(db, ch),
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
