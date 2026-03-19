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

logger = logging.getLogger(__name__)

# Default timeout for upstream requests (seconds)
_UPSTREAM_TIMEOUT = 120.0
# Timeout for upstream connection establishment
_UPSTREAM_CONNECT_TIMEOUT = 15.0


class ResponsesTurnError(Exception):
    """Internal error used to decide whether a websocket turn can retry."""

    def __init__(self, message: str, can_retry: bool):
        self.can_retry = can_retry
        super().__init__(message)


class ProxyService:
    """Stateless proxy that forwards LLM requests through managed channels."""

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
                    )
                return await ProxyService._non_stream_responses_request(
                    db, user, api_key_record, channel, unified_model,
                    channel_request, request_id, requested_model, client_ip,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Responses channel %s (%d) failed for model %s: %s",
                    channel.name, channel.id, actual_model_name, exc,
                )
                ProxyService._record_channel_failure(db, channel)
                continue

        error_detail = str(last_error) if last_error else "Unknown error"
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
        raise ServiceException(503, f"All channels failed: {error_detail}", "ALL_CHANNELS_FAILED")

    @staticmethod
    async def handle_responses_websocket(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        websocket: WebSocket,
        client_ip: str,
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
    ) -> StreamingResponse:
        """Forward a streaming Responses request to upstream ``/responses``."""
        start_time = time.time()
        async def event_generator():
            input_tokens = 0
            output_tokens = 0
            completed = False
            saw_error = False
            error_message = ""
            stream_error: Exception | None = None

            try:
                async for payload in ProxyService._iter_responses_upstream_payloads(
                    channel,
                    request_data,
                    requested_model,
                ):
                    payload_type = str(payload.get("type", "") or "")
                    if payload_type == "response.completed":
                        completed = True
                        input_tokens, output_tokens = ProxyService._extract_responses_usage(payload)
                    elif payload_type == "error":
                        saw_error = True
                        error_message = (
                            payload.get("error", {}).get("message")
                            or "Upstream responses error"
                        )
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
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True, str(stream_error), channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, input_tokens, output_tokens, channel,
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
    ):
        """Yield parsed Responses payload dicts from upstream SSE or JSON."""
        start_url = channel.base_url.rstrip("/")
        url = f"{start_url}/responses"
        headers = ProxyService._build_headers(channel, "openai")
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
    ) -> JSONResponse:
        """Forward a non-streaming Responses request to upstream ``/responses``."""
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/responses"
        headers = ProxyService._build_headers(channel, "openai")

        timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request_data, headers=headers)

        response_time_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            raise Exception(f"Upstream returned HTTP {response.status_code}: {response.text[:500]}")

        response_body, input_tokens, output_tokens = ProxyService._parse_non_stream_responses_body(
            response.text
        )
        response_body = ProxyService._rewrite_response_model(response_body, requested_model)

        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, input_tokens, output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        return JSONResponse(
            content=response_body,
            headers={"X-Request-ID": request_id},
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
        for channel, actual_model_name in channels:
            try:
                # Build upstream request with the actual model name
                request_data_copy = dict(request_data)
                request_data_copy["model"] = actual_model_name

                if is_stream:
                    return await ProxyService._stream_openai_request(
                        db, user, api_key_record, channel, unified_model,
                        request_data_copy, request_id, requested_model, client_ip,
                    )
                else:
                    return await ProxyService._non_stream_openai_request(
                        db, user, api_key_record, channel, unified_model,
                        request_data_copy, request_id, requested_model, client_ip,
                    )
            except ServiceException:
                raise  # Re-raise business exceptions immediately
            except Exception as e:
                last_error = e
                logger.warning(
                    "Channel %s (%d) failed for model %s: %s",
                    channel.name, channel.id, actual_model_name, e,
                )
                ProxyService._record_channel_failure(db, channel)
                continue

        # All channels exhausted
        error_detail = str(last_error) if last_error else "Unknown error"
        # Log the failure
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
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
        for channel, actual_model_name in channels:
            try:
                request_data_copy = dict(request_data)
                request_data_copy["model"] = actual_model_name

                if is_stream:
                    return await ProxyService._stream_anthropic_request(
                        db, user, api_key_record, channel, unified_model,
                        request_data_copy, request_id, requested_model, client_ip,
                    )
                else:
                    return await ProxyService._non_stream_anthropic_request(
                        db, user, api_key_record, channel, unified_model,
                        request_data_copy, request_id, requested_model, client_ip,
                    )
            except ServiceException:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Channel %s (%d) failed for model %s: %s",
                    channel.name, channel.id, actual_model_name, e,
                )
                ProxyService._record_channel_failure(db, channel)
                continue

        error_detail = str(last_error) if last_error else "Unknown error"
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model,
            client_ip, is_stream, error_detail,
        )
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
        headers = ProxyService._build_headers(channel, "openai")

        # Ensure stream flag is set
        request_data["stream"] = True
        # Request usage in streaming (OpenAI supports stream_options)
        if "stream_options" not in request_data:
            request_data["stream_options"] = {"include_usage": True}

        async def event_generator():
            input_tokens = 0
            output_tokens = 0
            stream_error = None

            try:
                timeout = httpx.Timeout(
                    _UPSTREAM_TIMEOUT,
                    connect=_UPSTREAM_CONNECT_TIMEOUT,
                )
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
                                # Empty line is the SSE record separator - skip it
                                # The upstream already sends proper SSE format with \n\n
                                continue

                            if line.startswith("data: "):
                                data_str = line[6:]

                                if data_str.strip() == "[DONE]":
                                    # Send standard [DONE] for OpenAI clients
                                    yield "data: [DONE]\n\n"
                                    # Send response.completed event for Codex CLI compatibility
                                    completion_event = json.dumps({
                                        "type": "response.completed",
                                        "usage": {
                                            "input_tokens": input_tokens,
                                            "output_tokens": output_tokens,
                                            "total_tokens": input_tokens + output_tokens
                                        }
                                    })
                                    yield f"data: {completion_event}\n\n"
                                    break

                                # Try to extract usage from this chunk
                                try:
                                    chunk = json.loads(data_str)
                                    usage = chunk.get("usage")
                                    if usage:
                                        input_tokens = usage.get("prompt_tokens", 0)
                                        output_tokens = usage.get("completion_tokens", 0)
                                except (json.JSONDecodeError, TypeError):
                                    pass

                                yield f"data: {data_str}\n\n"
                            else:
                                # Forward any other SSE fields (e.g., event:, id:)
                                yield f"{line}\n"

            except Exception as e:
                stream_error = e
                logger.error("OpenAI stream error on channel %s: %s", channel.name, e)
                # Send an error event to the client
                error_payload = json.dumps({
                    "error": {
                        "message": f"Stream error: {str(e)}",
                        "type": "proxy_error",
                        "code": "stream_error",
                    }
                })
                yield f"data: {error_payload}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                # Post-stream accounting
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True, str(stream_error), channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, input_tokens, output_tokens, channel,
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
    ) -> JSONResponse:
        """
        Non-streaming forward for the OpenAI chat completions protocol.

        Sends the request, extracts token usage, deducts balance, logs,
        and returns the full response.
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = ProxyService._build_headers(channel, "openai")

        request_data["stream"] = False

        timeout = httpx.Timeout(
            _UPSTREAM_TIMEOUT,
            connect=_UPSTREAM_CONNECT_TIMEOUT,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=request_data, headers=headers)

        response_time_ms = int((time.time() - start_time) * 1000)

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

        # Record success and do accounting
        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, input_tokens, output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        return JSONResponse(
            content=response_body,
            headers={"X-Request-ID": request_id},
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
        headers = ProxyService._build_headers(channel, "anthropic")

        request_data["stream"] = True

        async def event_generator():
            input_tokens = 0
            output_tokens = 0
            stream_error = None

            try:
                timeout = httpx.Timeout(
                    _UPSTREAM_TIMEOUT,
                    connect=_UPSTREAM_CONNECT_TIMEOUT,
                )
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

                                # Parse to extract usage info
                                try:
                                    chunk = json.loads(data_str)
                                    chunk_type = chunk.get("type", "")

                                    if chunk_type == "message_start":
                                        # Input tokens from message.usage
                                        msg = chunk.get("message", {})
                                        usage = msg.get("usage", {})
                                        input_tokens = usage.get("input_tokens", 0)

                                    elif chunk_type == "message_delta":
                                        # Output tokens from usage; some proxies
                                        # also put final input_tokens here.
                                        usage = chunk.get("usage", {})
                                        output_tokens = usage.get("output_tokens", output_tokens)
                                        if "input_tokens" in usage and usage["input_tokens"]:
                                            input_tokens = usage["input_tokens"]

                                except (json.JSONDecodeError, TypeError):
                                    pass

                                yield f"data: {data_str}\n\n"

                                # Check for message_stop to end
                                if current_event == "message_stop":
                                    break
                            else:
                                yield f"{line}\n"

            except Exception as e:
                stream_error = e
                logger.error("Anthropic stream error on channel %s: %s", channel.name, e)
                error_payload = json.dumps({
                    "type": "error",
                    "error": {
                        "type": "proxy_error",
                        "message": f"Stream error: {str(e)}",
                    },
                })
                yield f"event: error\ndata: {error_payload}\n\n"
            finally:
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    if stream_error:
                        ProxyService._record_channel_failure(db, channel)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True, str(stream_error), channel=channel,
                            response_time_ms=response_time_ms,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, input_tokens, output_tokens, channel,
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
    ) -> JSONResponse:
        """
        Non-streaming forward for the Anthropic messages protocol.

        Anthropic response contains ``usage.input_tokens`` and
        ``usage.output_tokens`` at the top level.
        """
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/messages"
        headers = ProxyService._build_headers(channel, "anthropic")

        request_data["stream"] = False

        timeout = httpx.Timeout(
            _UPSTREAM_TIMEOUT,
            connect=_UPSTREAM_CONNECT_TIMEOUT,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=request_data, headers=headers)

        response_time_ms = int((time.time() - start_time) * 1000)

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

        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, input_tokens, output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
        )

        return JSONResponse(
            content=response_body,
            headers={"X-Request-ID": request_id},
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
    def _build_headers(channel: Channel, protocol_type: str) -> dict[str, str]:
        """Build upstream request headers based on protocol type."""
        if protocol_type == "openai":
            return {
                "Authorization": f"Bearer {channel.api_key}",
                "Content-Type": "application/json",
            }
        else:  # anthropic
            return {
                "x-api-key": channel.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }

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
