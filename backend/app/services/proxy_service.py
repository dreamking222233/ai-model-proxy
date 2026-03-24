"""Proxy service -- the core request forwarding engine.

Handles OpenAI and Anthropic protocol forwarding with:
- Model resolution and override rules
- Multi-channel failover
- SSE streaming and non-streaming modes
- Token usage extraction and balance deduction
- Request logging and consumption records
- Circuit breaker support
"""
from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from typing import Optional

from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.models.user import SysUser, UserApiKey
from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.models.log import (
    RequestLog,
    UserBalance,
    ConsumptionRecord,
    SystemConfig,
    UserSubscription,
)
from app.services.model_service import ModelService
from app.services.health_service import get_system_config
from app.core.exceptions import ServiceException
from app.middleware.cache_middleware import CacheMiddleware
from app.middleware.stream_cache_middleware import StreamCacheMiddleware

logger = logging.getLogger(__name__)

# Default timeout for upstream requests (seconds)
_UPSTREAM_TIMEOUT = 120.0
# Timeout for upstream connection establishment
_UPSTREAM_CONNECT_TIMEOUT = 15.0
# Some upstream gateways block generic client defaults like ``python-httpx``.
_UPSTREAM_DEFAULT_USER_AGENT = "Mozilla/5.0"


class ResponsesTurnError(Exception):
    """Internal error used to decide whether a websocket turn can retry."""

    def __init__(self, message: str, can_retry: bool):
        self.can_retry = can_retry
        super().__init__(message)


