"""Channel-scoped native passthrough for text model APIs.

The payload is never rebuilt on the passthrough path. A side observer reads
usage from a copy of upstream JSON/SSE events so the existing accounting code
can still be used.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional, Union
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.database import release_session_connection
from app.models.channel import Channel
from app.models.model import UnifiedModel
from app.models.user import SysUser, UserApiKey
from app.services.anthropic_prompt_cache_service import AnthropicPromptCacheService
from app.services.billing_concurrency_service import BillingConcurrencyService
from app.services.model_service import ModelService

logger = logging.getLogger(__name__)

_TEXT_PROTOCOLS = {"openai", "anthropic", "responses"}
_HOP_HEADERS = {
    b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
    b"te", b"trailer", b"transfer-encoding", b"upgrade",
}
_SITE_HEADERS = {
    b"authorization", b"x-api-key", b"anthropic-api-key", b"host", b"content-length",
    b"cookie", b"x-site-host", b"origin", b"referer", b"x-forwarded-for",
    b"x-forwarded-host", b"x-forwarded-proto", b"forwarded",
}
_RESPONSE_DROP_HEADERS = _HOP_HEADERS | {b"content-length", b"content-encoding"}
_EVENT_BUFFER_LIMIT = 1024 * 1024
_LOCAL_TERMINAL_ERRORS = {
    "BALANCE_INSUFFICIENT",
    "SUBSCRIPTION_EXPIRED",
    "SUBSCRIPTION_DAILY_QUOTA_EXCEEDED",
    "BILLING_CONCURRENCY_LIMITED",
    "BILLING_CONCURRENCY_UNAVAILABLE",
    "TEXT_BILLING_FAILED",
}


class PassthroughUpstreamError(Exception):
    def __init__(self, status_code: int, body: bytes, headers: list[tuple[bytes, bytes]]):
        self.status_code = int(status_code)
        self.body = body
        self.headers = headers
        super().__init__(f"Passthrough upstream returned HTTP {status_code}")


@dataclass(frozen=True)
class PassthroughCandidate:
    channel: Channel
    unified_model: Optional[UnifiedModel]
    mode: str
    protocol_rank: int = 0


class UsageObserver:
    """Observe usage without changing response bytes or event ordering."""

    def __init__(self, protocol: str, channel: Channel):
        self.protocol = protocol
        self.channel = channel
        self.buffer = bytearray()
        self.usage_seen = False
        self.completed = False
        self.failed = False
        self.summary: dict[str, Any] = {}

    def feed_json(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        event_type = str(payload.get("type") or "")
        if self.protocol == "anthropic":
            usage = payload.get("usage")
            if not isinstance(usage, dict) and isinstance(payload.get("message"), dict):
                usage = payload["message"].get("usage")
            if isinstance(usage, dict):
                self._merge(AnthropicPromptCacheService.extract_usage_summary(usage))
            if event_type in {"message_stop"} or payload.get("stop_reason"):
                self.completed = True
            if event_type == "error" or "error" in payload:
                self.failed = True
            return

        if self.protocol == "responses":
            response = payload.get("response") if isinstance(payload.get("response"), dict) else payload
            usage = response.get("usage") if isinstance(response, dict) else None
            if isinstance(usage, dict):
                from app.services.proxy_service import ProxyService
                self._merge(ProxyService._extract_responses_prompt_cache_summary(usage, self.channel))
            if event_type == "response.completed" or (
                payload.get("object") == "response" and payload.get("status") == "completed"
            ):
                self.completed = True
            if event_type in {"response.failed", "response.cancelled", "response.incomplete", "error"} or (
                payload.get("object") == "response" and payload.get("status") in {"failed", "cancelled", "incomplete"}
            ):
                self.failed = True
            return

        usage = payload.get("usage")
        if isinstance(usage, dict):
            from app.services.proxy_service import ProxyService
            self._merge(ProxyService._extract_openai_prompt_cache_summary(usage, self.channel))
        choices = payload.get("choices")
        if isinstance(choices, list) and any(
            isinstance(choice, dict) and choice.get("finish_reason") is not None
            for choice in choices
        ):
            self.completed = True
        if payload.get("error") is not None:
            self.failed = True

    def feed_sse(self, chunk: bytes) -> None:
        self.buffer.extend(chunk)
        if len(self.buffer) > _EVENT_BUFFER_LIMIT:
            raise ServiceException(502, "上游流式事件过大", "UPSTREAM_EVENT_TOO_LARGE")
        normalized = bytes(self.buffer).replace(b"\r\n", b"\n")
        events = normalized.split(b"\n\n")
        self.buffer = bytearray(events.pop() if events else b"")
        for event in events:
            self._feed_sse_event(event)

    def finish_sse(self) -> None:
        """Observe a final SSE event when the upstream omits the blank terminator."""
        if not self.buffer:
            return
        event = bytes(self.buffer).replace(b"\r\n", b"\n")
        self.buffer.clear()
        self._feed_sse_event(event)

    def _feed_sse_event(self, event: bytes) -> None:
        data_lines = [line[5:].lstrip() for line in event.split(b"\n") if line.startswith(b"data:")]
        if not data_lines:
            return
        raw = b"\n".join(data_lines)
        if raw == b"[DONE]":
            self.completed = True
            return
        try:
            self.feed_json(json.loads(raw))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

    def _merge(self, summary: dict[str, Any]) -> None:
        self.usage_seen = True
        merged = dict(self.summary)
        for key, value in summary.items():
            if key.endswith("_tokens") or key in {"input_tokens", "output_tokens", "logical_input_tokens"}:
                merged[key] = max(int(merged.get(key, 0) or 0), int(value or 0))
            elif value is not None:
                merged[key] = value
        self.summary = merged


class ChannelPassthroughService:
    """Dispatch native text requests through channels that opt into passthrough."""

    @staticmethod
    def _snapshot_orm_columns(instance: Any) -> Any:
        """Keep scalar ORM values usable after the request session is released."""
        if instance is None or not hasattr(instance, "__table__"):
            return instance
        return SimpleNamespace(**{
            column.key: getattr(instance, column.key)
            for column in instance.__table__.columns
        })

    @staticmethod
    def _is_text_model(model: UnifiedModel) -> bool:
        return (
            str(getattr(model, "model_type", "") or "chat") not in {"image", "video"}
            and str(getattr(model, "billing_type", "") or "token") != "image_credit"
        )

    @staticmethod
    def _channel_supports_protocol(channel: Channel, protocol: str, actual_model: str) -> bool:
        channel_protocol = str(channel.protocol_type or "").lower()
        if protocol == "anthropic":
            return channel_protocol == "anthropic"
        if protocol == "openai":
            return channel_protocol == "openai" and not str(actual_model or "").startswith("responses:")
        if protocol == "responses":
            return channel_protocol in {"openai", "responses"}
        return False

    @staticmethod
    def get_candidates(db: Session, requested_model: str, protocol: str) -> list[PassthroughCandidate]:
        if protocol not in _TEXT_PROTOCOLS:
            return []
        original_model = ModelService.get_enabled_model_by_name(db, requested_model)
        if not original_model or not ChannelPassthroughService._is_text_model(original_model):
            return []
        candidates = []
        for channel, actual_model in ModelService.get_available_channels(db, original_model.id):
            if not int(getattr(channel, "passthrough_enabled", 0) or 0):
                continue
            if not ChannelPassthroughService._channel_supports_protocol(channel, protocol, actual_model):
                continue
            candidates.append(PassthroughCandidate(
                ChannelPassthroughService._snapshot_orm_columns(channel),
                ChannelPassthroughService._snapshot_orm_columns(original_model),
                "passthrough",
            ))
        return sorted(candidates, key=lambda item: int(item.channel.priority or 10))

    @staticmethod
    def get_normal_channel_ids(db: Session, requested_model: str, protocol: str) -> list[int]:
        return [
            int(candidate.channel.id)
            for candidate in ChannelPassthroughService.get_normal_candidates(
                db, requested_model, protocol
            )
        ]

    @staticmethod
    def get_normal_candidates(
        db: Session,
        requested_model: str,
        protocol: str,
    ) -> list[PassthroughCandidate]:
        resolved = ModelService.resolve_model(db, requested_model)
        if not resolved or not ChannelPassthroughService._is_text_model(resolved):
            return []
        candidates = []
        for channel, actual_model in ModelService.get_available_channels(db, resolved.id):
            if int(getattr(channel, "passthrough_enabled", 0) or 0):
                continue
            candidates.append(PassthroughCandidate(
                ChannelPassthroughService._snapshot_orm_columns(channel),
                None,
                "normal",
                ChannelPassthroughService._protocol_rank(channel, actual_model, protocol),
            ))
        return sorted(
            candidates,
            key=lambda item: (item.protocol_rank, int(item.channel.priority or 10)),
        )

    @staticmethod
    def _protocol_rank(channel: Channel, actual_model: str, protocol: str) -> int:
        channel_protocol = str(channel.protocol_type or "").strip().lower()
        raw_target = str(actual_model or "").strip().lower()
        if protocol == "anthropic":
            return 0 if channel_protocol == "anthropic" else (1 if raw_target.startswith("responses:") else 2)
        if protocol == "responses":
            return 0 if raw_target.startswith("responses:") else (1 if channel_protocol == "openai" else 2)
        if protocol == "openai":
            if channel_protocol == "openai" and not raw_target.startswith("responses:"):
                return 0
            return 1 if channel_protocol == "anthropic" else 2
        return 0

    @staticmethod
    def merge_candidates(
        passthrough: list[PassthroughCandidate],
        normal: list[PassthroughCandidate],
    ) -> list[PassthroughCandidate]:
        return sorted(
            [*passthrough, *normal],
            key=lambda item: (item.protocol_rank, int(item.channel.priority or 10)),
        )

    @staticmethod
    def _build_url(channel: Channel, incoming_path: str, query_string: bytes) -> str:
        base = str(channel.base_url or "").rstrip("/")
        parsed = urlsplit(base)
        base_path = parsed.path.rstrip("/")
        incoming = "/" + str(incoming_path or "").lstrip("/")
        canonical = incoming[3:] if incoming.startswith("/v1/") else incoming
        if base_path.endswith(canonical) or base_path.endswith(incoming):
            path = base_path
        elif base_path.endswith("/v1"):
            path = base_path + canonical
        else:
            path = base_path + incoming
        query = query_string.decode("latin-1") if query_string else parsed.query
        return urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))

    @staticmethod
    def _request_headers(channel: Channel, raw_headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
        connection_tokens = set()
        for key, value in raw_headers:
            if key.lower() == b"connection":
                connection_tokens.update(item.strip().lower() for item in value.split(b",") if item.strip())
        blocked = _HOP_HEADERS | _SITE_HEADERS | connection_tokens
        headers = [(key, value) for key, value in raw_headers if key.lower() not in blocked]
        auth_type = str(getattr(channel, "auth_header_type", "") or "").lower()
        api_key = str(channel.api_key or "").encode()
        if auth_type == "authorization" or (not auth_type and channel.protocol_type == "openai"):
            headers.append((b"authorization", b"Bearer " + api_key))
        elif auth_type == "anthropic-api-key":
            headers.append((b"anthropic-api-key", api_key))
        elif auth_type == "x-goog-api-key":
            headers.append((b"x-goog-api-key", api_key))
        else:
            headers.append((b"x-api-key", api_key))
        return headers

    @staticmethod
    def _response_headers(headers: httpx.Headers) -> list[tuple[bytes, bytes]]:
        return [
            (key, value)
            for key, value in headers.raw
            if key.lower() not in _RESPONSE_DROP_HEADERS
        ]

    @staticmethod
    def _build_billing(
        db: Session,
        user: SysUser,
        model: UnifiedModel,
        protocol: str,
        request_data: dict,
        requested_model: str,
    ):
        from app.services.proxy_service import ProxyService
        quota = ProxyService._build_text_quota_precheck(
            db, protocol, request_data, model, user_id=ProxyService._safe_object_id(user)
        )
        billing_context = ProxyService._build_frozen_text_billing_context(
            ProxyService._build_text_billing_context(protocol, request_data), quota
        )
        admission = ProxyService._assert_text_request_allowed(
            db, user, quota_precheck=quota, unified_model=model, requested_model=requested_model
        )
        return admission, billing_context

    @staticmethod
    def _cache_info(observer: UsageObserver, protocol: str) -> Optional[dict[str, Any]]:
        if not observer.usage_seen:
            return None
        if protocol == "anthropic":
            return AnthropicPromptCacheService.merge_into_cache_info(
                None, attempt_meta={"attempted": False}, usage_summary=observer.summary
            )
        from app.services.proxy_service import ProxyService
        return ProxyService._merge_upstream_cache_usage_into_cache_info(
            None, observer.summary, source=f"{protocol}_native_passthrough"
        )

    @staticmethod
    def _finalize(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        model: UnifiedModel,
        channel: Channel,
        observer: UsageObserver,
        request_id: str,
        requested_model: str,
        client_ip: str,
        started_at: float,
        is_stream: bool,
        protocol: str,
        billing_context: dict[str, Any],
        stream_error: Optional[BaseException] = None,
    ) -> None:
        from app.services.proxy_service import ProxyService
        billing_type = str(getattr(model, "billing_type", "") or "token").lower()
        protocol_success = observer.completed and not observer.failed
        should_charge = observer.usage_seen or (billing_type in {"request", "free"} and protocol_success)
        cache_info = ChannelPassthroughService._cache_info(observer, protocol)
        input_tokens = int(observer.summary.get("input_tokens", 0) or 0)
        output_tokens = int(observer.summary.get("output_tokens", 0) or 0)
        response_time_ms = max(0, int((time.time() - started_at) * 1000))
        if should_charge:
            ProxyService._finalize_successful_text_request(
                db, user, api_key_record, model, request_id, requested_model,
                input_tokens, output_tokens, channel, client_ip, response_time_ms,
                is_stream=is_stream, actual_model=requested_model,
                cache_info=cache_info,
                request_type="responses" if protocol == "responses" else "chat",
                raise_on_failure=not is_stream,
                billing_context=billing_context,
            )
            return
        ProxyService._log_failed_request(
            db, user, api_key_record, request_id, requested_model, client_ip, is_stream,
            str(stream_error or "上游成功响应未包含可计费用量"),
            channel=channel, response_time_ms=response_time_ms,
            cache_info=cache_info,
            request_type="responses" if protocol == "responses" else "chat",
            actual_model=requested_model, billing_context=billing_context,
        )

    @staticmethod
    async def forward_http(
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        candidate: PassthroughCandidate,
        request_data: dict,
        raw_body: bytes,
        raw_headers: list[tuple[bytes, bytes]],
        incoming_path: str,
        query_string: bytes,
        client_ip: str,
        protocol: str,
    ) -> Response:
        from app.services.proxy_service import ProxyService
        channel = candidate.channel
        requested_model = str(request_data.get("model") or "")
        is_stream = bool(request_data.get("stream", False))
        request_id = str(uuid.uuid4())
        if candidate.unified_model is None:
            raise ServiceException(500, "透传候选缺少计费模型", "PASSTHROUGH_MODEL_MISSING")
        admission, billing_context = ChannelPassthroughService._build_billing(
            db, user, candidate.unified_model, protocol, request_data, requested_model
        )
        user = ChannelPassthroughService._snapshot_orm_columns(user)
        api_key_record = ChannelPassthroughService._snapshot_orm_columns(api_key_record)
        lease = BillingConcurrencyService.acquire_if_needed(
            admission, request_id,
            ttl_seconds=ProxyService._billing_concurrency_lease_ttl_seconds(db),
        )
        url = ChannelPassthroughService._build_url(channel, incoming_path, query_string)
        headers = ChannelPassthroughService._request_headers(channel, raw_headers)
        observer = UsageObserver(protocol, channel)
        started_at = time.time()
        release_session_connection(db)
        client = httpx.AsyncClient(timeout=ProxyService._build_upstream_stream_timeout(), headers={})
        request = httpx.Request("POST", url, content=raw_body, headers=headers)
        try:
            upstream = await client.send(request, stream=is_stream)
        except Exception:
            BillingConcurrencyService.release(lease)
            await client.aclose()
            raise
        if upstream.status_code < 200 or upstream.status_code >= 300:
            body = await upstream.aread()
            response_headers = ChannelPassthroughService._response_headers(upstream.headers)
            await upstream.aclose()
            await client.aclose()
            BillingConcurrencyService.release(lease)
            raise PassthroughUpstreamError(upstream.status_code, body, response_headers)

        response_headers = ChannelPassthroughService._response_headers(upstream.headers)
        if not is_stream:
            try:
                body = await upstream.aread()
                try:
                    observer.feed_json(json.loads(body))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                observer.completed = not observer.failed
                ChannelPassthroughService._finalize(
                    db, user, api_key_record, candidate.unified_model, channel, observer,
                    request_id, requested_model, client_ip, started_at, False, protocol,
                    billing_context,
                )
                response = Response(content=body, status_code=upstream.status_code)
                response.raw_headers = response_headers
                return response
            finally:
                await upstream.aclose()
                await client.aclose()
                BillingConcurrencyService.release(lease)

        async def stream_body():
            queue: asyncio.Queue = asyncio.Queue(maxsize=16)
            disconnected = asyncio.Event()

            async def offer(item) -> None:
                while not disconnected.is_set():
                    try:
                        await asyncio.wait_for(queue.put(item), timeout=0.1)
                        return
                    except asyncio.TimeoutError:
                        continue

            async def pump() -> None:
                stream_error = None
                try:
                    async for chunk in upstream.aiter_bytes():
                        observer.feed_sse(chunk)
                        if not disconnected.is_set():
                            await offer(("data", chunk))
                    observer.finish_sse()
                except BaseException as exc:
                    stream_error = exc
                    if not disconnected.is_set():
                        await offer(("error", exc))
                finally:
                    if not disconnected.is_set():
                        await offer(("done", None))
                    try:
                        ChannelPassthroughService._finalize(
                            db, user, api_key_record, candidate.unified_model, channel, observer,
                            request_id, requested_model, client_ip, started_at, True, protocol,
                            billing_context, stream_error,
                        )
                    except Exception as exc:
                        logger.error("Native passthrough accounting failed request_id=%s: %s", request_id, exc, exc_info=True)
                    await upstream.aclose()
                    await client.aclose()
                    BillingConcurrencyService.release(lease)

            task = asyncio.create_task(pump())
            try:
                while True:
                    kind, payload = await queue.get()
                    if kind == "done":
                        return
                    if kind == "error":
                        raise payload
                    yield payload
            finally:
                disconnected.set()
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.shield(task)

        response = StreamingResponse(stream_body(), status_code=upstream.status_code)
        response.raw_headers = response_headers
        response._native_passthrough_observer = observer
        return response

    @staticmethod
    async def dispatch_http(
        request: Request,
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        request_data: dict,
        protocol: str,
        normal_handler,
    ) -> Response:
        from app.services.proxy_service import ProxyService
        requested_model = str(request_data.get("model") or "")
        passthrough = ChannelPassthroughService.get_candidates(db, requested_model, protocol)
        normal = ChannelPassthroughService.get_normal_candidates(db, requested_model, protocol)
        if not passthrough:
            return await normal_handler(
                copy.deepcopy(request_data),
                [int(candidate.channel.id) for candidate in normal],
            )
        candidates = ChannelPassthroughService.merge_candidates(passthrough, normal)
        raw_body = await request.body()
        raw_headers = list(request.scope.get("headers") or [])
        query_string = request.scope.get("query_string") or b""
        client_ip = request.client.host if request.client else None
        last_error = None
        last_upstream_error: Optional[PassthroughUpstreamError] = None
        for candidate in candidates:
            try:
                if candidate.mode == "normal":
                    response = await normal_handler(copy.deepcopy(request_data), [int(candidate.channel.id)])
                else:
                    response = await ChannelPassthroughService.forward_http(
                        db, user, api_key_record, candidate, request_data, raw_body, raw_headers,
                        request.url.path, query_string, client_ip, protocol,
                    )
                if isinstance(response, StreamingResponse):
                    response, usable = await ChannelPassthroughService._prefetch_stream(response, protocol)
                    if not usable:
                        last_error = ServiceException(502, "候选渠道在首个事件前失败", "UPSTREAM_STREAM_START_FAILED")
                        continue
                return response
            except PassthroughUpstreamError as exc:
                last_error = exc
                last_upstream_error = exc
                if exc.status_code < 500 and exc.status_code not in {401, 403, 408, 409, 429}:
                    response = Response(content=exc.body, status_code=exc.status_code)
                    response.raw_headers = exc.headers
                    return response
                ProxyService._record_channel_failure(db, candidate.channel, exc)
                continue
            except ServiceException as exc:
                if exc.error_code in _LOCAL_TERMINAL_ERRORS or (
                    exc.status_code < 500 and exc.status_code != 429
                ):
                    raise
                last_error = exc
                continue
            except Exception as exc:
                last_error = exc
                if candidate.mode == "passthrough":
                    ProxyService._record_channel_failure(db, candidate.channel, exc)
                continue
        if last_upstream_error:
            response = Response(content=last_upstream_error.body, status_code=last_upstream_error.status_code)
            response.raw_headers = last_upstream_error.headers
            return response
        if isinstance(last_error, ServiceException):
            raise last_error
        raise ProxyService._build_all_channels_failed_exception()

    @staticmethod
    async def _prefetch_stream(response: StreamingResponse, protocol: str) -> tuple[StreamingResponse, bool]:
        """Start the upstream before committing response headers, enabling safe first-event fallback."""
        iterator = response.body_iterator
        prefetched: list[Any] = []
        preview = bytearray()

        def inspect_preview(include_trailing: bool = False) -> Optional[bool]:
            normalized = bytes(preview).replace(b"\r\n", b"\n")
            events = normalized.split(b"\n\n")
            if not include_trailing:
                events = events[:-1]
            first_payload = None
            usage_seen = False
            for event in events:
                if not event.strip() or event.lstrip().startswith(b":"):
                    continue
                data_lines = [
                    line[5:].lstrip()
                    for line in event.split(b"\n")
                    if line.startswith(b"data:")
                ]
                if not data_lines:
                    continue
                raw = b"\n".join(data_lines)
                if raw == b"[DONE]":
                    return True
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if include_trailing:
                        return True
                    continue
                if first_payload is None:
                    first_payload = payload
                if isinstance(payload, dict):
                    nested = payload.get("response") if isinstance(payload.get("response"), dict) else payload
                    usage_seen = usage_seen or isinstance(nested.get("usage"), dict)
            if first_payload is None:
                return None
            event_type = str(first_payload.get("type") or "") if isinstance(first_payload, dict) else ""
            is_error = event_type in {"error", "response.failed"} or (
                isinstance(first_payload, dict) and first_payload.get("error") is not None
            )
            return not is_error or usage_seen

        async def close_and_check_usage() -> bool:
            close = getattr(iterator, "aclose", None)
            if close:
                await close()
            observer = getattr(response, "_native_passthrough_observer", None)
            return bool(getattr(observer, "usage_seen", False))

        try:
            while len(preview) < 65536:
                chunk = await iterator.__anext__()
                prefetched.append(chunk)
                preview.extend(chunk.encode() if isinstance(chunk, str) else bytes(chunk))
                classification = inspect_preview()
                if classification is None:
                    continue
                if not classification:
                    usage_seen = await close_and_check_usage()
                    if not usage_seen:
                        return response, False
                break
        except StopAsyncIteration:
            classification = inspect_preview(include_trailing=True)
            if classification is None:
                return response, False
            if not classification:
                observer = getattr(response, "_native_passthrough_observer", None)
                if not bool(getattr(observer, "usage_seen", False)):
                    return response, False
        except Exception:
            await close_and_check_usage()
            return response, False

        async def replay():
            for chunk in prefetched:
                yield chunk
            async for chunk in iterator:
                yield chunk

        response.body_iterator = replay()
        return response, True

    @staticmethod
    async def forward_count_tokens(
        request: Request,
        db: Session,
        request_data: dict,
    ) -> Optional[Response]:
        requested_model = str(request_data.get("model") or "")
        passthrough = ChannelPassthroughService.get_candidates(db, requested_model, "anthropic")
        if not passthrough:
            return None
        normal = ChannelPassthroughService.get_normal_candidates(db, requested_model, "anthropic")
        candidates = ChannelPassthroughService.merge_candidates(passthrough, normal)
        raw_body = await request.body()
        raw_headers = list(request.scope.get("headers") or [])
        last_response: Optional[Response] = None
        last_error: Optional[Exception] = None
        for candidate in candidates:
            if candidate.mode == "normal":
                return None
            channel = candidate.channel
            client = httpx.AsyncClient(timeout=60.0, headers={})
            try:
                upstream = await client.send(httpx.Request(
                    "POST",
                    ChannelPassthroughService._build_url(
                        channel, request.url.path, request.scope.get("query_string") or b""
                    ),
                    content=raw_body,
                    headers=ChannelPassthroughService._request_headers(channel, raw_headers),
                ))
                if 200 <= upstream.status_code < 300:
                    response = Response(content=upstream.content, status_code=upstream.status_code)
                    response.raw_headers = ChannelPassthroughService._response_headers(upstream.headers)
                    return response
                last_response = Response(content=upstream.content, status_code=upstream.status_code)
                last_response.raw_headers = ChannelPassthroughService._response_headers(upstream.headers)
                if upstream.status_code < 500 and upstream.status_code not in {408, 409, 429}:
                    return last_response
            except Exception as exc:
                last_error = exc
                logger.warning("count_tokens passthrough failed channel=%s: %s", channel.name, exc)
            finally:
                await client.aclose()
        if last_response is not None:
            return last_response
        if last_error is not None:
            from app.services.proxy_service import ProxyService
            raise ProxyService._build_all_channels_failed_exception() from last_error
        return None

    @staticmethod
    def _websocket_url(channel: Channel, incoming_path: str, query_string: bytes) -> str:
        url = ChannelPassthroughService._build_url(channel, incoming_path, query_string)
        parsed = urlsplit(url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, ""))

    @staticmethod
    def _extract_websocket_model(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        model = payload.get("model")
        if model:
            return str(model)
        response = payload.get("response")
        if isinstance(response, dict) and response.get("model"):
            return str(response["model"])
        return ""

    @staticmethod
    async def dispatch_websocket(
        websocket: WebSocket,
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        client_ip: str,
    ) -> tuple[bool, Optional[Union[str, bytes]], Optional[list[int]]]:
        """Use a native upstream WebSocket when the selected channel opts in."""
        try:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return True, None, None
            first_message = message.get("text")
            if first_message is None:
                first_message = message.get("bytes")
            if first_message is None:
                return False, None, None
        except WebSocketDisconnect:
            return True, None, None
        try:
            first_payload = json.loads(first_message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, first_message, None
        requested_model = ChannelPassthroughService._extract_websocket_model(first_payload)
        if not requested_model:
            return False, first_message, None

        passthrough = ChannelPassthroughService.get_candidates(db, requested_model, "responses")
        normal = ChannelPassthroughService.get_normal_candidates(db, requested_model, "responses")
        normal_ids = [int(item.channel.id) for item in normal]
        if not passthrough:
            return False, first_message, normal_ids
        candidates = ChannelPassthroughService.merge_candidates(passthrough, normal)
        if not candidates:
            return False, first_message, normal_ids

        last_error: Optional[Exception] = None
        for candidate in candidates:
            if candidate.mode == "normal":
                from app.services.proxy_service import ProxyService
                handled = await ProxyService.handle_responses_websocket(
                    db,
                    user,
                    api_key_record,
                    websocket,
                    client_ip,
                    request_headers=dict(getattr(websocket, "headers", {}).items()),
                    initial_message=first_message,
                    _allowed_channel_ids=[int(candidate.channel.id)],
                    _defer_retryable_start_failure=True,
                )
                if handled:
                    return True, None, None
                continue
            try:
                await ChannelPassthroughService._relay_websocket(
                    websocket, db, user, api_key_record, candidate,
                    first_message, first_payload, client_ip,
                )
                return True, None, None
            except Exception as exc:
                last_error = exc
                if isinstance(exc, ServiceException) and exc.error_code in _LOCAL_TERMINAL_ERRORS:
                    await websocket.close(code=1008, reason=str(exc.detail)[:120])
                    return True, None, None
                logger.warning(
                    "Native Responses websocket handshake failed channel=%s channel_id=%s: %s",
                    candidate.channel.name, candidate.channel.id, exc,
                )
                from app.services.proxy_service import ProxyService
                ProxyService._record_channel_failure(db, candidate.channel, exc)
                continue
        from app.services.proxy_service import ProxyService
        if last_error:
            logger.info("All Responses websocket candidates failed before commit: %s", last_error)
        await websocket.send_text(json.dumps(
            ProxyService._build_responses_error_payload(
                "调用失败，所有候选渠道均不可用，请稍后重试",
                status_code=503,
            ),
            ensure_ascii=False,
        ))
        return True, None, None

    @staticmethod
    async def _relay_websocket(
        websocket: WebSocket,
        db: Session,
        user: SysUser,
        api_key_record: UserApiKey,
        candidate: PassthroughCandidate,
        first_message: Union[str, bytes],
        first_payload: dict,
        client_ip: str,
    ) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise ServiceException(503, "原生 WebSocket 依赖不可用", "PASSTHROUGH_WEBSOCKET_UNAVAILABLE") from exc

        from app.services.proxy_service import ProxyService
        if candidate.unified_model is None:
            raise ServiceException(500, "透传候选缺少计费模型", "PASSTHROUGH_MODEL_MISSING")
        channel = candidate.channel
        raw_headers = list(websocket.scope.get("headers") or [])
        blocked_ws = {
            b"sec-websocket-key", b"sec-websocket-version", b"sec-websocket-extensions",
            b"sec-websocket-protocol",
        }
        upstream_headers = [
            (key.decode("latin-1"), value.decode("latin-1"))
            for key, value in ChannelPassthroughService._request_headers(channel, raw_headers)
            if key.lower() not in blocked_ws and key.lower() not in _HOP_HEADERS
        ]
        requested_subprotocols = []
        for key, value in raw_headers:
            if key.lower() == b"sec-websocket-protocol":
                requested_subprotocols.extend(
                    item.strip().decode("latin-1") for item in value.split(b",") if item.strip()
                )
        url = ChannelPassthroughService._websocket_url(
            channel,
            websocket.url.path,
            websocket.scope.get("query_string") or b"",
        )

        requested_model = ChannelPassthroughService._extract_websocket_model(first_payload)
        last_model_name = requested_model

        def build_turn(payload: dict, model_name: str, model: UnifiedModel) -> dict[str, Any]:
            is_prewarm = payload.get("generate") is False
            request_id = str(uuid.uuid4())
            admission = None
            billing_context: dict[str, Any] = {}
            lease = None
            if not is_prewarm:
                admission, billing_context = ChannelPassthroughService._build_billing(
                    db, user, model, "responses", payload, model_name
                )
                lease = BillingConcurrencyService.acquire_if_needed(
                    admission, request_id,
                    ttl_seconds=ProxyService._billing_concurrency_lease_ttl_seconds(db),
                )
            return {
                "request_id": request_id,
                "model": model,
                "requested_model": model_name,
                "billing_context": billing_context,
                "lease": lease,
                "observer": UsageObserver("responses", channel),
                "started_at": time.time(),
                "finalized": False,
                "billable": not is_prewarm,
                "response_id": None,
            }

        first_type = str(first_payload.get("type") or "")
        turn = (
            build_turn(first_payload, requested_model, candidate.unified_model)
            if first_type in {"response.create", "response.append"}
            else None
        )
        user = ChannelPassthroughService._snapshot_orm_columns(user)
        api_key_record = ChannelPassthroughService._snapshot_orm_columns(api_key_record)
        finalized_response_ids: set[str] = set()

        def parse_json_frame(payload: Union[str, bytes]) -> Optional[dict[str, Any]]:
            try:
                parsed = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                return None
            return parsed if isinstance(parsed, dict) else None

        def event_response_id(payload: dict[str, Any]) -> Optional[str]:
            response = payload.get("response")
            if isinstance(response, dict) and response.get("id"):
                return str(response["id"])
            if payload.get("response_id"):
                return str(payload["response_id"])
            return None

        async def connect_upstream():
            kwargs = {"max_size": None, "ping_interval": 20, "ping_timeout": 20}
            if requested_subprotocols:
                kwargs["subprotocols"] = requested_subprotocols
            try:
                return await websockets.connect(url, additional_headers=upstream_headers, **kwargs)
            except TypeError:
                return await websockets.connect(url, extra_headers=upstream_headers, **kwargs)

        upstream = None
        committed = False
        client_connected = True
        release_session_connection(db)

        def finalize_turn(current_turn: Optional[dict[str, Any]], stream_error: Optional[BaseException] = None) -> None:
            if not current_turn or current_turn.get("finalized"):
                return
            current_turn["finalized"] = True
            if current_turn.get("response_id"):
                finalized_response_ids.add(str(current_turn["response_id"]))
            if not current_turn.get("billable"):
                return
            try:
                ChannelPassthroughService._finalize(
                    db, user, api_key_record, current_turn["model"], channel, current_turn["observer"],
                    current_turn["request_id"], current_turn["requested_model"], client_ip,
                    current_turn["started_at"], True, "responses",
                    current_turn["billing_context"], stream_error,
                )
            finally:
                BillingConcurrencyService.release(current_turn.get("lease"))

        try:
            upstream = await connect_upstream()
            await upstream.send(first_message)
            committed = True

            async def client_to_upstream() -> None:
                nonlocal turn, client_connected, last_model_name
                while True:
                    message = await websocket.receive()
                    message_type = message.get("type")
                    if message_type == "websocket.disconnect":
                        client_connected = False
                        return
                    payload = message.get("text")
                    if payload is None:
                        payload = message.get("bytes")
                    if payload is None:
                        continue
                    parsed = parse_json_frame(payload)
                    request_type = str(parsed.get("type") or "") if parsed else ""
                    if request_type in {"response.create", "response.append"}:
                        if turn and not turn.get("finalized"):
                            raise ServiceException(409, "原生 WebSocket 暂不支持并发生成轮次", "WEBSOCKET_TURN_CONFLICT")
                        next_model_name = (
                            ChannelPassthroughService._extract_websocket_model(parsed)
                            or last_model_name
                        )
                        matching = ChannelPassthroughService.get_candidates(db, next_model_name, "responses")
                        next_candidate = next(
                            (item for item in matching if int(item.channel.id) == int(channel.id)),
                            None,
                        )
                        if not next_candidate or next_candidate.unified_model is None:
                            raise ServiceException(400, "后续模型未映射到当前透传渠道", "WEBSOCKET_MODEL_CHANNEL_MISMATCH")
                        turn = build_turn(parsed, next_model_name, next_candidate.unified_model)
                        last_model_name = next_model_name
                    await upstream.send(payload)

            async def upstream_to_client() -> None:
                async for payload in upstream:
                    parsed = parse_json_frame(payload)
                    if parsed:
                        event_type = str(parsed.get("type") or "")
                        response_id = event_response_id(parsed)
                        is_finalized_duplicate = bool(
                            response_id and response_id in finalized_response_ids
                        )
                        if not is_finalized_duplicate and turn and not turn.get("finalized"):
                            known_id = turn.get("response_id")
                            if response_id and known_id and known_id != response_id:
                                raise ServiceException(
                                    502,
                                    "上游 WebSocket 返回了无法关联的响应",
                                    "WEBSOCKET_RESPONSE_MISMATCH",
                                )
                            if event_type == "response.created" and response_id:
                                turn["response_id"] = response_id
                            turn["observer"].feed_json(parsed)
                            if event_type in {
                                "response.completed", "response.incomplete",
                                "response.failed", "response.cancelled",
                            }:
                                if response_id:
                                    turn["response_id"] = response_id
                                finalize_turn(turn)
                        elif (
                            not is_finalized_duplicate
                            and response_id
                            and event_type.startswith("response.")
                        ):
                            raise ServiceException(
                                502,
                                "上游 WebSocket 返回了未知轮次响应",
                                "WEBSOCKET_RESPONSE_MISMATCH",
                            )
                    if isinstance(payload, str):
                        if client_connected:
                            await websocket.send_text(payload)
                    else:
                        if client_connected:
                            await websocket.send_bytes(payload)

            sender = asyncio.create_task(client_to_upstream())
            receiver = asyncio.create_task(upstream_to_client())
            done, pending = await asyncio.wait(
                {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
            if sender in done and receiver in pending and turn and not turn.get("finalized"):
                try:
                    await asyncio.wait_for(receiver, timeout=600.0)
                except asyncio.TimeoutError:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
            else:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
        except WebSocketDisconnect as exc:
            finalize_turn(turn, exc)
        except Exception as exc:
            finalize_turn(turn, exc)
            if committed:
                if client_connected:
                    await websocket.close(code=1011, reason="上游 WebSocket 会话异常")
                return
            raise
        finally:
            if turn and not turn.get("finalized"):
                finalize_turn(
                    turn,
                    ServiceException(499, "WebSocket 会话提前结束", "WEBSOCKET_DISCONNECTED"),
                )
            if upstream is not None:
                await upstream.close()
