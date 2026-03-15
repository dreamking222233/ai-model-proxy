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

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
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
)
from app.services.model_service import ModelService
from app.services.health_service import get_system_config
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)

# Default timeout for upstream requests (seconds)
_UPSTREAM_TIMEOUT = 120.0
# Timeout for upstream connection establishment
_UPSTREAM_CONNECT_TIMEOUT = 15.0


class ProxyService:
    """Stateless proxy that forwards LLM requests through managed channels."""

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
            2. Resolve model (apply override rules).
            3. Get available channels sorted by priority.
            4. Attempt each channel in order (failover).

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

        # 1. Check user balance
        balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
        if not balance or balance.balance <= 0:
            raise ServiceException(402, "余额不足，请充值", "INSUFFICIENT_BALANCE")

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

        # 1. Check user balance
        balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
        if not balance or balance.balance <= 0:
            raise ServiceException(402, "余额不足，请充值", "INSUFFICIENT_BALANCE")

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
                                # Empty line is the SSE record separator
                                yield "\n"
                                continue

                            if line.startswith("data: "):
                                data_str = line[6:]

                                if data_str.strip() == "[DONE]":
                                    yield "data: [DONE]\n\n"
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
        Calculate cost, deduct from user balance, write request log and
        consumption record, and update API key usage stats.
        """
        try:
            total_tokens = input_tokens + output_tokens

            # Calculate cost
            input_cost = (input_tokens / 1_000_000) * float(unified_model.input_price_per_million)
            output_cost = (output_tokens / 1_000_000) * float(unified_model.output_price_per_million)
            total_cost = input_cost + output_cost

            # Deduct balance (with row lock)
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

            # Write consumption record
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
        response_time_ms: int | None = None,
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