class ProxyService:
    """Stateless proxy that forwards LLM requests through managed channels."""

    _LEGACY_CLAUDE_TOOL_CONTEXT_GUARD_TOKENS = 20000
    _LEGACY_CLAUDE_TOOL_CONTEXT_HARD_GUARD_TOKENS = 60000
    _LEGACY_CLAUDE_TOOL_CONTEXT_GUARD_MESSAGE_COUNT = 20

    @staticmethod
    def _is_legacy_kiro_amazonq_host(channel: Channel, model_name: Optional[str] = None) -> bool:
        """
        Compatibility rewrites are disabled to preserve upstream request integrity.
        """
        return False

    @staticmethod
    def _is_kiro_amazonq_channel(channel: Channel, model_name: Optional[str] = None) -> bool:
        """
        Upstream compatibility rewrites are disabled; requests should be
        forwarded as-is.
        """
        return False

    @staticmethod
    def _should_apply_kiro_amazonq_compat(
        channel: Channel,
        model_name: Optional[str] = None,
        force_compat: bool = False,
    ) -> bool:
        """Compatibility rewrites are disabled; preserve the original request."""
        return False

    @staticmethod
    def _estimate_message_text_tokens(messages) -> int:
        """Roughly estimate tokens from mixed Anthropic/OpenAI message content."""
        if not isinstance(messages, list):
            return 0

        total_length = 0
        for message in messages:
            if not isinstance(message, dict):
                total_length += len(str(message))
                continue

            content = message.get("content", "")
            if isinstance(content, str):
                total_length += len(content)
                continue

            if not isinstance(content, list):
                total_length += len(str(content))
                continue

            for part in content:
                if isinstance(part, str):
                    total_length += len(part)
                    continue
                if not isinstance(part, dict):
                    total_length += len(str(part))
                    continue

                part_type = str(part.get("type", "") or "")
                if part_type in {"text", "input_text", "output_text"}:
                    total_length += len(str(part.get("text", "") or ""))
                else:
                    total_length += len(json.dumps(part, ensure_ascii=False))

        return int(total_length / 2.5)

    @staticmethod
    def estimate_anthropic_input_tokens(request_data: dict) -> int:
        """Approximate Anthropic input tokens for ``/messages/count_tokens``."""
        total_tokens = ProxyService._estimate_message_text_tokens(
            request_data.get("messages")
        )

        for field in (
            "system",
            "tools",
            "tool_choice",
            "metadata",
            "thinking",
            "context_management",
            "betas",
        ):
            value = request_data.get(field)
            if value is None:
                continue

            if isinstance(value, str):
                total_tokens += int(len(value) / 2.5)
            else:
                total_tokens += int(len(json.dumps(value, ensure_ascii=False)) / 2.5)

        return total_tokens

    @staticmethod
    def _guard_legacy_claude_tool_context(
        channel: Channel,
        requested_model: str,
        request_data: dict,
    ) -> None:
        """
        Block long-context Anthropic tool calls on the legacy 43.156 Claude relay.

        Diagnostics show this upstream can emit correct ``tool_use`` events for
        short prompts, but starts returning empty content or trivial text once
        tool-bearing contexts become large. Failing fast with an actionable 400
        is safer than returning a misleading 200 success to Claude Code.
        """
        if not ProxyService._is_legacy_kiro_amazonq_host(channel, requested_model):
            return
        if "tools" not in request_data:
            return

        messages = request_data.get("messages")
        message_count = len(messages) if isinstance(messages, list) else 0
        history_tokens = ProxyService._estimate_message_text_tokens(messages)
        total_estimated_tokens = ProxyService.estimate_anthropic_input_tokens(request_data)
        if (
            history_tokens < ProxyService._LEGACY_CLAUDE_TOOL_CONTEXT_HARD_GUARD_TOKENS
            and (
                message_count < ProxyService._LEGACY_CLAUDE_TOOL_CONTEXT_GUARD_MESSAGE_COUNT
                or history_tokens < ProxyService._LEGACY_CLAUDE_TOOL_CONTEXT_GUARD_TOKENS
            )
        ):
            return

        preview_text = ""
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    preview_text = content.strip()[:200]
                    break
                if isinstance(content, list):
                    collected_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("text"):
                            collected_parts.append(str(part.get("text")))
                    preview_candidate = "\n".join(collected_parts).strip()
                    if preview_candidate:
                        preview_text = preview_candidate[:200]
                        break

        system_preview = ""
        system_value = request_data.get("system")
        if isinstance(system_value, str):
            system_preview = system_value.strip()[:200]
        elif isinstance(system_value, list):
            collected_parts = []
            for part in system_value:
                if isinstance(part, str):
                    collected_parts.append(part)
                elif isinstance(part, dict) and part.get("text"):
                    collected_parts.append(str(part.get("text")))
            system_preview = "\n".join(collected_parts).strip()[:200]

        tools_value = request_data.get("tools")
        tool_count = len(tools_value) if isinstance(tools_value, list) else 0
        tool_names = []
        if isinstance(tools_value, list):
            for tool in tools_value[:8]:
                if isinstance(tool, dict) and tool.get("name"):
                    tool_names.append(str(tool.get("name")))

        preview_lower = preview_text.lstrip().lower()
        if preview_lower.startswith("<system-reminder>") and message_count <= 6:
            logger.info(
                "Allowing large bootstrap-style Claude tool request on legacy relay %s: history_tokens=%s total_estimated_tokens=%s message_count=%s preview=%r",
                channel.name,
                history_tokens,
                total_estimated_tokens,
                message_count,
                preview_text,
            )
            return

        logger.warning(
            "Blocking long-context Claude tool request on legacy relay %s: history_tokens=%s total_estimated_tokens=%s requested_model=%s message_count=%s tool_count=%s tool_names=%s preview=%r system_preview=%r",
            channel.name,
            history_tokens,
            total_estimated_tokens,
            requested_model,
            message_count,
            tool_count,
            ",".join(tool_names) if tool_names else "none",
            preview_text,
            system_preview,
        )
        return

    @staticmethod
    def _stringify_legacy_function_content(content):
        """Convert tool/function message content into a legacy string payload."""
        if content is None or isinstance(content, str):
            return content
        if isinstance(content, dict):
            return json.dumps(content, ensure_ascii=False)
        if not isinstance(content, list):
            return str(content)

        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                parts.append(str(item))
                continue

            item_type = str(item.get("type", "") or "")
            if item_type in {"text", "input_text", "output_text"} and item.get("text") is not None:
                parts.append(str(item.get("text")))
            elif "text" in item and item.get("text") is not None:
                parts.append(str(item.get("text")))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))

        return "\n".join(part for part in parts if part)

    @staticmethod
    def _convert_openai_tool_history_for_kiro(messages):
        """
        Convert new-style OpenAI tool history into the legacy function-call form.

        The Kiro / Amazon Q relay accepts top-level ``tools`` definitions, but
        rejects historical ``assistant.tool_calls`` plus ``tool`` messages with
        ``Improperly formed request``. Rewriting only the history preserves the
        current channel while keeping top-level tool support intact.
        """
        if not isinstance(messages, list):
            return messages

        converted_messages = []
        tool_name_by_id: dict[str, str] = {}

        for raw_message in messages:
            if not isinstance(raw_message, dict):
                converted_messages.append(raw_message)
                continue

            message = copy.deepcopy(raw_message)
            role = str(message.get("role", "") or "")
            tool_calls = message.get("tool_calls")

            if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
                base_message = {
                    key: value
                    for key, value in message.items()
                    if key not in {"tool_calls", "tool_call_id"}
                }

                for index, tool_call in enumerate(tool_calls):
                    if not isinstance(tool_call, dict):
                        continue

                    function_payload = tool_call.get("function")
                    if not isinstance(function_payload, dict):
                        continue

                    call_id = str(tool_call.get("id", "") or "")
                    function_name = str(function_payload.get("name", "") or "")
                    if call_id and function_name:
                        tool_name_by_id[call_id] = function_name

                    legacy_message = copy.deepcopy(base_message)
                    legacy_message["function_call"] = copy.deepcopy(function_payload)

                    content = legacy_message.get("content")
                    if content is not None and not isinstance(content, str):
                        legacy_message["content"] = ProxyService._stringify_legacy_function_content(content)
                    if index > 0:
                        legacy_message["content"] = None

                    converted_messages.append(legacy_message)

                continue

            if role == "tool":
                tool_call_id = str(message.pop("tool_call_id", "") or "")
                message["role"] = "function"
                message["name"] = (
                    str(message.get("name", "") or "")
                    or tool_name_by_id.get(tool_call_id)
                    or "tool"
                )
                message["content"] = ProxyService._stringify_legacy_function_content(
                    message.get("content")
                )
                converted_messages.append(message)
                continue

            if role == "function":
                message["content"] = ProxyService._stringify_legacy_function_content(
                    message.get("content")
                )

            converted_messages.append(message)

        return converted_messages

    @staticmethod
    def _prepare_openai_request_for_channel(
        channel: Channel,
        request_data: dict,
        force_compat: bool = False,
    ) -> dict:
        """Forward OpenAI requests without compatibility rewrites."""
        return copy.deepcopy(request_data)

    @staticmethod
    def _sanitize_anthropic_content_for_kiro(content):
        """Preserve Anthropic content blocks without compatibility rewrites."""
        return copy.deepcopy(content)

    @staticmethod
    def _prepare_anthropic_request_for_channel(
        channel: Channel,
        request_data: dict,
        force_compat: bool = False,
    ) -> dict:
        """Forward Anthropic requests without compatibility rewrites."""
        return copy.deepcopy(request_data)

    @staticmethod
    def _extract_upstream_error_message(error_detail: str) -> str:
        """Unwrap nested upstream JSON error bodies into a short readable string."""
        message = str(error_detail or "").strip()
        if ": " in message and message.lower().startswith("upstream returned http"):
            message = message.split(": ", 1)[1].strip()

        for _ in range(3):
            try:
                parsed = json.loads(message)
            except (TypeError, ValueError):
                break

            if isinstance(parsed, dict):
                nested_error = parsed.get("error")
                if isinstance(nested_error, dict):
                    nested_message = nested_error.get("message")
                    if isinstance(nested_message, str) and nested_message.strip():
                        message = nested_message.strip()
                        continue

                nested_message = parsed.get("message")
                if isinstance(nested_message, str) and nested_message.strip():
                    message = nested_message.strip()
                    continue
            break

        return message

    @staticmethod
    def _map_upstream_request_error(exc: Exception) -> Optional[ServiceException]:
        """
        Map upstream 4xx request-format failures to user-facing 400 errors.

        These should not count as channel health failures or be wrapped as 503.
        """
        if isinstance(exc, ServiceException):
            if 400 <= exc.status_code < 500:
                return exc
            return None

        error_detail = str(exc or "").strip()
        lowered = error_detail.lower()
        if not any(
            marker in lowered
            for marker in (
                "http 400",
                "http 413",
                "http 422",
                "improperly formed request",
                "invalid beta flag",
                "invalid signature in thinking block",
                "payload too large",
                "context length",
                "context window",
                "too many tokens",
                "maximum context length",
                "token limit",
            )
        ):
            return None

        upstream_message = ProxyService._extract_upstream_error_message(error_detail)

        if "invalid beta flag" in lowered:
            return ServiceException(400, upstream_message, "UPSTREAM_INVALID_REQUEST")

        if "invalid signature in thinking block" in lowered:
            return ServiceException(400, upstream_message, "UPSTREAM_INVALID_REQUEST")

        if any(
            marker in lowered
            for marker in (
                "http 413",
                "payload too large",
                "request too large",
                "context length",
                "context window",
                "too many tokens",
            )
        ):
            return ServiceException(400, upstream_message, "CONTENT_TOO_LONG")

        if "improperly formed request" in lowered:
            return ServiceException(400, upstream_message, "UPSTREAM_INVALID_REQUEST")

        return ServiceException(
            400,
            upstream_message,
            "UPSTREAM_INVALID_REQUEST",
        )

    # -------------------------------------------------------------------
    # OpenAI Responses API entry point (for Codex CLI)
    # -------------------------------------------------------------------

    @staticmethod
    async def handle_responses_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        request_data: dict,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ):
        """
        Handle OpenAI Responses API format request (/v1/responses).

        This endpoint is used by Codex CLI and forwards to the upstream
        ``/responses`` endpoint.
        """
        request_id = str(uuid.uuid4())
        client_request = copy.deepcopy(request_data)
        requested_model = str(client_request.get("model", "") or "")
        is_stream = bool(client_request.get("stream", True))
        client_request["stream"] = is_stream

        unified_model, channels = ProxyService._prepare_responses_request_context(
            db, user, requested_model
        )

        last_error: Exception | None = None
        request_error: ServiceException | None = None
        for channel, actual_model_name in channels:
            try:
                channel_request = copy.deepcopy(client_request)
                channel_request["model"] = actual_model_name
                channel_request = ProxyService._prepare_responses_request_body(
                    actual_model_name,
                    channel_request,
                )

                if is_stream:
                    return await ProxyService._stream_responses_request(
                        db, user, api_key_record, channel, unified_model,
                        channel_request, request_id, requested_model, client_ip,
                        request_headers=request_headers,
                    )
                return await ProxyService._non_stream_responses_request(
                    db, user, api_key_record, channel, unified_model,
                    channel_request, request_id, requested_model, client_ip,
                    request_headers=request_headers,
                )
            except ServiceException as exc:
                if exc.error_code in {"UPSTREAM_INVALID_REQUEST", "CONTENT_TOO_LONG"}:
                    request_error = exc
                    logger.info(
                        "Responses channel %s (%d) rejected request without counting channel failure: %s",
                        channel.name, channel.id, exc.detail,
                    )
                    continue
                raise
            except Exception as exc:
                mapped_request_error = ProxyService._map_upstream_request_error(exc)
                if mapped_request_error:
                    request_error = mapped_request_error
                    logger.info(
                        "Responses channel %s (%d) rejected request without counting channel failure: %s",
                        channel.name, channel.id, mapped_request_error.detail,
                    )
                    continue

                last_error = exc
                logger.warning(
                    "Responses channel %s (%d) failed for model %s: %s",
                    channel.name, channel.id, actual_model_name, exc,
                )
                ProxyService._record_channel_failure(db, channel)
                continue

        if request_error:
            error_detail = request_error.detail
        else:
            error_detail = str(last_error) if last_error else "Unknown error"
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
        if request_error:
            raise request_error
        raise ServiceException(503, f"All channels failed: {error_detail}", "ALL_CHANNELS_FAILED")

    @staticmethod
    async def handle_responses_websocket(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        websocket: WebSocket,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Serve a Codex-compatible websocket session on ``GET /v1/responses``."""
        last_request: dict | None = None
        last_response_output: list = []

        while True:
            try:
                raw_message = await websocket.receive_text()
            except WebSocketDisconnect:
                return

            request_id = str(uuid.uuid4())
            try:
                incoming_request = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps(
                    ProxyService._build_responses_error_payload(
                        "websocket request must be valid JSON",
                        status_code=400,
                        error_type="invalid_request_error",
                    ),
                    ensure_ascii=False,
                ))
                continue

            try:
                normalized_request, state_request, is_prewarm = (
                    ProxyService._normalize_responses_websocket_request(
                        incoming_request,
                        last_request,
                        last_response_output,
                    )
                )
            except ServiceException as exc:
                await websocket.send_text(json.dumps(
                    ProxyService._build_responses_error_payload(
                        exc.detail,
                        status_code=exc.status_code,
                        error_type="invalid_request_error",
                    ),
                    ensure_ascii=False,
                ))
                continue

            last_request = copy.deepcopy(state_request)
            last_response_output = []

            if is_prewarm:
                for payload in ProxyService._build_responses_prewarm_payloads(state_request):
                    await websocket.send_text(json.dumps(payload, ensure_ascii=False))
                continue

            requested_model = str(state_request.get("model", "") or "")
            try:
                unified_model, channels = ProxyService._prepare_responses_request_context(
                    db, user, requested_model
                )
            except ServiceException as exc:
                await websocket.send_text(json.dumps(
                    ProxyService._build_responses_error_payload(
                        exc.detail,
                        status_code=exc.status_code,
                        error_type="invalid_request_error",
                    ),
                    ensure_ascii=False,
                ))
                return

            turn_completed = False
            last_error: Exception | None = None
            for channel, actual_model_name in channels:
                channel_request = copy.deepcopy(normalized_request)
                channel_request["model"] = actual_model_name
                channel_request = ProxyService._prepare_responses_request_body(
                    actual_model_name,
                    channel_request,
                )
                started_at = time.time()
                try:
                    completed_output, input_tokens, output_tokens = (
                        await ProxyService._forward_responses_websocket_turn(
                            websocket,
                            channel,
                            channel_request,
                            requested_model,
                            request_headers=request_headers,
                        )
                    )
                    response_time_ms = int((time.time() - started_at) * 1000)
                    ProxyService._record_success(db, channel)
                    ProxyService._deduct_balance_and_log(
                        db, user, api_key_record, unified_model, request_id,
                        requested_model, input_tokens, output_tokens, channel,
                        client_ip, response_time_ms, is_stream=True,
                    )
                    last_response_output = completed_output
                    turn_completed = True
                    break
                except ResponsesTurnError as exc:
                    response_time_ms = int((time.time() - started_at) * 1000)
                    last_error = exc
                    logger.warning(
                        "Responses websocket channel %s (%d) failed for model %s: %s",
                        channel.name, channel.id, actual_model_name, exc,
                    )
                    ProxyService._record_channel_failure(db, channel)
                    if not exc.can_retry:
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True, str(exc), channel=channel,
                            response_time_ms=response_time_ms,
                        )
                        return
                    continue
                except Exception as exc:
                    response_time_ms = int((time.time() - started_at) * 1000)
                    last_error = exc
                    logger.warning(
                        "Responses websocket channel %s (%d) failed for model %s: %s",
                        channel.name, channel.id, actual_model_name, exc,
                    )
                    ProxyService._record_channel_failure(db, channel)
                    ProxyService._log_failed_request(
                        db, user, api_key_record, request_id, requested_model,
                        client_ip, True, str(exc), channel=channel,
                        response_time_ms=response_time_ms,
                    )
                    return

            if turn_completed:
                continue

            error_detail = str(last_error) if last_error else "Unknown error"
            ProxyService._log_failed_request(
                db, user, api_key_record, request_id, requested_model,
                client_ip, True, error_detail,
            )
            await websocket.send_text(json.dumps(
                ProxyService._build_responses_error_payload(
                    f"All channels failed: {error_detail}",
                    status_code=503,
                ),
                ensure_ascii=False,
            ))
            return

    @staticmethod
    def _prepare_responses_request_context(
        db: Session,
        user: SysUser,
        requested_model: str,
    ) -> tuple[UnifiedModel, list[tuple[Channel, str]]]:
        """Resolve a Responses request into a model plus channel candidates."""
        if user.subscription_type == "balance":
            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
            if not balance or balance.balance <= 0:
                raise ServiceException(402, "余额不足，请充值", "INSUFFICIENT_BALANCE")

        unified_model = ModelService.resolve_model(db, requested_model)
        if not unified_model:
            raise ServiceException(404, f"Model '{requested_model}' not found", "MODEL_NOT_FOUND")

        channels = ModelService.get_available_channels(db, unified_model.id)
        if not channels:
            raise ServiceException(503, "No available channel for this model", "NO_CHANNEL")
        return unified_model, channels

    @staticmethod
    def _normalize_responses_input(input_data) -> list:
        """Normalize Responses ``input`` into an item array."""
        if isinstance(input_data, str):
            return [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_data}],
                }
            ]
        if input_data is None:
            return []
        if isinstance(input_data, dict):
            input_data = [input_data]
        if not isinstance(input_data, list):
            return [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": str(input_data)}],
                }
            ]

        normalized_items = []
        for raw_item in input_data:
            if not isinstance(raw_item, dict):
                normalized_items.append({
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": str(raw_item)}],
                })
                continue

            item = copy.deepcopy(raw_item)
            if item.get("type") == "message":
                content = item.get("content")
                if isinstance(content, str):
                    item["content"] = [{"type": "input_text", "text": content}]
                elif content is None:
                    item["content"] = []
                elif not isinstance(content, list):
                    item["content"] = [{"type": "input_text", "text": str(content)}]
            normalized_items.append(item)
        return normalized_items

    @staticmethod
    def _prepare_responses_request_body(model_name: str, request_data: dict) -> dict:
        """Apply compatibility normalization before forwarding to upstream ``/responses``."""
        prepared = copy.deepcopy(request_data)
        prepared["input"] = ProxyService._normalize_responses_input(prepared.get("input"))
        prepared.setdefault("store", False)
        prepared.setdefault("parallel_tool_calls", True)
        if "stream" not in prepared:
            prepared["stream"] = True

        model_name_lower = model_name.lower()
        if "codex" in model_name_lower:
            prepared.setdefault("include", ["reasoning.encrypted_content"])

            for field in (
                "max_output_tokens",
                "max_completion_tokens",
                "temperature",
                "top_p",
                "truncation",
                "user",
                "context_management",
            ):
                prepared.pop(field, None)

            service_tier = prepared.get("service_tier")
            if service_tier and service_tier != "priority":
                prepared.pop("service_tier", None)

            for item in prepared["input"]:
                if isinstance(item, dict) and item.get("type") == "message" and item.get("role") == "system":
                    item["role"] = "developer"

        return prepared

    @staticmethod
    def _normalize_responses_websocket_request(
        request_data: dict,
        last_request: dict | None,
        last_response_output: list,
    ) -> tuple[dict, dict, bool]:
        """Normalize websocket ``response.create`` / ``response.append`` payloads."""
        request_type = str(request_data.get("type", "") or "").strip()
        if request_type == "response.create":
            if not last_request:
                normalized = copy.deepcopy(request_data)
                normalized.pop("type", None)
                normalized["input"] = ProxyService._normalize_responses_input(
                    normalized.get("input")
                )
                if not normalized.get("model"):
                    raise ServiceException(400, "missing model in response.create request", "INVALID_REQUEST")
                normalized["stream"] = True
                is_prewarm = bool(normalized.pop("generate", True) is False)
                return normalized, copy.deepcopy(normalized), is_prewarm

            return ProxyService._normalize_followup_responses_websocket_request(
                request_data,
                last_request,
                last_response_output,
            )

        if request_type == "response.append":
            return ProxyService._normalize_followup_responses_websocket_request(
                request_data,
                last_request,
                last_response_output,
            )

        raise ServiceException(400, f"unsupported websocket request type: {request_type}", "INVALID_REQUEST")

    @staticmethod
    def _normalize_followup_responses_websocket_request(
        request_data: dict,
        last_request: dict | None,
        last_response_output: list,
    ) -> tuple[dict, dict, bool]:
        """Merge follow-up websocket input with prior request/response state."""
        if not last_request:
            raise ServiceException(400, "websocket request received before response.create", "INVALID_REQUEST")

        next_input = request_data.get("input")
        if next_input is None:
            raise ServiceException(400, "websocket request requires field: input", "INVALID_REQUEST")

        merged_input = []
        merged_input.extend(ProxyService._normalize_responses_input(last_request.get("input")))
        merged_input.extend(copy.deepcopy(last_response_output or []))
        merged_input.extend(ProxyService._normalize_responses_input(next_input))

        normalized = copy.deepcopy(request_data)
        normalized.pop("type", None)
        normalized.pop("previous_response_id", None)
        normalized["input"] = merged_input
        normalized["stream"] = True

        if not normalized.get("model"):
            normalized["model"] = last_request.get("model")
        if "instructions" not in normalized and "instructions" in last_request:
            normalized["instructions"] = copy.deepcopy(last_request.get("instructions"))

        return normalized, copy.deepcopy(normalized), False

    @staticmethod
    def _build_responses_prewarm_payloads(request_data: dict) -> list[dict]:
        """Return a synthetic empty turn for Codex websocket prewarm requests."""
        response_id = f"resp_prewarm_{uuid.uuid4().hex[:24]}"
        created_at = int(time.time())
        model_name = str(request_data.get("model", "") or "")
        return [
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": created_at,
                    "status": "in_progress",
                    "background": False,
                    "error": None,
                    "model": model_name,
                    "output": [],
                },
            },
            {
                "type": "response.completed",
                "sequence_number": 1,
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": created_at,
                    "status": "completed",
                    "background": False,
                    "error": None,
                    "model": model_name,
                    "output": [],
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                },
            },
        ]

    @staticmethod
    async def _stream_responses_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> StreamingResponse:
        """Forward a streaming Responses request to upstream ``/responses``."""
        start_time = time.time()
        model_name = request_data.get("model", requested_model)

        billing_input_tokens = 0
        billing_output_tokens = 0

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        async def upstream_call(collector, collected_usage):
            """上游 Responses API 流式调用"""
            input_tokens = 0
            output_tokens = 0
            completed = False
            saw_error = False
            error_message = ""
            stream_error = None

            try:
                async for payload in ProxyService._iter_responses_upstream_payloads(
                    channel,
                    request_data,
                    requested_model,
                    request_headers=request_headers,
                ):
                    payload_type = str(payload.get("type", "") or "")
                    if payload_type == "response.completed":
                        completed = True
                        input_tokens, output_tokens = ProxyService._extract_responses_usage(payload)
                        collected_usage["prompt_tokens"] = input_tokens
                        collected_usage["completion_tokens"] = output_tokens
                        # 记录结束
                        collector.add_chunk("", "stop")
                    elif payload_type == "error":
                        saw_error = True
                        error_message = (
                            payload.get("error", {}).get("message")
                            or "Upstream responses error"
                        )
                    elif payload_type == "response.output_text.delta":
                        # 收集文本内容
                        delta = payload.get("delta", "")
                        if delta:
                            collector.add_chunk(delta)

                    yield ProxyService._payload_to_sse(payload)

                if completed:
                    yield "data: [DONE]\n\n"
                else:
                    if saw_error:
                        stream_error = Exception(error_message or "Upstream responses error")
                    else:
                        stream_error = Exception("stream closed before response.completed")
                        yield ProxyService._payload_to_sse(
                            ProxyService._build_responses_error_payload(
                                str(stream_error),
                                status_code=408,
                            )
                        )
            except Exception as exc:
                stream_error = exc
                logger.error("Responses API stream error on channel %s: %s", channel.name, exc)
                yield ProxyService._payload_to_sse(
                    ProxyService._build_responses_error_payload(
                        str(exc),
                        status_code=502,
                    )
                )
                raise

            billing_callback(input_tokens, output_tokens, False)

        async def event_generator():
            stream_error = None

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="responses",
                    model=model_name,
                    billing_callback=billing_callback,
                ):
                    yield sse_line

            except Exception as exc:
                stream_error = exc
                mapped_request_error = ProxyService._map_upstream_request_error(exc)
                error_message = mapped_request_error.detail if mapped_request_error else str(exc)
                logger.error("Responses API stream error on channel %s: %s", channel.name, exc)
                yield ProxyService._payload_to_sse(
                    ProxyService._build_responses_error_payload(
                        error_message,
                        status_code=mapped_request_error.status_code if mapped_request_error else 502,
                    )
                )
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                        )
                except Exception as accounting_err:
                    logger.error("Post-stream accounting error: %s", accounting_err)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    @staticmethod
    async def _forward_responses_websocket_turn(
        websocket: WebSocket,
        channel: Channel,
        request_data: dict,
        requested_model: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> tuple[list, int, int]:
        """Forward one websocket turn to upstream ``/responses`` SSE."""
        completed_output: list = []
        input_tokens = 0
        output_tokens = 0
        completed = False
        sent_any_payload = False
        saw_error = False
        error_message = ""

        try:
            async for payload in ProxyService._iter_responses_upstream_payloads(
                channel,
                request_data,
                requested_model,
                request_headers=request_headers,
            ):
                sent_any_payload = True
                payload_type = str(payload.get("type", "") or "")
                if payload_type == "response.completed":
                    completed = True
                    completed_output = ProxyService._extract_responses_output(payload)
                    input_tokens, output_tokens = ProxyService._extract_responses_usage(payload)
                elif payload_type == "error":
                    saw_error = True
                    error_message = (
                        payload.get("error", {}).get("message")
                        or "Upstream responses error"
                    )
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            if sent_any_payload:
                error_payload = ProxyService._build_responses_error_payload(
                    str(exc),
                    status_code=502,
                )
                await websocket.send_text(json.dumps(error_payload, ensure_ascii=False))
                raise ResponsesTurnError(str(exc), can_retry=False) from exc
            raise ResponsesTurnError(str(exc), can_retry=True) from exc

        if completed:
            return completed_output, input_tokens, output_tokens

        if saw_error:
            raise ResponsesTurnError(error_message or "Upstream responses error", can_retry=not sent_any_payload)

        if sent_any_payload:
            error_payload = ProxyService._build_responses_error_payload(
                "stream closed before response.completed",
                status_code=408,
            )
            await websocket.send_text(json.dumps(error_payload, ensure_ascii=False))
            raise ResponsesTurnError("stream closed before response.completed", can_retry=False)

        raise ResponsesTurnError("stream closed before response.completed", can_retry=True)

    @staticmethod
    async def _iter_responses_upstream_payloads(
        channel: Channel,
        request_data: dict,
        requested_model: str,
        request_headers: Optional[dict[str, str]] = None,
    ):
        """Yield parsed Responses payload dicts from upstream SSE or JSON."""
        start_url = channel.base_url.rstrip("/")
        url = f"{start_url}/responses"
        headers = ProxyService._build_headers(channel, "openai", request_headers=request_headers)
        timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=request_data, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise Exception(
                        f"Upstream returned HTTP {response.status_code}: "
                        f"{body.decode('utf-8', errors='replace')[:500]}"
                    )

                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    body = await response.aread()
                    body_text = body.decode("utf-8", errors="replace").strip()
                    if not body_text:
                        return
                    payload = ProxyService._parse_non_stream_responses_payload(body_text)
                    if payload is None:
                        raise Exception(f"Invalid upstream /responses body: {body_text[:500]}")
                    yield ProxyService._rewrite_response_model(payload, requested_model)
                    return

                async for line in response.aiter_lines():
                    payload = ProxyService._parse_responses_payload_line(line)
                    if payload is None:
                        continue
                    yield ProxyService._rewrite_response_model(payload, requested_model)

    @staticmethod
    def _parse_non_stream_responses_payload(raw_text: str) -> dict | None:
        """Parse a non-stream upstream response into a standard payload wrapper."""
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("type") == "response.completed":
            return payload
        if payload.get("object") == "response":
            return {"type": "response.completed", "response": payload}
        return payload

    @staticmethod
    def _parse_responses_payload_line(line: str) -> dict | None:
        """Parse one SSE line into a Responses payload dict."""
        stripped = line.strip()
        if not stripped or stripped.startswith("event:"):
            return None
        if stripped.startswith("data:"):
            stripped = stripped[5:].strip()
        if not stripped or stripped == "[DONE]":
            return None
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    @staticmethod
    def _rewrite_response_model(payload: dict, requested_model: str) -> dict:
        """Rewrite upstream model fields back to the client-requested model alias."""
        rewritten = copy.deepcopy(payload)
        if not requested_model:
            return rewritten
        if isinstance(rewritten.get("response"), dict):
            rewritten["response"]["model"] = requested_model
        elif rewritten.get("object") == "response":
            rewritten["model"] = requested_model
        return rewritten

    @staticmethod
    def _build_responses_error_payload(
        message: str,
        status_code: int = 500,
        error_type: str = "server_error",
    ) -> dict:
        """Build a websocket/SSE compatible Responses error event."""
        return {
            "type": "error",
            "status": status_code,
            "error": {
                "type": error_type,
                "message": message,
            },
        }

    @staticmethod
    def _payload_to_sse(payload: dict) -> str:
        """Render a Responses payload dict as an SSE event."""
        event_type = str(payload.get("type", "message") or "message")
        return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _extract_responses_usage(payload: dict) -> tuple[int, int]:
        """Extract input/output token usage from a Responses payload."""
        usage = {}
        if payload.get("type") == "response.completed":
            usage = payload.get("response", {}).get("usage", {}) or {}
        elif payload.get("object") == "response":
            usage = payload.get("usage", {}) or {}
        return (
            int(usage.get("input_tokens") or 0),
            int(usage.get("output_tokens") or 0),
        )

    @staticmethod
    def _extract_responses_output(payload: dict) -> list:
        """Extract ``response.output`` from a completed Responses payload."""
        if payload.get("type") == "response.completed":
            output = payload.get("response", {}).get("output", [])
            if isinstance(output, list):
                return copy.deepcopy(output)
        return []

    @staticmethod
    def _parse_non_stream_responses_body(raw_text: str) -> tuple[dict, int, int]:
        """Convert an SSE or wrapped Responses payload body into a response object."""
        response_body: dict | None = None

        for line in raw_text.splitlines():
            payload = ProxyService._parse_responses_payload_line(line)
            if payload and payload.get("type") == "response.completed":
                response_body = payload.get("response", {})

        if response_body is None:
            payload = ProxyService._parse_non_stream_responses_payload(raw_text)
            if payload and payload.get("type") == "response.completed":
                response_body = payload.get("response", {})
            elif payload and payload.get("object") == "response":
                response_body = payload

        if response_body is None:
            raise Exception(f"Invalid upstream /responses body: {raw_text[:500]}")

        input_tokens = int(response_body.get("usage", {}).get("input_tokens") or 0)
        output_tokens = int(response_body.get("usage", {}).get("output_tokens") or 0)
        return response_body, input_tokens, output_tokens

    @staticmethod
    async def _non_stream_responses_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> JSONResponse:
        """Forward a non-streaming Responses request to upstream ``/responses``."""
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/responses"
        headers = ProxyService._build_headers(channel, "openai", request_headers=request_headers)

        # Define upstream call function for passthrough middleware
        async def upstream_call():
            timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=request_data, headers=headers)

            if resp.status_code != 200:
                raise Exception(f"Upstream returned HTTP {resp.status_code}: {resp.text[:500]}")

            response_body, input_tokens, output_tokens = ProxyService._parse_non_stream_responses_body(
                resp.text
            )
            response_body = ProxyService._rewrite_response_model(response_body, requested_model)

            # Return standardized response format for the shared middleware contract
            return {
                "response": response_body,
                "model": request_data.get("model"),
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                }
            }

        # Shared passthrough middleware contract
        cache_response, cache_info = await CacheMiddleware.wrap_request(
            request_body=request_data,
            headers=request_headers or {},
            user=user,
            db=db,
            upstream_call=upstream_call,
            unified_model=unified_model,
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        # Extract response body and tokens
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)

        # Middleware is passthrough; billing tokens equal actual tokens
        billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
            cache_info=cache_info,
            user=user,
            actual_tokens={
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
            }
        )

        # Record success and do accounting with billing tokens
        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        response_headers = {"X-Request-ID": request_id}

        return JSONResponse(
            content=response_body,
            headers=response_headers,
        )

    # -------------------------------------------------------------------
    # OpenAI protocol entry point
    # -------------------------------------------------------------------

    @staticmethod
    async def handle_openai_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        request_data: dict,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ):
        """
        Handle an OpenAI-format ``/v1/chat/completions`` request.

        Workflow:
            1. Validate user balance.
            2. Validate request content length.
            3. Resolve model (apply override rules).
            4. Get available channels sorted by priority.
            5. Attempt each channel in order (failover).

        Returns:
            ``StreamingResponse`` for stream=true, or ``JSONResponse`` for
            non-streaming requests.

        Raises:
            ServiceException: on insufficient balance, model not found,
            or all channels failing.
        """
        request_id = str(uuid.uuid4())
        requested_model = request_data.get("model", "")
        is_stream = request_data.get("stream", False)

        # 1. Check user balance (only for balance mode users)
        if user.subscription_type == "balance":
            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
            if not balance or balance.balance <= 0:
                raise ServiceException(402, "余额不足，请充值", "INSUFFICIENT_BALANCE")
        # For unlimited mode users, subscription expiration is already checked in verify_api_key

        # 2. Validate request content length
        ProxyService._validate_request_length(db, request_data)

        # 2. Resolve model (apply override rules)
        unified_model = ModelService.resolve_model(db, requested_model)
        if not unified_model:
            raise ServiceException(404, f"Model '{requested_model}' not found", "MODEL_NOT_FOUND")

        # 3. Get available channels sorted by priority
        channels = ModelService.get_available_channels(db, unified_model.id)
        if not channels:
            raise ServiceException(503, "No available channel for this model", "NO_CHANNEL")

        # 4. Try each channel (failover)
        last_error: Exception | None = None
        request_error: ServiceException | None = None
        for channel, actual_model_name in channels:
            explicit_compat = ProxyService._is_kiro_amazonq_channel(channel, actual_model_name)
            legacy_compat_retry = (
                not explicit_compat
                and ProxyService._is_legacy_kiro_amazonq_host(channel, actual_model_name)
            )
            channel_request_error: ServiceException | None = None
            compat_attempts = [True] if explicit_compat else [False]
            if legacy_compat_retry:
                compat_attempts.append(True)

            for compat_mode in compat_attempts:
                try:
                    # Build upstream request with the actual model name
                    request_data_copy = dict(request_data)
                    request_data_copy["model"] = actual_model_name
                    request_data_copy = ProxyService._prepare_openai_request_for_channel(
                        channel,
                        request_data_copy,
                        force_compat=compat_mode,
                    )

                    if is_stream:
                        return await ProxyService._stream_openai_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                        )
                    else:
                        return await ProxyService._non_stream_openai_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                        )
                except ServiceException as exc:
                    if exc.error_code in {"UPSTREAM_INVALID_REQUEST", "CONTENT_TOO_LONG"}:
                        if legacy_compat_retry and not compat_mode:
                            logger.info(
                                "Channel %s (%d) rejected raw request, retrying with Kiro/AmazonQ compatibility: %s",
                                channel.name,
                                channel.id,
                                exc.detail,
                            )
                            continue

                        channel_request_error = exc
                        logger.info(
                            "Channel %s (%d) rejected request without counting channel failure: %s",
                            channel.name, channel.id, exc.detail,
                        )
                        break
                    raise  # Re-raise business exceptions immediately
                except Exception as e:
                    mapped_request_error = ProxyService._map_upstream_request_error(e)
                    if mapped_request_error:
                        if legacy_compat_retry and not compat_mode:
                            logger.info(
                                "Channel %s (%d) rejected raw request, retrying with Kiro/AmazonQ compatibility: %s",
                                channel.name,
                                channel.id,
                                mapped_request_error.detail,
                            )
                            continue

                        channel_request_error = mapped_request_error
                        logger.info(
                            "Channel %s (%d) rejected request without counting channel failure: %s",
                            channel.name, channel.id, mapped_request_error.detail,
                        )
                        break

                    last_error = e
                    logger.warning(
                        "Channel %s (%d) failed for model %s: %s",
                        channel.name, channel.id, actual_model_name, e,
                    )
                    ProxyService._record_channel_failure(db, channel)
                    channel_request_error = None
                    break

            if channel_request_error:
                request_error = channel_request_error
                continue

        # All channels exhausted
        if request_error:
            error_detail = request_error.detail
        else:
            error_detail = str(last_error) if last_error else "Unknown error"
        # Log the failure
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
        if request_error:
            raise request_error
        raise ServiceException(503, f"All channels failed: {error_detail}", "ALL_CHANNELS_FAILED")

    # -------------------------------------------------------------------
    # Anthropic protocol entry point
    # -------------------------------------------------------------------

    @staticmethod
    async def handle_anthropic_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        request_data: dict,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ):
        """
        Handle an Anthropic-format ``/v1/messages`` request.

        Same failover logic as OpenAI but with Anthropic message format.
        """
        request_id = str(uuid.uuid4())
        requested_model = request_data.get("model", "")
        is_stream = request_data.get("stream", False)

        # 1. Check user balance (only for balance mode users)
        if user.subscription_type == "balance":
            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
            if not balance or balance.balance <= 0:
                raise ServiceException(402, "余额不足，请充值", "INSUFFICIENT_BALANCE")
        # For unlimited mode users, subscription expiration is already checked in verify_api_key

        # 2. Validate request content length
        ProxyService._validate_request_length(db, request_data)

        # 2. Resolve model
        unified_model = ModelService.resolve_model(db, requested_model)
        if not unified_model:
            raise ServiceException(404, f"Model '{requested_model}' not found", "MODEL_NOT_FOUND")

        # 3. Get available channels
        channels = ModelService.get_available_channels(db, unified_model.id)
        if not channels:
            raise ServiceException(503, "No available channel for this model", "NO_CHANNEL")

        # 4. Failover
        last_error: Exception | None = None
        request_error: ServiceException | None = None
        for channel, actual_model_name in channels:
            explicit_compat = ProxyService._is_kiro_amazonq_channel(channel, actual_model_name)
            legacy_compat_retry = (
                not explicit_compat
                and ProxyService._is_legacy_kiro_amazonq_host(channel, actual_model_name)
            )
            channel_request_error: ServiceException | None = None
            compat_attempts = [True] if explicit_compat else [False]
            if legacy_compat_retry:
                compat_attempts.append(True)

            for compat_mode in compat_attempts:
                try:
                    request_data_copy = dict(request_data)
                    request_data_copy["model"] = actual_model_name
                    if not compat_mode:
                        ProxyService._guard_legacy_claude_tool_context(
                            channel,
                            requested_model,
                            request_data_copy,
                        )
                    request_data_copy = ProxyService._prepare_anthropic_request_for_channel(
                        channel,
                        request_data_copy,
                        force_compat=compat_mode,
                    )

                    if is_stream:
                        return await ProxyService._stream_anthropic_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                            force_compat=compat_mode,
                        )
                    else:
                        return await ProxyService._non_stream_anthropic_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                            force_compat=compat_mode,
                        )
                except ServiceException as exc:
                    if exc.error_code == "LEGACY_CLAUDE_TOOL_CONTEXT_LIMIT":
                        channel_request_error = exc
                        logger.info(
                            "Anthropic channel %s (%d) blocked long-context tool request before upstream call: %s",
                            channel.name,
                            channel.id,
                            exc.detail,
                        )
                        break
                    if exc.error_code in {"UPSTREAM_INVALID_REQUEST", "CONTENT_TOO_LONG"}:
                        if legacy_compat_retry and not compat_mode:
                            logger.info(
                                "Anthropic channel %s (%d) rejected raw request, retrying with Kiro/AmazonQ compatibility: %s",
                                channel.name,
                                channel.id,
                                exc.detail,
                            )
                            continue

                        channel_request_error = exc
                        logger.info(
                            "Anthropic channel %s (%d) rejected request without counting channel failure: %s",
                            channel.name, channel.id, exc.detail,
                        )
                        break
                    raise
                except Exception as e:
                    mapped_request_error = ProxyService._map_upstream_request_error(e)
                    if mapped_request_error:
                        if legacy_compat_retry and not compat_mode:
                            logger.info(
                                "Anthropic channel %s (%d) rejected raw request, retrying with Kiro/AmazonQ compatibility: %s",
                                channel.name,
                                channel.id,
                                mapped_request_error.detail,
                            )
                            continue

                        channel_request_error = mapped_request_error
                        logger.info(
                            "Anthropic channel %s (%d) rejected request without counting channel failure: %s",
                            channel.name, channel.id, mapped_request_error.detail,
                        )
                        break

                    last_error = e
                    logger.warning(
                        "Channel %s (%d) failed for model %s: %s",
                        channel.name, channel.id, actual_model_name, e,
                    )
                    ProxyService._record_channel_failure(db, channel)
                    channel_request_error = None
                    break

            if channel_request_error:
                request_error = channel_request_error
                continue

        if request_error:
            error_detail = request_error.detail
        else:
            error_detail = str(last_error) if last_error else "Unknown error"
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
        if request_error:
            raise request_error
        raise ServiceException(503, f"All channels failed: {error_detail}", "ALL_CHANNELS_FAILED")

    # ===================================================================
    # OpenAI streaming
    # ===================================================================

    @staticmethod
    async def _stream_openai_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> StreamingResponse:
        """
        SSE streaming forward for the OpenAI chat completions protocol.

        Reads SSE lines from upstream, forwards each ``data: {...}`` chunk to
        the client. After the stream ends (``data: [DONE]``), extracts token
        usage from the final chunk (if present), deducts balance, and logs.
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = ProxyService._build_headers(channel, "openai", request_headers=request_headers)

        # Ensure stream flag is set
        request_data["stream"] = True
        # Request usage in streaming (OpenAI supports stream_options)
        if "stream_options" not in request_data:
            request_data["stream_options"] = {"include_usage": True}

        model_name = request_data.get("model", requested_model)

        billing_input_tokens = 0
        billing_output_tokens = 0

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        async def upstream_call(collector, collected_usage):
            """上游流式调用，同时通过 collector 收集 chunks"""
            input_tokens = 0
            output_tokens = 0

            timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, json=request_data, headers=headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(
                            f"Upstream returned HTTP {response.status_code}: "
                            f"{body.decode('utf-8', errors='replace')[:500]}"
                        )

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:]

                            if data_str.strip() == "[DONE]":
                                yield "data: [DONE]\n\n"
                                completion_event = json.dumps({
                                    "type": "response.completed",
                                    "usage": {
                                        "input_tokens": input_tokens,
                                        "output_tokens": output_tokens,
                                        "total_tokens": input_tokens + output_tokens,
                                    },
                                })
                                yield f"data: {completion_event}\n\n"
                                break

                            try:
                                chunk = json.loads(data_str)
                                usage = chunk.get("usage")
                                if usage:
                                    input_tokens = usage.get("prompt_tokens", 0)
                                    output_tokens = usage.get("completion_tokens", 0)
                                    collected_usage["prompt_tokens"] = input_tokens
                                    collected_usage["completion_tokens"] = output_tokens

                                # 收集文本内容（包括 reasoning_content 和 content）
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    reasoning_content = delta.get("reasoning_content", "")
                                    finish_reason = choices[0].get("finish_reason")
                                    if content or reasoning_content or finish_reason:
                                        # 优先收集 reasoning_content，然后是 content
                                        if reasoning_content:
                                            collector.add_chunk(reasoning_content)
                                        if content:
                                            collector.add_chunk(content)
                                        if finish_reason:
                                            collector.add_chunk("", finish_reason)
                            except (json.JSONDecodeError, TypeError):
                                pass

                            yield f"data: {data_str}\n\n"
                        else:
                            yield f"{line}\n"

            # 更新计费 tokens
            billing_input_tokens_local = input_tokens
            billing_output_tokens_local = output_tokens
            billing_callback(billing_input_tokens_local, billing_output_tokens_local, False)

        async def event_generator():
            stream_error = None

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="openai",
                    model=model_name,
                    billing_callback=billing_callback,
                ):
                    # 检测是否是缓存命中（wrap 内部会设置 cache_status）
                    yield sse_line

            except Exception as e:
                stream_error = e
                mapped_request_error = ProxyService._map_upstream_request_error(e)
                error_message = mapped_request_error.detail if mapped_request_error else f"Stream error: {str(e)}"
                logger.error("OpenAI stream error on channel %s: %s", channel.name, e)
                error_payload = json.dumps({
                    "error": {
                        "message": error_message,
                        "type": "proxy_error",
                        "code": "stream_error",
                    }
                })
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                        )
                except Exception as accounting_err:
                    logger.error("Post-stream accounting error: %s", accounting_err)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    # ===================================================================
    # OpenAI non-streaming
    # ===================================================================

    @staticmethod
    async def _non_stream_openai_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
    ) -> JSONResponse:
        """
        Non-streaming forward for the OpenAI chat completions protocol.

        Sends the request, extracts token usage, deducts balance, logs,
        and returns the full response.
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = ProxyService._build_headers(channel, "openai", request_headers=request_headers)

        request_data["stream"] = False

        # Define upstream call function for passthrough middleware
        async def upstream_call():
            timeout = httpx.Timeout(
                _UPSTREAM_TIMEOUT,
                connect=_UPSTREAM_CONNECT_TIMEOUT,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=request_data, headers=headers)

            if resp.status_code != 200:
                raise Exception(
                    f"Upstream returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            # Some upstreams always return SSE even with stream=false.
            # Detect and parse SSE to reconstruct a non-streaming response.
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type or resp.text.lstrip().startswith("data: "):
                response_body, input_tokens, output_tokens = (
                    ProxyService._parse_sse_to_non_stream_openai(resp.text)
                )
            else:
                response_body = resp.json()
                usage = response_body.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

            # Return standardized response format for the shared middleware contract
            return {
                "response": response_body,
                "model": request_data.get("model"),
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                }
            }

        # Shared passthrough middleware contract
        cache_response, cache_info = await CacheMiddleware.wrap_request(
            request_body=request_data,
            headers=request_headers or {},
            user=user,
            db=db,
            upstream_call=upstream_call,
            unified_model=unified_model,
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        # Extract response body and tokens
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)

        # Middleware is passthrough; billing tokens equal actual tokens
        billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
            cache_info=cache_info,
            user=user,
            actual_tokens={
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
            }
        )

        # Record success and do accounting with billing tokens
        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        response_headers = {"X-Request-ID": request_id}

        return JSONResponse(
            content=response_body,
            headers=response_headers,
        )

    # ===================================================================
    # Anthropic streaming
    # ===================================================================

    @staticmethod
    async def _stream_anthropic_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
        force_compat: bool = False,
    ) -> StreamingResponse:
        """
        SSE streaming forward for the Anthropic messages protocol.

        Anthropic SSE events look like:
            event: message_start
            data: {"type":"message_start","message":{...}}

            event: content_block_delta
            data: {"type":"content_block_delta","delta":{"text":"..."}}

            event: message_delta
            data: {"type":"message_delta","delta":{},"usage":{"output_tokens":N}}

            event: message_stop
            data: {"type":"message_stop"}

        Usage info comes from ``message_start`` (input_tokens) and
        ``message_delta`` (output_tokens).
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/messages"
        model_name = request_data.get("model", requested_model)
        headers = ProxyService._build_headers(
            channel,
            "anthropic",
            request_headers=request_headers,
            model_name=model_name,
            force_compat=force_compat,
        )

        request_data["stream"] = True

        billing_input_tokens = 0
        billing_output_tokens = 0

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        async def upstream_call(collector, collected_usage):
            """上游流式调用，同时通过 collector 收集 chunks"""
            input_tokens = 0
            output_tokens = 0

            timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, json=request_data, headers=headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(
                            f"Upstream returned HTTP {response.status_code}: "
                            f"{body.decode('utf-8', errors='replace')[:500]}"
                        )

                    current_event = ""
                    async for line in response.aiter_lines():
                        if not line:
                            yield "\n"
                            continue

                        if line.startswith("event: "):
                            current_event = line[7:].strip()
                            yield f"{line}\n"
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:]

                            try:
                                chunk = json.loads(data_str)
                                chunk_type = chunk.get("type", "")

                                if chunk_type == "message_start":
                                    msg = chunk.get("message", {})
                                    usage = msg.get("usage", {})
                                    input_tokens = usage.get("input_tokens", 0)

                                elif chunk_type == "message_delta":
                                    usage = chunk.get("usage", {})
                                    output_tokens = usage.get("output_tokens", output_tokens)
                                    if "input_tokens" in usage and usage["input_tokens"]:
                                        input_tokens = usage["input_tokens"]
                                    collected_usage["prompt_tokens"] = input_tokens
                                    collected_usage["completion_tokens"] = output_tokens

                                elif chunk_type == "content_block_delta":
                                    # 收集文本内容（包括 thinking 和 text）
                                    delta = chunk.get("delta", {})
                                    text = delta.get("text", "")
                                    thinking = delta.get("thinking", "")
                                    if text:
                                        collector.add_chunk(text)
                                    if thinking:
                                        collector.add_chunk(thinking)

                                elif chunk_type == "message_stop":
                                    # 记录结束
                                    collector.add_chunk("", "end_turn")

                            except (json.JSONDecodeError, TypeError):
                                pass

                            yield f"data: {data_str}\n\n"

                            if current_event == "message_stop":
                                break
                        else:
                            yield f"{line}\n"

            billing_callback(input_tokens, output_tokens, False)

        async def event_generator():
            stream_error = None

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="anthropic",
                    model=model_name,
                    billing_callback=billing_callback,
                ):
                    yield sse_line

            except Exception as e:
                stream_error = e
                mapped_request_error = ProxyService._map_upstream_request_error(e)
                error_message = mapped_request_error.detail if mapped_request_error else f"Stream error: {str(e)}"
                logger.error("Anthropic stream error on channel %s: %s", channel.name, e)
                error_payload = json.dumps({
                    "type": "error",
                    "error": {
                        "type": "proxy_error",
                        "message": error_message,
                    },
                })
                yield f"event: error\ndata: {error_payload}\n\n"
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                        )
                except Exception as accounting_err:
                    logger.error("Post-stream accounting error: %s", accounting_err)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    # ===================================================================
    # Anthropic non-streaming
    # ===================================================================

    @staticmethod
    async def _non_stream_anthropic_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        channel: Channel,
        unified_model: UnifiedModel,
        request_data: dict,
        request_id: str,
        requested_model: str,
        client_ip: str,
        request_headers: Optional[dict[str, str]] = None,
        force_compat: bool = False,
    ) -> JSONResponse:
        """
        Non-streaming forward for the Anthropic messages protocol.

        Anthropic response contains ``usage.input_tokens`` and
        ``usage.output_tokens`` at the top level.
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/messages"
        headers = ProxyService._build_headers(
            channel,
            "anthropic",
            request_headers=request_headers,
            model_name=request_data.get("model", requested_model),
            force_compat=force_compat,
        )

        request_data["stream"] = False

        # Define upstream call function for passthrough middleware
        async def upstream_call():
            timeout = httpx.Timeout(
                _UPSTREAM_TIMEOUT,
                connect=_UPSTREAM_CONNECT_TIMEOUT,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=request_data, headers=headers)

            if resp.status_code != 200:
                raise Exception(
                    f"Upstream returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            # Some upstreams always return SSE even with stream=false.
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type or resp.text.lstrip().startswith("event: "):
                response_body, input_tokens, output_tokens = (
                    ProxyService._parse_sse_to_non_stream_anthropic(resp.text)
                )
            else:
                response_body = resp.json()
                usage = response_body.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

            # Return standardized response format for the shared middleware contract
            return {
                "response": response_body,
                "model": request_data.get("model"),
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                }
            }

        # Shared passthrough middleware contract
        cache_response, cache_info = await CacheMiddleware.wrap_request(
            request_body=request_data,
            headers=request_headers or {},
            user=user,
            db=db,
            upstream_call=upstream_call,
            unified_model=unified_model,
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        # Extract response body and tokens
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)

        # Middleware is passthrough; billing tokens equal actual tokens
        billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
            cache_info=cache_info,
            user=user,
            actual_tokens={
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
            }
        )

        # Record success and do accounting with billing tokens
        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        response_headers = {"X-Request-ID": request_id}

        return JSONResponse(
            content=response_body,
            headers=response_headers,
        )

    # ===================================================================
    # Helper: parse SSE response into non-streaming format
    # ===================================================================

    @staticmethod
    def _parse_sse_to_non_stream_openai(raw_text: str) -> tuple[dict, int, int]:
        """
        Parse an SSE text body (from an upstream that always streams) into
        a non-streaming OpenAI chat completion response.

        Collects all content deltas, extracts usage from the final chunk,
        and reconstructs a standard ``chat.completion`` response dict.

        Returns:
            Tuple of (response_body_dict, input_tokens, output_tokens).
        """
        input_tokens = 0
        output_tokens = 0
        collected_content = []
        last_id = None
        last_model = None
        finish_reason = None

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                last_id = chunk.get("id", last_id)
                last_model = chunk.get("model", last_model)

                # Extract content from choices
                choices = chunk.get("choices", [])
                for choice in choices:
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if content:
                        collected_content.append(content)
                    fr = choice.get("finish_reason")
                    if fr:
                        finish_reason = fr

                # Extract usage
                usage = chunk.get("usage")
                if usage:
                    input_tokens = usage.get("prompt_tokens", input_tokens)
                    output_tokens = usage.get("completion_tokens", output_tokens)
            except (json.JSONDecodeError, TypeError):
                pass

        full_content = "".join(collected_content)

        response_body = {
            "id": last_id or "chatcmpl-unknown",
            "object": "chat.completion",
            "model": last_model or "unknown",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_content,
                    },
                    "finish_reason": finish_reason or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

        return response_body, input_tokens, output_tokens

    @staticmethod
    def _parse_sse_to_non_stream_anthropic(raw_text: str) -> tuple[dict, int, int]:
        """
        Parse an SSE text body from an Anthropic-protocol upstream that always
        streams into a non-streaming Anthropic message response.

        Collects all content deltas, extracts usage from message_start and
        message_delta events, and reconstructs a standard Anthropic response.

        Returns:
            Tuple of (response_body_dict, input_tokens, output_tokens).
        """
        input_tokens = 0
        output_tokens = 0
        collected_content = []
        msg_id = None
        msg_model = None
        stop_reason = None

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                chunk = json.loads(data_str)
                chunk_type = chunk.get("type", "")

                if chunk_type == "message_start":
                    msg = chunk.get("message", {})
                    msg_id = msg.get("id")
                    msg_model = msg.get("model")
                    usage = msg.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)

                elif chunk_type == "content_block_delta":
                    delta = chunk.get("delta", {})
                    text = delta.get("text")
                    if text:
                        collected_content.append(text)

                elif chunk_type == "message_delta":
                    delta = chunk.get("delta", {})
                    stop_reason = delta.get("stop_reason", stop_reason)
                    usage = chunk.get("usage", {})
                    output_tokens = usage.get("output_tokens", output_tokens)
                    if "input_tokens" in usage and usage["input_tokens"]:
                        input_tokens = usage["input_tokens"]

                elif chunk_type == "message_stop":
                    break

            except (json.JSONDecodeError, TypeError):
                pass

        full_content = "".join(collected_content)

        response_body = {
            "id": msg_id or "msg-unknown",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": full_content}],
            "model": msg_model or "unknown",
            "stop_reason": stop_reason or "end_turn",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }

        return response_body, input_tokens, output_tokens

    # ===================================================================
    # Helper: build upstream headers
    # ===================================================================

    @staticmethod
    def _extract_forward_headers(
        request_headers: Optional[dict[str, str]],
        protocol_type: str,
    ) -> dict[str, str]:
        """Allowlist a few safe client headers that some upstreams require."""
        if not request_headers:
            return {}

        source = {
            str(key).lower(): value
            for key, value in request_headers.items()
            if isinstance(value, str) and value.strip()
        }
        headers: dict[str, str] = {}

        user_agent = source.get("user-agent")
        if user_agent:
            headers["User-Agent"] = user_agent

        if protocol_type == "anthropic":
            anthropic_version = source.get("anthropic-version")
            anthropic_beta = source.get("anthropic-beta")
            if anthropic_version:
                headers["anthropic-version"] = anthropic_version
            if anthropic_beta:
                headers["anthropic-beta"] = anthropic_beta
        else:
            openai_org = source.get("openai-organization")
            openai_project = source.get("openai-project")
            openai_beta = source.get("openai-beta")
            if openai_org:
                headers["OpenAI-Organization"] = openai_org
            if openai_project:
                headers["OpenAI-Project"] = openai_project
            if openai_beta:
                headers["OpenAI-Beta"] = openai_beta

        return headers

    @staticmethod
    def _build_headers(
        channel: Channel,
        protocol_type: str,
        request_headers: Optional[dict[str, str]] = None,
        model_name: Optional[str] = None,
        force_compat: bool = False,
    ) -> dict[str, str]:
        """Build upstream request headers based on protocol type and channel auth config."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": _UPSTREAM_DEFAULT_USER_AGENT,
        }
        headers.update(ProxyService._extract_forward_headers(request_headers, protocol_type))

        # Determine auth header type (default to protocol-specific behavior for backward compatibility)
        auth_header_type = getattr(channel, "auth_header_type", None)
        if not auth_header_type:
            # Backward compatibility: use protocol-specific default
            auth_header_type = "authorization" if protocol_type == "openai" else "x-api-key"

        if protocol_type == "anthropic":
            headers.setdefault("anthropic-version", "2023-06-01")

        # Set authentication header based on channel configuration
        if auth_header_type == "authorization":
            headers["Authorization"] = f"Bearer {channel.api_key}"
        elif protocol_type == "openai" and auth_header_type == "x-api-key":
            # Existing records may still hold the migration default ``x-api-key``.
            # Emit both formats so OpenAI-compatible upstreams continue to work.
            headers["x-api-key"] = channel.api_key
            headers["Authorization"] = f"Bearer {channel.api_key}"
        elif protocol_type == "anthropic" and auth_header_type in {"x-api-key", "anthropic-api-key"}:
            # OpenClaw verification and Anthropic-compatible gateways are split
            # between these two header names. Mirror both for compatibility.
            headers["x-api-key"] = channel.api_key
            headers["anthropic-api-key"] = channel.api_key
        elif auth_header_type == "anthropic-api-key":
            headers["anthropic-api-key"] = channel.api_key
        else:  # x-api-key (default)
            headers["x-api-key"] = channel.api_key

        return headers

    # ===================================================================
    # Helper: channel health tracking
    # ===================================================================

    @staticmethod
    def _record_channel_failure(db: Session, channel: Channel) -> None:
        """
        Record a failure on a channel.

        Increments ``failure_count``, sets ``last_failure_at``, and triggers
        the circuit breaker if the threshold is reached.
        """
        try:
            channel.failure_count += 1
            channel.last_failure_at = datetime.utcnow()

            # Check circuit breaker threshold
            threshold = get_system_config(db, "circuit_breaker_threshold", 5)
            if channel.failure_count >= threshold:
                recovery = get_system_config(db, "circuit_breaker_recovery", 600)
                channel.circuit_breaker_until = datetime.utcnow() + timedelta(seconds=recovery)
                channel.is_healthy = 0

            # Decrease health score
            channel.health_score = max(0, channel.health_score - 10)

            db.commit()
        except Exception as e:
            logger.error("Failed to record channel failure: %s", e)
            db.rollback()

    @staticmethod
    def _record_success(db: Session, channel: Channel) -> None:
        """
        Record a successful request on a channel.

        Resets ``failure_count`` and ``circuit_breaker_until``, marks healthy.
        """
        try:
            channel.failure_count = 0
            channel.last_success_at = datetime.utcnow()
            channel.is_healthy = 1
            channel.circuit_breaker_until = None

            # Increase health score
            channel.health_score = min(100, channel.health_score + 5)

            db.commit()
        except Exception as e:
            logger.error("Failed to record channel success: %s", e)
            db.rollback()

    # ===================================================================
    # Helper: balance deduction and logging
    # ===================================================================

    @staticmethod
    def _deduct_balance_and_log(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        unified_model: UnifiedModel,
        request_id: str,
        requested_model: str,
        input_tokens: int,
        output_tokens: int,
        channel: Channel,
        client_ip: str,
        response_time_ms: int,
        is_stream: bool,
    ) -> None:
        """
        Calculate cost, deduct from user balance (for balance mode) or just record usage (for unlimited mode),
        write request log and consumption record, and update API key usage stats.
        """
        try:
            usage_now = datetime.utcnow()

            # Apply token multiplier
            token_multiplier = get_system_config(db, "token_multiplier", 1.0)
            input_tokens = int(input_tokens * token_multiplier)
            output_tokens = int(output_tokens * token_multiplier)
            total_tokens = input_tokens + output_tokens

            # Calculate cost with price multiplier
            price_multiplier = get_system_config(db, "price_multiplier", 1.0)
            input_cost = (input_tokens / 1_000_000) * float(unified_model.input_price_per_million) * price_multiplier
            output_cost = (output_tokens / 1_000_000) * float(unified_model.output_price_per_million) * price_multiplier
            total_cost = input_cost + output_cost

            # Handle balance deduction based on subscription type
            billing_mode = "balance"
            subscription_id: int | None = None
            if user.subscription_type == "balance":
                # Balance mode: deduct from user balance (with row lock)
                balance = (
                    db.query(UserBalance)
                    .filter(UserBalance.user_id == user.id)
                    .with_for_update()
                    .first()
                )
                if balance:
                    balance_before = float(balance.balance)
                    balance.balance -= Decimal(str(total_cost))
                    balance.total_consumed += Decimal(str(total_cost))
                    balance_after = float(balance.balance)
                else:
                    balance_before = 0.0
                    balance_after = 0.0
            else:
                # Unlimited mode: no balance deduction, just record usage.
                billing_mode = "subscription"
                active_subscription = (
                    db.query(UserSubscription)
                    .filter(
                        UserSubscription.user_id == user.id,
                        UserSubscription.status == "active",
                        UserSubscription.start_time <= usage_now,
                        UserSubscription.end_time >= usage_now,
                    )
                    .order_by(UserSubscription.id.desc())
                    .first()
                )
                subscription_id = active_subscription.id if active_subscription else None

                balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
                if balance:
                    balance_before = float(balance.balance)
                    balance_after = float(balance.balance)
                else:
                    balance_before = 0.0
                    balance_after = 0.0

            # Write consumption record (for both modes)
            consumption = ConsumptionRecord(
                user_id=user.id,
                request_id=request_id,
                model_name=requested_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                input_cost=Decimal(str(input_cost)),
                output_cost=Decimal(str(output_cost)),
                total_cost=Decimal(str(total_cost)),
                balance_before=Decimal(str(balance_before)),
                balance_after=Decimal(str(balance_after)),
                billing_mode=billing_mode,
                subscription_id=subscription_id,
            )
            db.add(consumption)

            # Write request log
            req_log = RequestLog(
                request_id=request_id,
                user_id=user.id,
                user_api_key_id=api_key_record.id,
                channel_id=channel.id,
                channel_name=channel.name,
                requested_model=requested_model,
                actual_model=unified_model.model_name,
                protocol_type=channel.protocol_type,
                is_stream=1 if is_stream else 0,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                response_time_ms=response_time_ms,
                status="success",
                error_message=None,
                client_ip=client_ip,
            )
            db.add(req_log)

            # Update API key stats
            api_key_record.total_requests += 1
            api_key_record.total_tokens += total_tokens
            api_key_record.total_cost += Decimal(str(total_cost))
            api_key_record.last_used_at = datetime.utcnow()

            db.commit()

        except Exception as e:
            logger.error("Balance deduction / logging failed: %s", e)
            db.rollback()

    @staticmethod
    def _log_failed_request(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        request_id: str,
        requested_model: str,
        client_ip: str,
        is_stream: bool,
        error_message: str,
        channel: Channel | None = None,
        response_time_ms: Optional[int] = None,
    ) -> None:
        """Log a failed request without deducting balance."""
        try:
            req_log = RequestLog(
                request_id=request_id,
                user_id=user.id,
                user_api_key_id=api_key_record.id,
                channel_id=channel.id if channel else None,
                channel_name=channel.name if channel else None,
                requested_model=requested_model,
                actual_model=None,
                protocol_type=channel.protocol_type if channel else None,
                is_stream=1 if is_stream else 0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                response_time_ms=response_time_ms,
                status="error",
                error_message=error_message[:2000] if error_message else None,
                client_ip=client_ip,
            )
            db.add(req_log)
            db.commit()
        except Exception as e:
            logger.error("Failed to log error request: %s", e)
            db.rollback()

    # ===================================================================
    # Helper: validate request content length
    # ===================================================================

    @staticmethod
    def _validate_request_length(db: Session, request_data: dict) -> None:
        """
        Validate request content length to prevent upstream quota exhaustion.

        Checks:
        1. Total message content length (characters)
        2. Estimated token count based on character length

        Raises:
            ServiceException: if content exceeds configured limits
        """
        try:
            # Get configuration limits
            max_message_length = get_system_config(db, "max_message_length", 500000)
            max_context_tokens = get_system_config(db, "max_context_tokens", 200000)

            # Extract messages from request
            messages = request_data.get("messages", [])
            if not messages:
                return

            # Calculate total content length
            total_length = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total_length += len(content)
                elif isinstance(content, list):
                    # Handle multi-part content (text + images)
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            total_length += len(part.get("text", ""))

            # Check character length limit
            if total_length > max_message_length:
                raise ServiceException(
                    400,
                    f"请求内容过长，当前 {total_length:,} 字符，超过限制 {max_message_length:,} 字符。"
                    f"请减少上下文长度或分批处理。",
                    "CONTENT_TOO_LONG"
                )

            # Estimate token count (rough estimate: 1 token ≈ 4 characters for English, 1.5 for Chinese)
            # Use conservative estimate of 2.5 characters per token
            estimated_tokens = int(total_length / 2.5)

            if estimated_tokens > max_context_tokens:
                raise ServiceException(
                    400,
                    f"预估 Token 数量过多（约 {estimated_tokens:,} tokens），超过限制 {max_context_tokens:,} tokens。"
                    f"请减少上下文长度或分批处理。",
                    "TOKENS_TOO_MANY"
                )

        except ServiceException:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.warning("Failed to validate request length: %s", e)
            # Don't block request if validation fails
