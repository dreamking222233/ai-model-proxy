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
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Optional

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
from app.services.anthropic_prompt_cache_service import AnthropicPromptCacheService
from app.services.conversation_shadow_service import ConversationShadowService
from app.services.conversation_session_service import ConversationSessionService
from app.services.compression_guard_service import CompressionGuardService
from app.services.upstream_session_strategy_service import UpstreamSessionStrategyService
from app.services.request_body_cache_service import RequestBodyCacheService
from app.services.request_cache_summary_service import RequestCacheSummaryService
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
    _REQUEST_DEBUG_MAX_STRING = 400
    _REQUEST_DEBUG_MAX_LIST_ITEMS = 6
    _REQUEST_DEBUG_MAX_DICT_ITEMS = 12
    _REQUEST_DEBUG_MAX_DEPTH = 5
    _REQUEST_DEBUG_MESSAGE_WINDOW = 6
    _REQUEST_DEBUG_REPEAT_SAMPLES = 5
    _STREAM_DEBUG_EVENT_LIMIT = 80
    _recent_anthropic_request_fingerprints: dict[str, dict[str, Any]] = {}

    # ----- Model identity system prompt mapping -----
    _MODEL_VENDOR_MAP = [
        # (keyword, display_vendor)
        ("claude", "Anthropic"),
        ("gpt", "OpenAI"),
        ("o1", "OpenAI"),
        ("o3", "OpenAI"),
        ("o4", "OpenAI"),
        ("gemini", "Google"),
        ("deepseek", "DeepSeek"),
        ("qwen", "Alibaba"),
    ]

    @staticmethod
    def _build_model_identity_prompt(requested_model: str) -> str:
        """Build a model identity system prompt like '你是 Claude Opus 4.6 模型，由 Anthropic 开发'."""
        if not requested_model:
            return ""
        model_lower = requested_model.lower()
        vendor = ""
        for keyword, display_vendor in ProxyService._MODEL_VENDOR_MAP:
            if keyword in model_lower:
                vendor = display_vendor
                break
        if vendor:
            return f"你是 {requested_model} 模型，由 {vendor} 开发"
        return f"你是 {requested_model} 模型"

    @staticmethod
    def _inject_model_identity(request_data: dict, requested_model: str, protocol: str) -> None:
        """Inject a model identity system prompt into the request body (in-place).

        Supports three protocols:
          * ``openai``    – prepend to ``messages`` as ``{"role":"system",...}``
          * ``anthropic`` – prepend to ``system`` field (string or block list)
          * ``responses`` – prepend to ``instructions`` field
        """
        prompt = ProxyService._build_model_identity_prompt(requested_model)
        if not prompt:
            return

        if protocol == "openai":
            # messages: [{role, content}, ...]
            messages = request_data.get("messages")
            if not isinstance(messages, list):
                return
            system_msg = {"role": "system", "content": prompt}
            # Insert at position 0
            messages.insert(0, system_msg)

        elif protocol == "anthropic":
            # system can be a string or list of blocks
            existing = request_data.get("system")
            if existing is None or existing == "":
                request_data["system"] = prompt
            elif isinstance(existing, str):
                request_data["system"] = prompt + "\n\n" + existing
            elif isinstance(existing, list):
                # Prepend as a text block
                request_data["system"] = [{"type": "text", "text": prompt}] + existing

        elif protocol == "responses":
            # instructions is a string field
            existing = request_data.get("instructions") or ""
            if existing:
                request_data["instructions"] = prompt + "\n\n" + existing
            else:
                request_data["instructions"] = prompt

    @staticmethod
    def _truncate_log_string(value: Any, max_length: int | None = None) -> str:
        """Return a readable string preview for debug logs."""
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        limit = max_length or ProxyService._REQUEST_DEBUG_MAX_STRING
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...<truncated {len(text) - limit} chars>"

    @staticmethod
    def _compact_for_debug_log(
        value: Any,
        *,
        depth: int = 0,
    ) -> Any:
        """Compact nested payloads so request debug logs stay readable."""
        if value is None or isinstance(value, (bool, int, float)):
            return value

        if isinstance(value, str):
            return ProxyService._truncate_log_string(value)

        if depth >= ProxyService._REQUEST_DEBUG_MAX_DEPTH:
            return ProxyService._truncate_log_string(value)

        if isinstance(value, list):
            limited_items = value[:ProxyService._REQUEST_DEBUG_MAX_LIST_ITEMS]
            compacted = [
                ProxyService._compact_for_debug_log(item, depth=depth + 1)
                for item in limited_items
            ]
            if len(value) > len(limited_items):
                compacted.append(
                    {
                        "__truncated_items__": len(value) - len(limited_items),
                    }
                )
            return compacted

        if isinstance(value, dict):
            compacted: dict[str, Any] = {}
            items = list(value.items())
            limited_items = items[:ProxyService._REQUEST_DEBUG_MAX_DICT_ITEMS]
            for key, item_value in limited_items:
                compacted[str(key)] = ProxyService._compact_for_debug_log(
                    item_value,
                    depth=depth + 1,
                )
            if len(items) > len(limited_items):
                compacted["__truncated_keys__"] = len(items) - len(limited_items)
            return compacted

        return ProxyService._truncate_log_string(value)

    @staticmethod
    def _stable_debug_dump(value: Any) -> str:
        """Serialize values consistently for hashing and size estimates."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        except TypeError:
            return str(value)

    @staticmethod
    def _debug_hash(value: Any) -> str:
        """Hash debug payloads for duplicate detection."""
        return hashlib.sha256(
            ProxyService._stable_debug_dump(value).encode("utf-8", errors="replace")
        ).hexdigest()

    @staticmethod
    def _debug_size(value: Any) -> int:
        """Measure serialized size for duplicate payload estimates."""
        return len(ProxyService._stable_debug_dump(value))

    @staticmethod
    def _summarize_exact_duplicates(entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize exact duplicate entries within a single request payload."""
        if not entries:
            return {
                "total": 0,
                "unique": 0,
                "repeated_groups": 0,
                "duplicate_instances": 0,
                "duplicate_chars": 0,
                "samples": [],
            }

        grouped: dict[str, dict[str, Any]] = {}
        for entry in entries:
            signature = entry["signature"]
            bucket = grouped.setdefault(
                signature,
                {
                    "count": 0,
                    "size_chars": entry["size_chars"],
                    "preview": entry["preview"],
                    "location": entry["location"],
                },
            )
            bucket["count"] += 1

        repeated = []
        duplicate_instances = 0
        duplicate_chars = 0
        for item in grouped.values():
            if item["count"] <= 1:
                continue
            extra_instances = item["count"] - 1
            item["duplicate_chars"] = extra_instances * item["size_chars"]
            duplicate_instances += extra_instances
            duplicate_chars += item["duplicate_chars"]
            repeated.append(item)

        repeated.sort(
            key=lambda item: (item["duplicate_chars"], item["count"], item["size_chars"]),
            reverse=True,
        )

        return {
            "total": len(entries),
            "unique": len(grouped),
            "repeated_groups": len(repeated),
            "duplicate_instances": duplicate_instances,
            "duplicate_chars": duplicate_chars,
            "samples": repeated[:ProxyService._REQUEST_DEBUG_REPEAT_SAMPLES],
        }

    @staticmethod
    def _build_anthropic_duplicate_analysis(request_data: dict) -> dict[str, Any]:
        """Calculate duplicate content metrics for one Anthropic request."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            messages = []

        system_value = request_data.get("system")
        if isinstance(system_value, list):
            system_blocks = system_value
        elif system_value is None:
            system_blocks = []
        else:
            system_blocks = [system_value]

        tools = request_data.get("tools")
        if not isinstance(tools, list):
            tools = []

        system_entries = []
        for index, block in enumerate(system_blocks):
            system_entries.append(
                {
                    "signature": ProxyService._debug_hash(block),
                    "size_chars": ProxyService._debug_size(block),
                    "preview": ProxyService._compact_for_debug_log(block),
                    "location": f"system[{index}]",
                }
            )

        tool_entries = []
        for index, tool in enumerate(tools):
            tool_entries.append(
                {
                    "signature": ProxyService._debug_hash(tool),
                    "size_chars": ProxyService._debug_size(tool),
                    "preview": ProxyService._compact_for_debug_log(tool),
                    "location": f"tools[{index}]",
                }
            )

        message_entries = []
        content_entries = []
        for index, message in enumerate(messages):
            role = str(message.get("role", "") or "") if isinstance(message, dict) else ""
            message_entries.append(
                {
                    "signature": ProxyService._debug_hash(message),
                    "size_chars": ProxyService._debug_size(message),
                    "preview": ProxyService._compact_for_debug_log(message),
                    "location": f"messages[{index}] role={role}",
                }
            )

            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                blocks = content
            elif content is None:
                blocks = []
            else:
                blocks = [content]

            for block_index, block in enumerate(blocks):
                block_location = f"messages[{index}].content[{block_index}] role={role}"
                content_entries.append(
                    {
                        "signature": ProxyService._debug_hash(block),
                        "size_chars": ProxyService._debug_size(block),
                        "preview": ProxyService._compact_for_debug_log(block),
                        "location": block_location,
                    }
                )

        return {
            "system_blocks": ProxyService._summarize_exact_duplicates(system_entries),
            "tools": ProxyService._summarize_exact_duplicates(tool_entries),
            "messages": ProxyService._summarize_exact_duplicates(message_entries),
            "content_blocks": ProxyService._summarize_exact_duplicates(content_entries),
        }

    @staticmethod
    def _build_anthropic_request_fingerprint(request_data: dict) -> dict[str, Any]:
        """Build section-level hashes for cross-request duplicate comparison."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            messages = []

        tools = request_data.get("tools")
        if not isinstance(tools, list):
            tools = []

        system_value = request_data.get("system")
        tail_messages = messages[-ProxyService._REQUEST_DEBUG_MESSAGE_WINDOW:]

        return {
            "payload_hash": ProxyService._debug_hash(request_data),
            "system_hash": ProxyService._debug_hash(system_value),
            "tools_hash": ProxyService._debug_hash(tools),
            "messages_hash": ProxyService._debug_hash(messages),
            "messages_tail_hash": ProxyService._debug_hash(tail_messages),
            "message_count": len(messages),
            "estimated_input_tokens": ProxyService.estimate_anthropic_input_tokens(request_data),
            "sizes": {
                "payload_chars": ProxyService._debug_size(request_data),
                "system_chars": ProxyService._debug_size(system_value),
                "tools_chars": ProxyService._debug_size(tools),
                "messages_chars": ProxyService._debug_size(messages),
                "messages_tail_chars": ProxyService._debug_size(tail_messages),
            },
        }

    @staticmethod
    def _compare_with_previous_anthropic_request(
        request_key: Optional[str],
        fingerprint: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Compare current Anthropic request with the previous one for the same key."""
        if not request_key:
            return None

        previous = ProxyService._recent_anthropic_request_fingerprints.get(request_key)
        ProxyService._recent_anthropic_request_fingerprints[request_key] = fingerprint
        if not previous:
            return {
                "has_previous": False,
            }

        sizes = fingerprint.get("sizes", {})
        previous_sizes = previous.get("sizes", {})
        repeated_sections = []
        reused_chars = 0
        for section, size_key in (
            ("system", "system_chars"),
            ("tools", "tools_chars"),
            ("messages", "messages_chars"),
            ("messages_tail", "messages_tail_chars"),
            ("payload", "payload_chars"),
        ):
            hash_key = f"{section}_hash"
            if previous.get(hash_key) == fingerprint.get(hash_key):
                repeated_sections.append(section)
                reused_chars += int(sizes.get(size_key, 0) or 0)

        return {
            "has_previous": True,
            "same_payload": previous.get("payload_hash") == fingerprint.get("payload_hash"),
            "same_system": previous.get("system_hash") == fingerprint.get("system_hash"),
            "same_tools": previous.get("tools_hash") == fingerprint.get("tools_hash"),
            "same_messages": previous.get("messages_hash") == fingerprint.get("messages_hash"),
            "same_messages_tail": previous.get("messages_tail_hash") == fingerprint.get("messages_tail_hash"),
            "repeated_sections": repeated_sections,
            "reused_chars_estimate": reused_chars,
            "message_count_delta": int(fingerprint.get("message_count", 0) or 0) - int(previous.get("message_count", 0) or 0),
            "estimated_input_tokens_delta": int(fingerprint.get("estimated_input_tokens", 0) or 0) - int(previous.get("estimated_input_tokens", 0) or 0),
            "payload_chars_delta": int(sizes.get("payload_chars", 0) or 0) - int(previous_sizes.get("payload_chars", 0) or 0),
        }

    @staticmethod
    def _build_anthropic_request_debug_snapshot(request_data: dict) -> dict[str, Any]:
        """Build a compact snapshot for Anthropic request debugging."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            messages = []

        tools = request_data.get("tools")
        if not isinstance(tools, list):
            tools = []

        system_value = request_data.get("system")
        tail_messages = messages[-ProxyService._REQUEST_DEBUG_MESSAGE_WINDOW:]

        return {
            "model": request_data.get("model"),
            "stream": bool(request_data.get("stream", False)),
            "max_tokens": request_data.get("max_tokens"),
            "temperature": request_data.get("temperature"),
            "top_p": request_data.get("top_p"),
            "message_count": len(messages),
            "estimated_input_tokens": ProxyService.estimate_anthropic_input_tokens(request_data),
            "section_hashes": {
                "system": ProxyService._debug_hash(system_value),
                "tools": ProxyService._debug_hash(tools),
                "messages": ProxyService._debug_hash(messages),
                "messages_tail": ProxyService._debug_hash(tail_messages),
                "payload": ProxyService._debug_hash(request_data),
            },
            "section_sizes": {
                "system_chars": ProxyService._debug_size(system_value),
                "tools_chars": ProxyService._debug_size(tools),
                "messages_chars": ProxyService._debug_size(messages),
                "messages_tail_chars": ProxyService._debug_size(tail_messages),
                "payload_chars": ProxyService._debug_size(request_data),
            },
            "duplicate_analysis": ProxyService._build_anthropic_duplicate_analysis(request_data),
            "system": ProxyService._compact_for_debug_log(system_value),
            "tools": ProxyService._compact_for_debug_log(tools),
            "tools_count": len(tools),
            "tool_choice": ProxyService._compact_for_debug_log(request_data.get("tool_choice")),
            "messages_tail": ProxyService._compact_for_debug_log(tail_messages),
        }

    @staticmethod
    def _log_anthropic_request_debug(
        stage: str,
        request_id: str,
        request_data: dict,
        *,
        channel: Channel | None = None,
        requested_model: Optional[str] = None,
        client_ip: Optional[str] = None,
        force_compat: bool = False,
        request_key: Optional[str] = None,
    ) -> None:
        """Emit a compact request snapshot for Claude relay debugging."""
        snapshot = ProxyService._build_anthropic_request_debug_snapshot(request_data)
        snapshot["cross_request_compare"] = ProxyService._compare_with_previous_anthropic_request(
            request_key,
            ProxyService._build_anthropic_request_fingerprint(request_data),
        )
        logger.info(
            "Anthropic request debug stage=%s request_id=%s requested_model=%s actual_model=%s "
            "channel=%s channel_id=%s client_ip=%s force_compat=%s snapshot=%s",
            stage,
            request_id,
            requested_model,
            request_data.get("model"),
            channel.name if channel else None,
            channel.id if channel else None,
            client_ip,
            force_compat,
            json.dumps(snapshot, ensure_ascii=False),
        )

    @staticmethod
    def _build_anthropic_runtime_debug_summary(
        request_data: dict,
        request_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Build a focused Anthropic request summary for runtime debugging."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            messages = []

        tools = request_data.get("tools")
        if not isinstance(tools, list):
            tools = []

        tool_names: list[str] = []
        for tool in tools[:12]:
            if not isinstance(tool, dict):
                continue
            tool_name = str(tool.get("name", "") or "")
            if tool_name:
                tool_names.append(tool_name)

        normalized_headers = {
            str(key).lower(): value
            for key, value in (request_headers or {}).items()
            if isinstance(value, str) and value.strip()
        }

        return {
            "stream": bool(request_data.get("stream", False)),
            "message_count": len(messages),
            "max_tokens": request_data.get("max_tokens"),
            "tools_count": len(tools),
            "tool_names": tool_names,
            "tool_choice": ProxyService._compact_for_debug_log(request_data.get("tool_choice")),
            "anthropic_version": normalized_headers.get("anthropic-version"),
            "anthropic_beta": normalized_headers.get("anthropic-beta"),
        }

    @staticmethod
    def _log_anthropic_runtime_debug(
        stage: str,
        request_id: str,
        requested_model: str,
        request_data: dict,
        *,
        channel: Channel | None = None,
        client_ip: Optional[str] = None,
        upstream_model: Optional[str] = None,
        upstream_api: Optional[str] = None,
        force_compat: bool = False,
        request_headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Emit concise runtime debug logs for Anthropic requests."""
        summary = ProxyService._build_anthropic_runtime_debug_summary(
            request_data,
            request_headers=request_headers,
        )
        logger.info(
            "Anthropic runtime debug stage=%s request_id=%s requested_model=%s upstream_model=%s "
            "upstream_api=%s channel=%s channel_id=%s client_ip=%s force_compat=%s summary=%s",
            stage,
            request_id,
            requested_model,
            upstream_model or request_data.get("model"),
            upstream_api,
            channel.name if channel else None,
            channel.id if channel else None,
            client_ip,
            force_compat,
            json.dumps(summary, ensure_ascii=False),
        )

    @staticmethod
    def _record_stream_debug_event(
        sequence: list[str],
        counts: dict[str, int],
        event_name: str,
        detail: Optional[Any] = None,
    ) -> None:
        """Append one compact event marker into an in-memory stream trace."""
        detail_text = ""
        if detail is not None and detail != "":
            detail_text = ProxyService._truncate_log_string(str(detail), 120)
        event_key = event_name if not detail_text else f"{event_name}:{detail_text}"
        counts[event_key] = counts.get(event_key, 0) + 1
        if len(sequence) < ProxyService._STREAM_DEBUG_EVENT_LIMIT:
            sequence.append(event_key)

    @staticmethod
    def _log_anthropic_stream_debug(
        stage: str,
        request_id: str,
        requested_model: str,
        *,
        actual_model: Optional[str],
        channel: Channel,
        client_ip: Optional[str],
        status: str,
        event_sequence: list[str],
        event_counts: dict[str, int],
        upstream_sequence: Optional[list[str]] = None,
        upstream_counts: Optional[dict[str, int]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit one summarized stream trace for Anthropic requests."""
        trace: dict[str, Any] = {
            "status": status,
            "event_sequence": event_sequence,
            "event_counts": event_counts,
        }
        if upstream_sequence is not None:
            trace["upstream_sequence"] = upstream_sequence
        if upstream_counts is not None:
            trace["upstream_counts"] = upstream_counts
        if extra:
            trace["extra"] = extra
        logger.info(
            "Anthropic stream debug stage=%s request_id=%s requested_model=%s actual_model=%s "
            "channel=%s channel_id=%s client_ip=%s trace=%s",
            stage,
            request_id,
            requested_model,
            actual_model,
            channel.name,
            channel.id,
            client_ip,
            json.dumps(trace, ensure_ascii=False),
        )

    @staticmethod
    def _extract_cache_info_from_error(exc: Exception) -> Optional[dict[str, Any]]:
        """Read request-body cache info that middleware attached to an exception."""
        cache_info = getattr(exc, "_request_cache_info", None)
        return cache_info if isinstance(cache_info, dict) else None

    @staticmethod
    def _merge_anthropic_usage_snapshot(
        target: dict[str, Any],
        usage: Optional[dict[str, Any]],
    ) -> None:
        """Merge Anthropic usage fragments from streaming or SSE-parsed responses."""
        if not isinstance(usage, dict):
            return

        for key in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
            "cache_creation_5m_input_tokens",
            "cache_creation_1h_input_tokens",
        ):
            if usage.get(key) is not None:
                target[key] = int(usage.get(key) or 0)

        cache_creation = usage.get("cache_creation")
        if isinstance(cache_creation, dict):
            merged_cache_creation = dict(target.get("cache_creation") or {})
            if cache_creation.get("ephemeral_5m_input_tokens") is not None:
                merged_cache_creation["ephemeral_5m_input_tokens"] = int(
                    cache_creation.get("ephemeral_5m_input_tokens") or 0
                )
            if cache_creation.get("ephemeral_1h_input_tokens") is not None:
                merged_cache_creation["ephemeral_1h_input_tokens"] = int(
                    cache_creation.get("ephemeral_1h_input_tokens") or 0
                )
            if merged_cache_creation:
                target["cache_creation"] = merged_cache_creation

    @staticmethod
    def _resolve_prompt_cache_billing_input_tokens(
        db: Session,
        usage_summary: dict[str, Any],
    ) -> int:
        """Resolve billed input tokens for Anthropic prompt-cache requests."""
        billing_mode = AnthropicPromptCacheService.get_billing_mode(db)
        if billing_mode == "actual_upstream":
            return int(usage_summary.get("input_tokens", 0) or 0)
        return int(usage_summary.get("logical_input_tokens", 0) or 0)

    @staticmethod
    def _merge_prompt_cache_state_into_cache_info(
        cache_info: Optional[dict[str, Any]],
        prompt_cache_state: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Merge Anthropic prompt-cache request/usage info into shared cache_info."""
        if not prompt_cache_state:
            return cache_info
        return AnthropicPromptCacheService.merge_into_cache_info(
            cache_info,
            attempt_meta=prompt_cache_state.get("attempt_meta"),
            usage_summary=prompt_cache_state.get("usage_summary"),
            fallback_triggered=bool(prompt_cache_state.get("fallback_triggered")),
            fallback_reason=prompt_cache_state.get("fallback_reason"),
        )

    @staticmethod
    def _merge_conversation_shadow_into_cache_info(
        cache_info: Optional[dict[str, Any]],
        conversation_shadow_info: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        """Merge conversation shadow compaction info into shared cache_info."""
        return ConversationShadowService.merge_into_cache_info(
            cache_info,
            conversation_shadow_info,
        )

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
    def _resolve_mapped_upstream_target(
        channel: Channel,
        actual_model_name: str,
        *,
        default_openai_api: str = "openai_chat",
    ) -> tuple[str, str]:
        """Resolve mapping directives like ``responses:gpt-5.4`` into model + API."""
        raw_target = str(actual_model_name or "")
        prefix, separator, remainder = raw_target.partition(":")
        if separator and prefix == "responses" and remainder:
            return remainder, "responses"

        protocol = str(getattr(channel, "protocol_type", "openai") or "openai")
        if protocol == "anthropic":
            return raw_target, "anthropic_messages"
        return raw_target, default_openai_api

    @staticmethod
    def _build_responses_message_content_parts(value) -> list[dict]:
        """Convert Anthropic string/content blocks into Responses message parts."""
        if value is None:
            return []
        if isinstance(value, str):
            if value == "":
                return []
            return [{"type": "input_text", "text": value}]
        if not isinstance(value, list):
            return [{"type": "input_text", "text": str(value)}]

        parts: list[dict] = []
        for item in value:
            if isinstance(item, str):
                if item == "":
                    continue
                parts.append({"type": "input_text", "text": item})
                continue
            if not isinstance(item, dict):
                parts.append({"type": "input_text", "text": str(item)})
                continue

            item_type = str(item.get("type", "") or "")
            if item_type in {"text", "input_text", "output_text"}:
                text_value = str(item.get("text", "") or "")
                if text_value:
                    parts.append({"type": "input_text", "text": text_value})
                continue

            if item_type == "image" and isinstance(item.get("source"), dict):
                source = item.get("source") or {}
                source_type = str(source.get("type", "") or "")
                if source_type == "base64":
                    data_value = str(source.get("data", "") or "")
                    media_type = str(source.get("media_type", "") or "")
                    if data_value and media_type:
                        parts.append({
                            "type": "input_image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data_value,
                            },
                        })
                        continue
                if source_type == "url":
                    url_value = str(source.get("url", "") or "")
                    if url_value:
                        parts.append({
                            "type": "input_image",
                            "source": {
                                "type": "url",
                                "url": url_value,
                            },
                        })
                        continue

            if "text" in item and item.get("text") is not None:
                text_value = str(item.get("text"))
                if text_value:
                    parts.append({"type": "input_text", "text": text_value})
                continue

            parts.append({"type": "input_text", "text": json.dumps(item, ensure_ascii=False)})

        return parts

    @staticmethod
    def _build_responses_message_item(role: str, parts: list[dict]) -> Optional[dict]:
        """Build one Responses message item and collapse to string when possible."""
        if not parts:
            return None
        if len(parts) == 1 and parts[0].get("type") == "input_text":
            return {
                "type": "message",
                "role": role,
                "content": str(parts[0].get("text", "") or ""),
            }
        return {
            "type": "message",
            "role": role,
            "content": parts,
        }

    @staticmethod
    def _convert_anthropic_tools_to_responses(
        request_data: dict,
    ) -> tuple[list[dict], Optional[str | dict]]:
        """Convert Anthropic tool declarations to Responses tool schema."""
        raw_tools = request_data.get("tools")
        responses_tools: list[dict] = []
        if isinstance(raw_tools, list):
            for tool in raw_tools:
                if not isinstance(tool, dict):
                    continue
                tool_name = str(tool.get("name", "") or "")
                if not tool_name:
                    continue
                responses_tools.append({
                    "type": "function",
                    "name": tool_name,
                    "description": tool.get("description"),
                    "parameters": copy.deepcopy(
                        tool.get("input_schema")
                        or {"type": "object", "properties": {}}
                    ),
                })

        raw_tool_choice = request_data.get("tool_choice")
        if isinstance(raw_tool_choice, dict):
            choice_type = str(raw_tool_choice.get("type", "") or "")
            if choice_type == "auto":
                return responses_tools, "auto"
            if choice_type == "any":
                return responses_tools, "required"
            if choice_type == "tool":
                tool_name = str(raw_tool_choice.get("name", "") or "")
                if tool_name:
                    return responses_tools, {
                        "type": "function",
                        "name": tool_name,
                    }
        return responses_tools, None

    @staticmethod
    def _convert_anthropic_request_to_responses(
        request_data: dict,
        *,
        requested_model: str,
    ) -> dict:
        """Convert an Anthropic Messages request into an OpenAI Responses request."""
        request_copy = copy.deepcopy(request_data)
        responses_request: dict[str, Any] = {
            "model": request_copy.get("model"),
            "stream": bool(request_copy.get("stream", False)),
            "store": False,
        }

        max_tokens = request_copy.get("max_tokens")
        if max_tokens is not None:
            responses_request["max_output_tokens"] = max_tokens

        input_items: list[dict] = []

        system_parts = ProxyService._build_responses_message_content_parts(
            request_copy.get("system")
        )
        system_message = ProxyService._build_responses_message_item("developer", system_parts)
        if system_message:
            input_items.append(system_message)

        for raw_message in request_copy.get("messages", []) or []:
            if not isinstance(raw_message, dict):
                continue

            role = str(raw_message.get("role", "") or "")
            if role not in {"user", "assistant"}:
                continue

            content = raw_message.get("content")
            if isinstance(content, str):
                content_blocks = [{"type": "text", "text": content}] if content else []
            elif isinstance(content, list):
                content_blocks = copy.deepcopy(content)
            elif content is None:
                content_blocks = []
            else:
                content_blocks = [{"type": "text", "text": str(content)}]

            message_parts: list[dict] = []

            def flush_message_parts() -> None:
                nonlocal message_parts
                message_item = ProxyService._build_responses_message_item(role, message_parts)
                if message_item:
                    input_items.append(message_item)
                message_parts = []

            for block in content_blocks:
                if isinstance(block, str):
                    if block:
                        message_parts.append({"type": "input_text", "text": block})
                    continue

                if not isinstance(block, dict):
                    message_parts.append({"type": "input_text", "text": str(block)})
                    continue

                block_type = str(block.get("type", "") or "")
                if block_type in {"text", "image"}:
                    message_parts.extend(
                        ProxyService._build_responses_message_content_parts([block])
                    )
                    continue

                if block_type in {"thinking", "redacted_thinking"}:
                    flush_message_parts()
                    # Anthropic thinking blocks are provider-internal artifacts.
                    # Do not replay them into Responses input items, because many
                    # /v1/responses upstreams expect a different reasoning schema
                    # and will reject ad-hoc ``type=reasoning`` payloads.
                    continue

                if block_type == "tool_use" and role == "assistant":
                    flush_message_parts()
                    tool_name = str(block.get("name", "") or "tool")
                    call_id = str(
                        block.get("id")
                        or f"call_{uuid.uuid4().hex[:24]}"
                    )
                    input_items.append({
                        "type": "function_call",
                        "call_id": call_id,
                        "name": tool_name,
                        "arguments": json.dumps(
                            block.get("input") or {},
                            ensure_ascii=False,
                        ),
                    })
                    continue

                if block_type == "tool_result" and role == "user":
                    flush_message_parts()
                    tool_use_id = str(
                        block.get("tool_use_id")
                        or block.get("id")
                        or f"call_{uuid.uuid4().hex[:24]}"
                    )
                    tool_result = ProxyService._stringify_legacy_function_content(
                        block.get("content")
                    ) or ""
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": tool_use_id,
                        "output": tool_result,
                    })
                    continue

                message_parts.append({
                    "type": "input_text",
                    "text": json.dumps(block, ensure_ascii=False),
                })

            flush_message_parts()

        if not input_items:
            input_items = [{
                "type": "message",
                "role": "user",
                "content": "",
            }]

        responses_request["input"] = input_items

        tools, tool_choice = ProxyService._convert_anthropic_tools_to_responses(
            request_copy
        )
        if tools:
            responses_request["tools"] = tools
        if tool_choice is not None:
            responses_request["tool_choice"] = tool_choice

        if requested_model == "claude-opus-4-6":
            reasoning = copy.deepcopy(responses_request.get("reasoning") or {})
            reasoning["effort"] = "high"
            reasoning.setdefault("summary", "auto")
            responses_request["reasoning"] = reasoning

        return responses_request

    @staticmethod
    def _build_anthropic_text_blocks(value) -> list[dict]:
        """Convert string/list content into Anthropic text blocks."""
        if value is None:
            return []
        if isinstance(value, str):
            if value == "":
                return []
            return [{"type": "text", "text": value}]
        if not isinstance(value, list):
            return [{"type": "text", "text": str(value)}]

        blocks: list[dict] = []
        for item in value:
            if isinstance(item, str):
                if item == "":
                    continue
                blocks.append({"type": "text", "text": item})
                continue
            if not isinstance(item, dict):
                blocks.append({"type": "text", "text": str(item)})
                continue

            item_type = str(item.get("type", "") or "")
            if item_type in {"text", "input_text", "output_text"}:
                text_value = str(item.get("text", "") or "")
                if text_value == "":
                    continue
                blocks.append({"type": "text", "text": text_value})
                continue

            image_url = item.get("image_url")
            if item_type == "image_url" and isinstance(image_url, dict):
                raw_url = str(image_url.get("url", "") or "")
                if raw_url.startswith("data:image/") and ";base64," in raw_url:
                    meta, encoded = raw_url.split(";base64,", 1)
                    media_type = meta[5:]
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    })
                    continue

            if item_type == "image" and isinstance(item.get("source"), dict):
                blocks.append(copy.deepcopy(item))
                continue

            if "text" in item and item.get("text") is not None:
                text_value = str(item.get("text"))
                if text_value == "":
                    continue
                blocks.append({"type": "text", "text": text_value})
                continue

            blocks.append({"type": "text", "text": json.dumps(item, ensure_ascii=False)})

        return blocks

    @staticmethod
    def _merge_anthropic_messages(messages: list[dict]) -> list[dict]:
        """Merge adjacent Anthropic messages with the same role."""
        merged: list[dict] = []

        for raw_message in messages:
            if not isinstance(raw_message, dict):
                continue

            role = str(raw_message.get("role", "") or "")
            if role not in {"user", "assistant"}:
                continue

            content = raw_message.get("content")
            if isinstance(content, str):
                content_blocks = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                content_blocks = copy.deepcopy(content)
            elif content is None:
                content_blocks = []
            else:
                content_blocks = [{"type": "text", "text": str(content)}]

            if not content_blocks:
                content_blocks = [{"type": "text", "text": ""}]

            if merged and merged[-1]["role"] == role:
                merged[-1]["content"].extend(content_blocks)
            else:
                merged.append({
                    "role": role,
                    "content": content_blocks,
                })

        return merged

    @staticmethod
    def _parse_tool_arguments(arguments) -> dict:
        """Parse OpenAI function arguments into an Anthropic tool input object."""
        if isinstance(arguments, dict):
            return copy.deepcopy(arguments)
        if arguments is None:
            return {}
        if isinstance(arguments, str):
            stripped = arguments.strip()
            if not stripped:
                return {}
            try:
                parsed = json.loads(stripped)
            except (TypeError, ValueError):
                return {"raw_arguments": arguments}
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        return {"value": arguments}

    @staticmethod
    def _stringify_tool_arguments_json(arguments: Any) -> str:
        """Serialize tool arguments into the JSON text Anthropic deltas expect."""
        if arguments is None:
            return ""
        if isinstance(arguments, str):
            return arguments
        try:
            return json.dumps(arguments, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(arguments)

    @staticmethod
    def _extract_responses_reasoning_text(value: Any) -> str:
        """Flatten Responses reasoning payloads into a readable Anthropic thinking string."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                text_value = ProxyService._extract_responses_reasoning_text(item)
                if text_value:
                    parts.append(text_value)
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            for key in ("text", "summary_text", "content", "thinking"):
                text_value = ProxyService._extract_responses_reasoning_text(value.get(key))
                if text_value:
                    return text_value
            try:
                return json.dumps(value, ensure_ascii=False).strip()
            except (TypeError, ValueError):
                return str(value).strip()
        return str(value).strip()

    @staticmethod
    def _convert_openai_tools_to_anthropic(request_data: dict) -> tuple[list[dict], Optional[dict], bool]:
        """Convert OpenAI tool definitions and tool choice to Anthropic format."""
        raw_tools = request_data.get("tools")
        if not raw_tools and isinstance(request_data.get("functions"), list):
            raw_tools = [
                {"type": "function", "function": copy.deepcopy(function)}
                for function in request_data.get("functions", [])
            ]

        anthropic_tools: list[dict] = []
        if isinstance(raw_tools, list):
            for tool in raw_tools:
                if not isinstance(tool, dict):
                    continue

                if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                    function_payload = tool["function"]
                    function_name = str(function_payload.get("name", "") or "")
                    if not function_name:
                        continue
                    anthropic_tools.append({
                        "name": function_name,
                        "description": function_payload.get("description"),
                        "input_schema": copy.deepcopy(
                            function_payload.get("parameters")
                            or {"type": "object", "properties": {}}
                        ),
                    })
                    continue

                if tool.get("name"):
                    anthropic_tools.append(copy.deepcopy(tool))

        raw_tool_choice = request_data.get("tool_choice")
        if raw_tool_choice is None and request_data.get("function_call") is not None:
            raw_tool_choice = request_data.get("function_call")

        disable_tools = False
        anthropic_tool_choice = None

        if isinstance(raw_tool_choice, str):
            if raw_tool_choice == "none":
                disable_tools = True
            elif raw_tool_choice == "required":
                anthropic_tool_choice = {"type": "any"}
            elif raw_tool_choice == "auto":
                anthropic_tool_choice = {"type": "auto"}
        elif isinstance(raw_tool_choice, dict):
            choice_type = str(raw_tool_choice.get("type", "") or "")
            if choice_type == "none":
                disable_tools = True
            elif choice_type == "function":
                function_payload = raw_tool_choice.get("function") or {}
                function_name = str(function_payload.get("name", "") or "")
                if function_name:
                    anthropic_tool_choice = {"type": "tool", "name": function_name}
            elif choice_type in {"tool", "auto", "any"}:
                anthropic_tool_choice = copy.deepcopy(raw_tool_choice)
            elif raw_tool_choice.get("name"):
                anthropic_tool_choice = {
                    "type": "tool",
                    "name": str(raw_tool_choice.get("name")),
                }

        if disable_tools:
            return [], None, True
        return anthropic_tools, anthropic_tool_choice, False

    @staticmethod
    def _convert_openai_request_to_anthropic(request_data: dict) -> dict:
        """Convert an OpenAI chat-completions request into Anthropic Messages API."""
        request_copy = copy.deepcopy(request_data)
        requested_n = request_copy.get("n")
        if requested_n not in (None, 1):
            raise ServiceException(
                400,
                "Anthropic upstream does not support n > 1 for chat completions",
                "UPSTREAM_INVALID_REQUEST",
            )

        anthropic_request: dict = {
            "model": request_copy.get("model"),
            "max_tokens": (
                request_copy.get("max_completion_tokens")
                or request_copy.get("max_tokens")
                or 4096
            ),
            "stream": bool(request_copy.get("stream", False)),
        }

        for source_field, target_field in (
            ("temperature", "temperature"),
            ("top_p", "top_p"),
            ("metadata", "metadata"),
            ("thinking", "thinking"),
        ):
            value = request_copy.get(source_field)
            if value is not None:
                anthropic_request[target_field] = copy.deepcopy(value)

        stop_value = request_copy.get("stop")
        if isinstance(stop_value, str) and stop_value:
            anthropic_request["stop_sequences"] = [stop_value]
        elif isinstance(stop_value, list):
            anthropic_request["stop_sequences"] = [
                str(item) for item in stop_value if str(item or "")
            ]

        system_blocks = ProxyService._build_anthropic_text_blocks(request_copy.get("system"))
        anthropic_messages: list[dict] = []

        for raw_message in request_copy.get("messages", []) or []:
            if not isinstance(raw_message, dict):
                continue

            role = str(raw_message.get("role", "") or "")
            if role in {"system", "developer"}:
                system_blocks.extend(
                    ProxyService._build_anthropic_text_blocks(raw_message.get("content"))
                )
                continue

            if role in {"user", "assistant"}:
                content_blocks = ProxyService._build_anthropic_text_blocks(
                    raw_message.get("content")
                )

                if role == "assistant" and isinstance(raw_message.get("tool_calls"), list):
                    for tool_call in raw_message.get("tool_calls", []):
                        if not isinstance(tool_call, dict):
                            continue
                        function_payload = tool_call.get("function") or {}
                        tool_name = str(function_payload.get("name", "") or "tool")
                        tool_id = str(
                            tool_call.get("id")
                            or f"toolu_{uuid.uuid4().hex[:24]}"
                        )
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool_name,
                            "input": ProxyService._parse_tool_arguments(
                                function_payload.get("arguments")
                            ),
                        })

                anthropic_messages.append({
                    "role": role,
                    "content": content_blocks,
                })
                continue

            if role in {"tool", "function"}:
                tool_result = ProxyService._stringify_legacy_function_content(
                    raw_message.get("content")
                ) or ""
                anthropic_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": str(
                            raw_message.get("tool_call_id")
                            or raw_message.get("id")
                            or raw_message.get("name")
                            or f"toolu_{uuid.uuid4().hex[:24]}"
                        ),
                        "content": tool_result,
                    }],
                })
                continue

            anthropic_messages.append({
                "role": "user",
                "content": ProxyService._build_anthropic_text_blocks(
                    raw_message.get("content")
                ),
            })

        merged_messages = ProxyService._merge_anthropic_messages(anthropic_messages)
        if not merged_messages:
            merged_messages = [{"role": "user", "content": [{"type": "text", "text": ""}]}]

        if system_blocks:
            anthropic_request["system"] = system_blocks

        anthropic_tools, anthropic_tool_choice, tools_disabled = (
            ProxyService._convert_openai_tools_to_anthropic(request_copy)
        )
        if anthropic_tools and not tools_disabled:
            anthropic_request["tools"] = anthropic_tools
        if anthropic_tool_choice and not tools_disabled:
            anthropic_request["tool_choice"] = anthropic_tool_choice

        anthropic_request["messages"] = merged_messages
        return anthropic_request

    @staticmethod
    def _convert_anthropic_stop_reason_to_openai(stop_reason: Optional[str], has_tool_calls: bool = False) -> str:
        """Map Anthropic stop reasons to OpenAI finish reasons."""
        if stop_reason == "tool_use":
            return "tool_calls"
        if stop_reason == "max_tokens":
            return "length"
        if has_tool_calls:
            return "tool_calls"
        return "stop"

    @staticmethod
    def _convert_anthropic_response_to_openai(response_body: dict) -> dict:
        """Convert an Anthropic Messages API response into OpenAI chat-completions format."""
        content_blocks = response_body.get("content") or []
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[dict] = []

        if isinstance(content_blocks, list):
            for index, block in enumerate(content_blocks):
                if not isinstance(block, dict):
                    content_parts.append(str(block))
                    continue

                block_type = str(block.get("type", "") or "")
                if block_type == "text":
                    content_parts.append(str(block.get("text", "") or ""))
                elif block_type in {"thinking", "redacted_thinking"}:
                    reasoning_parts.append(str(block.get("thinking", "") or block.get("text", "") or ""))
                elif block_type == "tool_use":
                    tool_calls.append({
                        "id": str(block.get("id") or f"call_{index}"),
                        "type": "function",
                        "function": {
                            "name": str(block.get("name", "") or "tool"),
                            "arguments": json.dumps(
                                block.get("input") or {},
                                ensure_ascii=False,
                            ),
                        },
                    })

        message_payload = {
            "role": "assistant",
            "content": "".join(content_parts) if content_parts else None,
        }
        if reasoning_parts:
            message_payload["reasoning_content"] = "".join(reasoning_parts)
        if tool_calls:
            message_payload["tool_calls"] = tool_calls

        usage = response_body.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        finish_reason = ProxyService._convert_anthropic_stop_reason_to_openai(
            response_body.get("stop_reason"),
            has_tool_calls=bool(tool_calls),
        )

        return {
            "id": response_body.get("id") or f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": response_body.get("model") or "unknown",
            "choices": [{
                "index": 0,
                "message": message_payload,
                "finish_reason": finish_reason,
            }],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    @staticmethod
    def _convert_responses_output_to_anthropic_content(output_items: Any) -> list[dict]:
        """Convert Responses output items into Anthropic content blocks."""
        if not isinstance(output_items, list):
            return [{"type": "text", "text": ""}]

        content_blocks: list[dict] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue

            item_type = str(item.get("type", "") or "")
            if item_type == "message":
                for part in item.get("content") or []:
                    if not isinstance(part, dict):
                        continue
                    part_type = str(part.get("type", "") or "")
                    if part_type in {"output_text", "text", "input_text"}:
                        text_value = str(part.get("text", "") or "")
                        if text_value:
                            content_blocks.append({
                                "type": "text",
                                "text": text_value,
                            })
                continue

            if item_type == "function_call":
                tool_name = str(item.get("name", "") or "tool")
                tool_id = str(
                    item.get("call_id")
                    or item.get("id")
                    or f"toolu_{uuid.uuid4().hex[:24]}"
                )
                content_blocks.append({
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool_name,
                    "input": ProxyService._parse_tool_arguments(
                        item.get("arguments")
                    ),
                })
                continue

            if item_type == "reasoning":
                thinking_value = ProxyService._extract_responses_reasoning_text(
                    item.get("summary") or item.get("content")
                )
                if thinking_value:
                    content_blocks.append({
                        "type": "thinking",
                        "thinking": thinking_value,
                    })

        if not content_blocks:
            return [{"type": "text", "text": ""}]
        return content_blocks

    @staticmethod
    def _convert_responses_response_to_anthropic(response_body: dict) -> dict:
        """Convert an OpenAI Responses response into an Anthropic message response."""
        output_items = response_body.get("output") or []
        content_blocks = ProxyService._convert_responses_output_to_anthropic_content(
            output_items
        )
        usage = response_body.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        has_tool_use = any(
            isinstance(block, dict) and str(block.get("type", "") or "") == "tool_use"
            for block in content_blocks
        )

        return {
            "id": response_body.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
            "type": "message",
            "role": "assistant",
            "content": content_blocks,
            "model": response_body.get("model") or "unknown",
            "stop_reason": "tool_use" if has_tool_use else "end_turn",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }

    @staticmethod
    def _build_anthropic_sse_event(event_name: str, payload: dict) -> str:
        """Render one Anthropic-compatible SSE event."""
        return (
            f"event: {event_name}\n"
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        )

    @staticmethod
    def _build_openai_stream_chunk(
        *,
        chunk_id: str,
        model_name: str,
        created_at: int,
        delta: Optional[dict] = None,
        finish_reason: Optional[str] = None,
        usage: Optional[dict] = None,
    ) -> str:
        """Build an OpenAI-compatible SSE chunk payload."""
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created_at,
            "model": model_name,
            "choices": [],
        }
        if usage is not None:
            payload["usage"] = usage
            return json.dumps(payload, ensure_ascii=False)

        payload["choices"] = [{
            "index": 0,
            "delta": delta or {},
            "finish_reason": finish_reason,
        }]
        return json.dumps(payload, ensure_ascii=False)

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

        # Inject model identity system prompt
        ProxyService._inject_model_identity(client_request, requested_model, "responses")

        unified_model, channels = ProxyService._prepare_responses_request_context(
            db, user, requested_model
        )

        last_error: Exception | None = None
        request_error: ServiceException | None = None
        request_cache_info: Optional[dict[str, Any]] = None
        for channel, actual_model_name in channels:
            try:
                upstream_model_name, upstream_api = ProxyService._resolve_mapped_upstream_target(
                    channel,
                    actual_model_name,
                    default_openai_api="responses",
                )
                channel_request = copy.deepcopy(client_request)
                channel_request["model"] = upstream_model_name
                channel_request = ProxyService._prepare_responses_request_body(
                    upstream_model_name,
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
                error_cache_info = ProxyService._extract_cache_info_from_error(exc)
                if error_cache_info:
                    request_cache_info = error_cache_info
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
            cache_info=request_cache_info,
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

            # Inject model identity system prompt for websocket requests
            ProxyService._inject_model_identity(normalized_request, requested_model, "responses")

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
            last_cache_info: Optional[dict[str, Any]] = None
            for channel, actual_model_name in channels:
                channel_request = copy.deepcopy(normalized_request)
                upstream_model_name, _ = ProxyService._resolve_mapped_upstream_target(
                    channel,
                    actual_model_name,
                    default_openai_api="responses",
                )
                channel_request["model"] = upstream_model_name
                channel_request = ProxyService._prepare_responses_request_body(
                    upstream_model_name,
                    channel_request,
                )
                cache_info = RequestBodyCacheService.analyze_request(
                    db=db,
                    user_id=user.id,
                    request_body=channel_request,
                    request_format="responses",
                    requested_model=requested_model,
                )
                last_cache_info = cache_info
                started_at = time.time()
                try:
                    completed_output, input_tokens, output_tokens, first_chunk_time = (
                        await ProxyService._forward_responses_websocket_turn(
                            websocket,
                            channel,
                            channel_request,
                            requested_model,
                            request_headers=request_headers,
                        )
                    )
                    response_time_ms = ProxyService._calculate_elapsed_ms(started_at, first_chunk_time)
                    ProxyService._record_success(db, channel)
                    ProxyService._deduct_balance_and_log(
                        db, user, api_key_record, unified_model, request_id,
                        requested_model, input_tokens, output_tokens, channel,
                        client_ip, response_time_ms, is_stream=True,
                        actual_model=channel_request.get("model"),
                        cache_info=cache_info,
                    )
                    last_response_output = completed_output
                    turn_completed = True
                    break
                except ResponsesTurnError as exc:
                    response_time_ms = ProxyService._calculate_elapsed_ms(
                        started_at,
                        getattr(exc, "first_chunk_time", None),
                    )
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
                            cache_info=cache_info,
                        )
                        return
                    continue
                except Exception as exc:
                    response_time_ms = ProxyService._calculate_elapsed_ms(started_at)
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
                        cache_info=cache_info,
                    )
                    return

            if turn_completed:
                continue

            error_detail = str(last_error) if last_error else "Unknown error"
            ProxyService._log_failed_request(
                db, user, api_key_record, request_id, requested_model,
                client_ip, True, error_detail,
                cache_info=last_cache_info,
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
    def _calculate_elapsed_ms(start_time: float, first_chunk_time: Optional[float] = None) -> int:
        target_time = first_chunk_time or time.time()
        return max(0, int((target_time - start_time) * 1000))

    @staticmethod
    def _resolve_stream_response_time_ms(start_time: float, cache_state: Optional[dict[str, Any]] = None) -> int:
        cache_state = cache_state or {}
        first_chunk_time = cache_state.get("first_stream_output_time")
        if first_chunk_time is None:
            collector = cache_state.get("stream_collector")
            first_chunk_time = getattr(collector, "first_chunk_time", None)
        return ProxyService._calculate_elapsed_ms(start_time, first_chunk_time)

    @staticmethod
    def _has_stream_first_chunk(cache_state: Optional[dict[str, Any]] = None) -> bool:
        cache_state = cache_state or {}
        if cache_state.get("first_stream_output_time") is not None:
            return True
        collector = cache_state.get("stream_collector")
        return getattr(collector, "first_chunk_time", None) is not None

    @staticmethod
    def _format_stream_timeout_error() -> str:
        return "流式请求未收到首字即结束"

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
                            if collected_usage.get("_first_stream_output_time") is None:
                                collected_usage["_first_stream_output_time"] = time.time()

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
            cache_state: dict[str, Any] = {}

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="responses",
                    request_format="responses",
                    model=model_name,
                    billing_callback=billing_callback,
                    cache_state=cache_state,
                ):
                    if (
                        cache_state.get("first_stream_output_time") is None
                        and isinstance(sse_line, str)
                        and "response.output_text.delta" in sse_line
                    ):
                        cache_state["first_stream_output_time"] = time.time()
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
                response_time_ms = ProxyService._resolve_stream_response_time_ms(start_time, cache_state)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        error_cache_info = cache_state.get("cache_info") or ProxyService._extract_cache_info_from_error(stream_error)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                            cache_info=error_cache_info,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                            actual_model=request_data.get("model"),
                            cache_info=cache_state.get("cache_info"),
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
    ) -> tuple[list, int, int, Optional[float]]:
        """Forward one websocket turn to upstream ``/responses`` SSE."""
        completed_output: list = []
        input_tokens = 0
        output_tokens = 0
        completed = False
        sent_any_payload = False
        saw_error = False
        error_message = ""
        first_chunk_time: Optional[float] = None

        try:
            async for payload in ProxyService._iter_responses_upstream_payloads(
                channel,
                request_data,
                requested_model,
                request_headers=request_headers,
            ):
                sent_any_payload = True
                if first_chunk_time is None:
                    first_chunk_time = time.time()
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
                error = ResponsesTurnError(str(exc), can_retry=False)
                error.first_chunk_time = first_chunk_time
                raise error from exc
            error = ResponsesTurnError(str(exc), can_retry=True)
            error.first_chunk_time = first_chunk_time
            raise error from exc

        if completed:
            return completed_output, input_tokens, output_tokens, first_chunk_time

        if saw_error:
            error = ResponsesTurnError(error_message or "Upstream responses error", can_retry=not sent_any_payload)
            error.first_chunk_time = first_chunk_time
            raise error

        if sent_any_payload:
            error_payload = ProxyService._build_responses_error_payload(
                "stream closed before response.completed",
                status_code=408,
            )
            await websocket.send_text(json.dumps(error_payload, ensure_ascii=False))
            error = ResponsesTurnError("stream closed before response.completed", can_retry=False)
            error.first_chunk_time = first_chunk_time
            raise error

        error = ResponsesTurnError("stream closed before response.completed", can_retry=True)
        error.first_chunk_time = first_chunk_time
        raise error

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
            request_format="responses",
            requested_model=requested_model,
        )

        response_time_ms = ProxyService._calculate_elapsed_ms(start_time)

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
            actual_model=request_data.get("model"),
            cache_info=cache_info,
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

        # Inject model identity system prompt
        ProxyService._inject_model_identity(request_data, requested_model, "openai")

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
        request_cache_info: Optional[dict[str, Any]] = None
        for channel, actual_model_name in channels:
            upstream_model_name, upstream_api = ProxyService._resolve_mapped_upstream_target(
                channel,
                actual_model_name,
            )
            explicit_compat = ProxyService._is_kiro_amazonq_channel(channel, upstream_model_name)
            legacy_compat_retry = (
                not explicit_compat
                and upstream_api == "anthropic_messages"
                and ProxyService._is_legacy_kiro_amazonq_host(channel, upstream_model_name)
            )
            channel_request_error: ServiceException | None = None
            compat_attempts = [True] if explicit_compat else [False]
            if legacy_compat_retry:
                compat_attempts.append(True)

            for compat_mode in compat_attempts:
                try:
                    # Build upstream request with the actual model name
                    request_data_copy = dict(request_data)
                    request_data_copy["model"] = upstream_model_name
                    request_data_copy = ProxyService._prepare_openai_request_for_channel(
                        channel,
                        request_data_copy,
                        force_compat=compat_mode,
                    )
                    upstream_protocol = str(getattr(channel, "protocol_type", "openai") or "openai")
                    if upstream_api == "responses":
                        raise ServiceException(
                            400,
                            "This model mapping requires /v1/messages or /v1/responses, not /v1/chat/completions",
                            "UPSTREAM_INVALID_REQUEST",
                        )

                    if is_stream:
                        if upstream_protocol == "anthropic":
                            return await ProxyService._stream_openai_via_anthropic_request(
                                db, user, api_key_record, channel, unified_model,
                                request_data_copy, request_id, requested_model, client_ip,
                                request_headers=request_headers,
                            )
                        return await ProxyService._stream_openai_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                        )
                    else:
                        if upstream_protocol == "anthropic":
                            return await ProxyService._non_stream_openai_via_anthropic_request(
                                db, user, api_key_record, channel, unified_model,
                                request_data_copy, request_id, requested_model, client_ip,
                                request_headers=request_headers,
                            )
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
                    error_cache_info = ProxyService._extract_cache_info_from_error(e)
                    if error_cache_info:
                        request_cache_info = error_cache_info
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
                        channel.name, channel.id, upstream_model_name, e,
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
            cache_info=request_cache_info,
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

        # Inject model identity system prompt
        ProxyService._inject_model_identity(request_data, requested_model, "anthropic")

        ProxyService._log_anthropic_runtime_debug(
            "entry",
            request_id,
            requested_model,
            request_data,
            client_ip=client_ip,
            request_headers=request_headers,
        )
        conversation_shadow_info = ConversationShadowService.analyze_request(
            db,
            user_id=user.id,
            requested_model=requested_model,
            protocol_type="anthropic",
            request_data=request_data,
            request_headers=request_headers,
            is_stream=bool(is_stream),
        )

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
        request_cache_info: Optional[dict[str, Any]] = None
        for channel, actual_model_name in channels:
            upstream_model_name, upstream_api = ProxyService._resolve_mapped_upstream_target(
                channel,
                actual_model_name,
            )
            explicit_compat = ProxyService._is_kiro_amazonq_channel(channel, upstream_model_name)
            legacy_compat_retry = (
                not explicit_compat
                and upstream_api == "anthropic_messages"
                and ProxyService._is_legacy_kiro_amazonq_host(channel, upstream_model_name)
            )
            channel_request_error: ServiceException | None = None
            compat_attempts = [True] if explicit_compat else [False]
            if legacy_compat_retry:
                compat_attempts.append(True)

            for compat_mode in compat_attempts:
                try:
                    request_data_copy = dict(request_data)
                    request_data_copy["model"] = upstream_model_name
                    if upstream_api == "anthropic_messages" and not compat_mode:
                        ProxyService._guard_legacy_claude_tool_context(
                            channel,
                            requested_model,
                            request_data_copy,
                        )
                    if upstream_api == "anthropic_messages":
                        request_data_copy = ProxyService._prepare_anthropic_request_for_channel(
                            channel,
                            request_data_copy,
                            force_compat=compat_mode,
                        )
                    ProxyService._log_anthropic_runtime_debug(
                        "dispatch",
                        request_id,
                        requested_model,
                        request_data_copy,
                        channel=channel,
                        client_ip=client_ip,
                        upstream_model=upstream_model_name,
                        upstream_api=upstream_api,
                        force_compat=compat_mode,
                        request_headers=request_headers,
                    )

                    if is_stream:
                        if upstream_api == "responses":
                            return await ProxyService._stream_anthropic_via_responses_request(
                                db, user, api_key_record, channel, unified_model,
                                request_data_copy, request_id, requested_model, client_ip,
                                request_headers=request_headers,
                                conversation_shadow_info=conversation_shadow_info,
                            )
                        return await ProxyService._stream_anthropic_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                            force_compat=compat_mode,
                            conversation_shadow_info=conversation_shadow_info,
                        )
                    else:
                        if upstream_api == "responses":
                            return await ProxyService._non_stream_anthropic_via_responses_request(
                                db, user, api_key_record, channel, unified_model,
                                request_data_copy, request_id, requested_model, client_ip,
                                request_headers=request_headers,
                                conversation_shadow_info=conversation_shadow_info,
                            )
                        return await ProxyService._non_stream_anthropic_request(
                            db, user, api_key_record, channel, unified_model,
                            request_data_copy, request_id, requested_model, client_ip,
                            request_headers=request_headers,
                            force_compat=compat_mode,
                            conversation_shadow_info=conversation_shadow_info,
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
                    error_cache_info = ProxyService._extract_cache_info_from_error(e)
                    if error_cache_info:
                        request_cache_info = error_cache_info
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
                        channel.name, channel.id, upstream_model_name, e,
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
            cache_info=ProxyService._merge_conversation_shadow_into_cache_info(
                request_cache_info,
                conversation_shadow_info,
            ),
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
                        logger.warning(
                            "Anthropic upstream error request_id=%s channel=%s channel_id=%s status=%s body=%s request_snapshot=%s",
                            request_id,
                            channel.name,
                            channel.id,
                            response.status_code,
                            body.decode("utf-8", errors="replace")[:500],
                            json.dumps(
                                ProxyService._build_anthropic_request_debug_snapshot(request_data),
                                ensure_ascii=False,
                            ),
                        )
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
                                            if collected_usage.get("_first_stream_output_time") is None:
                                                collected_usage["_first_stream_output_time"] = time.time()
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
            cache_state: dict[str, Any] = {}

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="openai",
                    request_format="openai_chat",
                    model=model_name,
                    billing_callback=billing_callback,
                    cache_state=cache_state,
                ):
                    # 检测是否是缓存命中（wrap 内部会设置 cache_status）
                    if (
                        cache_state.get("first_stream_output_time") is None
                        and isinstance(sse_line, str)
                        and '"content":' in sse_line
                    ):
                        cache_state["first_stream_output_time"] = time.time()
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
                response_time_ms = ProxyService._resolve_stream_response_time_ms(start_time, cache_state)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        error_cache_info = cache_state.get("cache_info") or ProxyService._extract_cache_info_from_error(stream_error)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                            cache_info=error_cache_info,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                            actual_model=request_data.get("model"),
                            cache_info=cache_state.get("cache_info"),
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
                logger.warning(
                    "Anthropic upstream error request_id=%s channel=%s channel_id=%s status=%s body=%s request_snapshot=%s",
                    request_id,
                    channel.name,
                    channel.id,
                    resp.status_code,
                    resp.text[:500],
                    json.dumps(
                        ProxyService._build_anthropic_request_debug_snapshot(request_data),
                        ensure_ascii=False,
                    ),
                )
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
            request_format="openai_chat",
            requested_model=requested_model,
        )

        response_time_ms = ProxyService._calculate_elapsed_ms(start_time)

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
            actual_model=request_data.get("model"),
            cache_info=cache_info,
        )

        response_headers = {"X-Request-ID": request_id}

        return JSONResponse(
            content=response_body,
            headers=response_headers,
        )

    @staticmethod
    async def _stream_openai_via_anthropic_request(
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
        Stream an OpenAI client request through an Anthropic upstream channel.

        The client still receives OpenAI chat-completions SSE chunks, while the
        upstream request is sent to Claude Messages API.
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
        )
        anthropic_request = ProxyService._convert_openai_request_to_anthropic(request_data)
        anthropic_request["stream"] = True

        billing_input_tokens = 0
        billing_output_tokens = 0

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        async def upstream_call(collector, collected_usage):
            input_tokens = 0
            output_tokens = 0
            chunk_id = f"chatcmpl-{request_id}"
            created_at = int(time.time())
            message_id = chunk_id
            upstream_model = model_name
            stop_reason = None
            role_sent = False
            content_block_meta: dict[int, dict] = {}

            timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", url, json=anthropic_request, headers=headers,
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

                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        try:
                            chunk = json.loads(data_str)
                        except (json.JSONDecodeError, TypeError):
                            continue

                        chunk_type = str(chunk.get("type", "") or "")

                        if chunk_type == "message_start":
                            message = chunk.get("message") or {}
                            message_id = str(message.get("id") or chunk_id)
                            upstream_model = str(message.get("model") or upstream_model)
                            usage = message.get("usage") or {}
                            input_tokens = int(usage.get("input_tokens", 0) or 0)
                            collected_usage["prompt_tokens"] = input_tokens

                            if not role_sent:
                                role_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={"role": "assistant"},
                                )
                                yield f"data: {role_chunk}\n\n"
                                role_sent = True
                            continue

                        if chunk_type == "content_block_start":
                            block_index = int(chunk.get("index", 0) or 0)
                            content_block = chunk.get("content_block") or {}
                            block_type = str(content_block.get("type", "") or "")
                            content_block_meta[block_index] = {
                                "type": block_type,
                                "id": str(content_block.get("id") or f"call_{block_index}"),
                                "name": str(content_block.get("name", "") or "tool"),
                            }
                            if not role_sent:
                                role_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={"role": "assistant"},
                                )
                                yield f"data: {role_chunk}\n\n"
                                role_sent = True
                            if block_type == "tool_use":
                                tool_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={
                                        "tool_calls": [{
                                            "index": block_index,
                                            "id": content_block_meta[block_index]["id"],
                                            "type": "function",
                                            "function": {
                                                "name": content_block_meta[block_index]["name"],
                                                "arguments": "",
                                            },
                                        }],
                                    },
                                )
                                yield f"data: {tool_chunk}\n\n"
                            continue

                        if chunk_type == "content_block_delta":
                            block_index = int(chunk.get("index", 0) or 0)
                            delta = chunk.get("delta") or {}
                            meta = content_block_meta.get(block_index, {})

                            text_value = delta.get("text")
                            thinking_value = delta.get("thinking")
                            partial_json = delta.get("partial_json")

                            if not role_sent:
                                role_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={"role": "assistant"},
                                )
                                yield f"data: {role_chunk}\n\n"
                                role_sent = True

                            if text_value:
                                collector.add_chunk(str(text_value))
                                if collected_usage.get("_first_stream_output_time") is None:
                                    collected_usage["_first_stream_output_time"] = time.time()
                                text_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={"content": str(text_value)},
                                )
                                yield f"data: {text_chunk}\n\n"
                                continue

                            if thinking_value:
                                collector.add_chunk(str(thinking_value))
                                thinking_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={"reasoning_content": str(thinking_value)},
                                )
                                yield f"data: {thinking_chunk}\n\n"
                                continue

                            if partial_json is not None and meta.get("type") == "tool_use":
                                tool_delta_chunk = ProxyService._build_openai_stream_chunk(
                                    chunk_id=message_id,
                                    model_name=upstream_model,
                                    created_at=created_at,
                                    delta={
                                        "tool_calls": [{
                                            "index": block_index,
                                            "function": {
                                                "arguments": str(partial_json),
                                            },
                                        }],
                                    },
                                )
                                yield f"data: {tool_delta_chunk}\n\n"
                            continue

                        if chunk_type == "message_delta":
                            delta = chunk.get("delta") or {}
                            usage = chunk.get("usage") or {}
                            stop_reason = delta.get("stop_reason", stop_reason)
                            if usage.get("output_tokens") is not None:
                                output_tokens = int(usage.get("output_tokens") or 0)
                            if usage.get("input_tokens") is not None:
                                input_tokens = int(usage.get("input_tokens") or 0)
                            collected_usage["prompt_tokens"] = input_tokens
                            collected_usage["completion_tokens"] = output_tokens
                            continue

                        if chunk_type == "message_stop":
                            final_chunk = ProxyService._build_openai_stream_chunk(
                                chunk_id=message_id,
                                model_name=upstream_model,
                                created_at=created_at,
                                delta={},
                                finish_reason=ProxyService._convert_anthropic_stop_reason_to_openai(
                                    stop_reason,
                                    has_tool_calls=any(
                                        meta.get("type") == "tool_use"
                                        for meta in content_block_meta.values()
                                    ),
                                ),
                            )
                            yield f"data: {final_chunk}\n\n"
                            usage_chunk = ProxyService._build_openai_stream_chunk(
                                chunk_id=message_id,
                                model_name=upstream_model,
                                created_at=created_at,
                                usage={
                                    "prompt_tokens": input_tokens,
                                    "completion_tokens": output_tokens,
                                    "total_tokens": input_tokens + output_tokens,
                                },
                            )
                            yield f"data: {usage_chunk}\n\n"
                            yield "data: [DONE]\n\n"
                            break

            billing_callback(input_tokens, output_tokens, False)

        async def event_generator():
            stream_error = None
            cache_state: dict[str, Any] = {}

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=anthropic_request,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="openai",
                    request_format="anthropic_messages",
                    model=model_name,
                    billing_callback=billing_callback,
                    cache_state=cache_state,
                ):
                    if (
                        cache_state.get("first_stream_output_time") is None
                        and isinstance(sse_line, str)
                        and '"content":' in sse_line
                    ):
                        cache_state["first_stream_output_time"] = time.time()
                    yield sse_line

            except Exception as e:
                stream_error = e
                mapped_request_error = ProxyService._map_upstream_request_error(e)
                error_message = mapped_request_error.detail if mapped_request_error else f"Stream error: {str(e)}"
                logger.error("OpenAI->Anthropic stream error on channel %s: %s", channel.name, e)
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
                response_time_ms = ProxyService._resolve_stream_response_time_ms(start_time, cache_state)
                try:
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        error_cache_info = cache_state.get("cache_info") or ProxyService._extract_cache_info_from_error(stream_error)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                            cache_info=error_cache_info,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                            actual_model=request_data.get("model"),
                            cache_info=cache_state.get("cache_info"),
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
    async def _non_stream_openai_via_anthropic_request(
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
        Send an OpenAI chat-completions request through an Anthropic upstream.
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
        )
        anthropic_request = ProxyService._convert_openai_request_to_anthropic(request_data)
        anthropic_request["stream"] = False

        async def upstream_call():
            timeout = httpx.Timeout(
                _UPSTREAM_TIMEOUT,
                connect=_UPSTREAM_CONNECT_TIMEOUT,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=anthropic_request, headers=headers)

            if resp.status_code != 200:
                raise Exception(
                    f"Upstream returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            content_type = resp.headers.get("content-type", "")
            if (
                "text/event-stream" in content_type
                or resp.text.lstrip().startswith("event: ")
                or resp.text.lstrip().startswith("data: ")
            ):
                anthropic_response, input_tokens, output_tokens = (
                    ProxyService._parse_sse_to_non_stream_anthropic(resp.text)
                )
            else:
                anthropic_response = resp.json()
                usage = anthropic_response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

            openai_response = ProxyService._convert_anthropic_response_to_openai(
                anthropic_response
            )
            return {
                "response": openai_response,
                "model": request_data.get("model"),
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                },
            }

        cache_response, cache_info = await CacheMiddleware.wrap_request(
            request_body=anthropic_request,
            headers=request_headers or {},
            user=user,
            db=db,
            upstream_call=upstream_call,
            unified_model=unified_model,
            request_format="anthropic_messages",
            requested_model=requested_model,
        )

        response_time_ms = ProxyService._calculate_elapsed_ms(start_time)
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)

        billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
            cache_info=cache_info,
            user=user,
            actual_tokens={
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
            }
        )

        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
            actual_model=request_data.get("model"),
            cache_info=cache_info,
        )

        return JSONResponse(
            content=response_body,
            headers={"X-Request-ID": request_id},
        )

    @staticmethod
    async def _stream_anthropic_via_responses_request(
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
        conversation_shadow_info: Optional[dict[str, Any]] = None,
    ) -> StreamingResponse:
        """Stream an Anthropic client request through an OpenAI Responses upstream."""
        start_time = time.time()
        responses_request = ProxyService._convert_anthropic_request_to_responses(
            request_data,
            requested_model=requested_model,
        )
        responses_request["stream"] = True
        upstream_event_sequence: list[str] = []
        upstream_event_counts: dict[str, int] = {}
        client_event_sequence: list[str] = []
        client_event_counts: dict[str, int] = {}
        stream_debug_extra: dict[str, Any] = {
            "bridge": "anthropic_via_responses",
            "completed": False,
            "stop_reason": None,
            "saw_tool_use": False,
        }

        billing_input_tokens = 0
        billing_output_tokens = 0

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        def record_upstream_event(event_name: str, detail: Optional[Any] = None) -> None:
            ProxyService._record_stream_debug_event(
                upstream_event_sequence,
                upstream_event_counts,
                event_name,
                detail,
            )

        def build_client_event(
            event_name: str,
            payload: dict[str, Any],
            *,
            detail: Optional[Any] = None,
        ) -> str:
            ProxyService._record_stream_debug_event(
                client_event_sequence,
                client_event_counts,
                event_name,
                detail,
            )
            return ProxyService._build_anthropic_sse_event(event_name, payload)

        async def upstream_call(collector, collected_usage):
            input_tokens = 0
            output_tokens = 0
            completed = False
            saw_error = False
            error_message = ""
            message_started = False
            message_id = f"msg_{uuid.uuid4().hex[:24]}"
            text_block_open = False
            text_block_index = -1
            next_block_index = 0
            saw_text_delta = False
            saw_tool_use = False
            seen_reasoning_ids: set[str] = set()
            tool_block_states: dict[str, dict[str, Any]] = {}
            tool_call_aliases: dict[str, str] = {}
            final_response: dict[str, Any] | None = None

            def ensure_message_start(response_obj: Optional[dict[str, Any]] = None) -> list[str]:
                nonlocal message_started, message_id, input_tokens
                if message_started:
                    return []
                response_data = response_obj or {}
                message_id = str(response_data.get("id") or message_id)
                usage = response_data.get("usage") or {}
                if usage.get("input_tokens") is not None:
                    input_tokens = int(usage.get("input_tokens") or 0)
                message_started = True
                return [build_client_event(
                    "message_start",
                    {
                        "type": "message_start",
                        "message": {
                            "id": message_id,
                            "type": "message",
                            "role": "assistant",
                            "content": [],
                            "model": requested_model,
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": {
                                "input_tokens": input_tokens,
                                "output_tokens": 0,
                            },
                        },
                    },
                )]

            def open_text_block() -> list[str]:
                nonlocal text_block_open, text_block_index, next_block_index
                if text_block_open:
                    return []
                text_block_index = next_block_index
                next_block_index += 1
                text_block_open = True
                return [build_client_event(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": text_block_index,
                        "content_block": {
                            "type": "text",
                            "text": "",
                        },
                    },
                    detail="text",
                )]

            def close_text_block() -> list[str]:
                nonlocal text_block_open
                if not text_block_open:
                    return []
                text_block_open = False
                return [build_client_event(
                    "content_block_stop",
                    {
                        "type": "content_block_stop",
                        "index": text_block_index,
                    },
                    detail="text",
                )]

            def emit_reasoning_block(item: dict[str, Any]) -> list[str]:
                nonlocal next_block_index
                item_id = str(item.get("id") or "")
                if item_id:
                    if item_id in seen_reasoning_ids:
                        return []
                    seen_reasoning_ids.add(item_id)
                thinking_value = ProxyService._extract_responses_reasoning_text(
                    item.get("summary") or item.get("content")
                )
                if not thinking_value:
                    return []
                collector.add_chunk(thinking_value)
                block_index = next_block_index
                next_block_index += 1
                return [
                    build_client_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": block_index,
                            "content_block": {"type": "thinking"},
                        },
                        detail="thinking",
                    ),
                    build_client_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": block_index,
                            "delta": {
                                "type": "thinking_delta",
                                "thinking": thinking_value,
                            },
                        },
                        detail="thinking_delta",
                    ),
                    build_client_event(
                        "content_block_stop",
                        {
                            "type": "content_block_stop",
                            "index": block_index,
                        },
                        detail="thinking",
                    ),
                ]

            def _resolve_tool_call_id(item: dict[str, Any]) -> str:
                raw_ids = [
                    str(item.get("call_id") or ""),
                    str(item.get("item_id") or ""),
                    str(item.get("id") or ""),
                ]
                for raw_id in raw_ids:
                    if raw_id and raw_id in tool_call_aliases:
                        return tool_call_aliases[raw_id]

                canonical_id = next((raw_id for raw_id in raw_ids if raw_id), "")
                if not canonical_id:
                    canonical_id = f"toolu_{uuid.uuid4().hex[:24]}"

                for raw_id in raw_ids:
                    if raw_id:
                        tool_call_aliases[raw_id] = canonical_id
                return canonical_id

            def ensure_tool_use_block_started(item: dict[str, Any]) -> tuple[str, list[str]]:
                nonlocal next_block_index, saw_tool_use
                call_id = _resolve_tool_call_id(item)
                state = tool_block_states.get(call_id)
                if state is None:
                    state = {
                        "id": call_id,
                        "name": str(item.get("name", "") or "tool"),
                        "index": next_block_index,
                        "started": False,
                        "closed": False,
                        "arguments_text": "",
                    }
                    tool_block_states[call_id] = state
                    next_block_index += 1
                elif item.get("name"):
                    state["name"] = str(item.get("name") or state["name"])

                saw_tool_use = True
                if state["started"]:
                    return call_id, []

                state["started"] = True
                return call_id, [
                    build_client_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": state["index"],
                            "content_block": {
                                "type": "tool_use",
                                "id": call_id,
                                "name": state["name"],
                                "input": {},
                            },
                        },
                        detail=f"tool_use:{state['name']}",
                    )
                ]

            def emit_tool_argument_delta(item: dict[str, Any], delta_text: Any) -> list[str]:
                call_id, events = ensure_tool_use_block_started(item)
                state = tool_block_states[call_id]
                serialized_delta = ProxyService._stringify_tool_arguments_json(delta_text)
                if serialized_delta == "":
                    return events
                state["arguments_text"] = f"{state['arguments_text']}{serialized_delta}"
                events.append(
                    build_client_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": state["index"],
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": serialized_delta,
                            },
                        },
                        detail="input_json_delta",
                    )
                )
                return events

            def close_tool_use_block(item: dict[str, Any], final_arguments: Any = None) -> list[str]:
                call_id, events = ensure_tool_use_block_started(item)
                state = tool_block_states[call_id]
                if state["closed"]:
                    return events

                final_text = ProxyService._stringify_tool_arguments_json(final_arguments)
                current_text = str(state.get("arguments_text", "") or "")
                if final_text:
                    missing_text = ""
                    if not current_text:
                        missing_text = final_text
                    elif final_text.startswith(current_text):
                        missing_text = final_text[len(current_text):]
                    elif final_text != current_text:
                        missing_text = ""

                    if missing_text:
                        state["arguments_text"] = f"{current_text}{missing_text}"
                        events.append(
                            build_client_event(
                                "content_block_delta",
                                {
                                    "type": "content_block_delta",
                                    "index": state["index"],
                                    "delta": {
                                        "type": "input_json_delta",
                                        "partial_json": missing_text,
                                    },
                                },
                                detail="input_json_delta",
                            )
                        )

                state["closed"] = True
                events.append(
                    build_client_event(
                        "content_block_stop",
                        {
                            "type": "content_block_stop",
                            "index": state["index"],
                        },
                        detail="tool_use",
                    )
                )
                return events

            async for payload in ProxyService._iter_responses_upstream_payloads(
                channel,
                responses_request,
                requested_model,
                request_headers=request_headers,
            ):
                payload_type = str(payload.get("type", "") or "")
                payload_detail = None
                if payload_type in {"response.output_item.added", "response.output_item.done"}:
                    payload_detail = str((payload.get("item") or {}).get("type", "") or "")
                elif payload_type in {"response.function_call_arguments.delta", "response.function_call_arguments.done"}:
                    payload_detail = payload.get("item_id") or payload.get("call_id")
                record_upstream_event(payload_type, payload_detail)
                if payload_type in {"response.created", "response.in_progress"}:
                    response_obj = payload.get("response") or {}
                    for sse_line in ensure_message_start(response_obj):
                        yield sse_line
                    continue

                if payload_type == "response.output_text.delta":
                    for sse_line in ensure_message_start():
                        yield sse_line
                    for sse_line in open_text_block():
                        yield sse_line
                    delta_value = str(payload.get("delta", "") or "")
                    if delta_value:
                        saw_text_delta = True
                        collector.add_chunk(delta_value)
                        if collected_usage.get("_first_stream_output_time") is None:
                            collected_usage["_first_stream_output_time"] = time.time()
                        yield build_client_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": text_block_index,
                                "delta": {
                                    "type": "text_delta",
                                    "text": delta_value,
                                },
                            },
                            detail="text_delta",
                        )
                    continue

                if payload_type == "response.output_item.added":
                    item = payload.get("item") or {}
                    if str(item.get("type", "") or "") == "function_call":
                        for sse_line in ensure_message_start():
                            yield sse_line
                        for sse_line in close_text_block():
                            yield sse_line
                        _, events = ensure_tool_use_block_started(item)
                        for sse_line in events:
                            yield sse_line
                    continue

                if payload_type == "response.function_call_arguments.delta":
                    call_item = {
                        "call_id": payload.get("call_id"),
                        "item_id": payload.get("item_id"),
                        "id": payload.get("id"),
                        "name": payload.get("name"),
                    }
                    for sse_line in ensure_message_start():
                        yield sse_line
                    for sse_line in close_text_block():
                        yield sse_line
                    for sse_line in emit_tool_argument_delta(call_item, payload.get("delta")):
                        yield sse_line
                    continue

                if payload_type == "response.function_call_arguments.done":
                    call_item = {
                        "call_id": payload.get("call_id"),
                        "item_id": payload.get("item_id"),
                        "id": payload.get("id"),
                        "name": payload.get("name"),
                    }
                    for sse_line in ensure_message_start():
                        yield sse_line
                    for sse_line in close_text_block():
                        yield sse_line
                    for sse_line in close_tool_use_block(call_item, payload.get("arguments")):
                        yield sse_line
                    continue

                if payload_type == "response.output_item.done":
                    item = payload.get("item") or {}
                    item_type = str(item.get("type", "") or "")
                    if item_type == "reasoning":
                        for sse_line in ensure_message_start():
                            yield sse_line
                        for sse_line in close_text_block():
                            yield sse_line
                        for sse_line in emit_reasoning_block(item):
                            yield sse_line
                        continue
                    if item_type == "function_call":
                        for sse_line in ensure_message_start():
                            yield sse_line
                        for sse_line in close_text_block():
                            yield sse_line
                        for sse_line in close_tool_use_block(item, item.get("arguments")):
                            yield sse_line
                        continue

                if payload_type == "response.completed":
                    final_response = payload.get("response") or {}
                    for sse_line in ensure_message_start(final_response):
                        yield sse_line

                    input_tokens, output_tokens = ProxyService._extract_responses_usage(payload)
                    collected_usage["prompt_tokens"] = input_tokens
                    collected_usage["completion_tokens"] = output_tokens

                    for sse_line in close_text_block():
                        yield sse_line

                    final_output = final_response.get("output") or []
                    if isinstance(final_output, list):
                        if not saw_text_delta:
                            text_content = []
                            for item in final_output:
                                if not isinstance(item, dict) or str(item.get("type", "") or "") != "message":
                                    continue
                                for part in item.get("content") or []:
                                    if isinstance(part, dict) and str(part.get("type", "") or "") in {
                                        "output_text", "text", "input_text",
                                    }:
                                        text_value = str(part.get("text", "") or "")
                                        if text_value:
                                            text_content.append(text_value)
                            if text_content:
                                for sse_line in open_text_block():
                                    yield sse_line
                                joined_text = "".join(text_content)
                                collector.add_chunk(joined_text)
                                yield build_client_event(
                                    "content_block_delta",
                                    {
                                        "type": "content_block_delta",
                                        "index": text_block_index,
                                        "delta": {
                                            "type": "text_delta",
                                            "text": joined_text,
                                        },
                                    },
                                    detail="text_delta",
                                )
                                for sse_line in close_text_block():
                                    yield sse_line

                        for item in final_output:
                            if not isinstance(item, dict):
                                continue
                            item_type = str(item.get("type", "") or "")
                            if item_type == "reasoning":
                                for sse_line in emit_reasoning_block(item):
                                    yield sse_line
                            elif item_type == "function_call":
                                for sse_line in close_tool_use_block(item, item.get("arguments")):
                                    yield sse_line

                    collector.add_chunk(
                        "",
                        "tool_use" if saw_tool_use else "end_turn",
                    )
                    stream_debug_extra["completed"] = True
                    stream_debug_extra["stop_reason"] = "tool_use" if saw_tool_use else "end_turn"
                    stream_debug_extra["saw_tool_use"] = saw_tool_use
                    yield build_client_event(
                        "message_delta",
                        {
                            "type": "message_delta",
                            "delta": {
                                "stop_reason": "tool_use" if saw_tool_use else "end_turn",
                                "stop_sequence": None,
                            },
                            "usage": {
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                            },
                        },
                        detail="tool_use" if saw_tool_use else "end_turn",
                    )
                    yield build_client_event(
                        "message_stop",
                        {"type": "message_stop"},
                        detail="final",
                    )
                    completed = True
                    break

                if payload_type == "error":
                    saw_error = True
                    error_message = (
                        payload.get("error", {}).get("message")
                        or "Upstream responses error"
                    )

            if not completed:
                if saw_error:
                    raise Exception(error_message or "Upstream responses error")
                raise Exception("stream closed before response.completed")

            billing_callback(input_tokens, output_tokens, False)

        async def event_generator():
            stream_error = None
            cache_state: dict[str, Any] = {}

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=responses_request,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="anthropic",
                    request_format="responses",
                    model=requested_model,
                    billing_callback=billing_callback,
                    cache_state=cache_state,
                ):
                    if (
                        cache_state.get("first_stream_output_time") is None
                        and isinstance(sse_line, str)
                        and '"type":"content_block_delta"' in sse_line
                    ):
                        cache_state["first_stream_output_time"] = time.time()
                    yield sse_line
            except Exception as exc:
                stream_error = exc
                mapped_request_error = ProxyService._map_upstream_request_error(exc)
                error_message = mapped_request_error.detail if mapped_request_error else str(exc)
                logger.error("Anthropic->Responses stream error on channel %s: %s", channel.name, exc)
                yield build_client_event(
                    "error",
                    {
                        "type": "error",
                        "error": {
                            "type": "proxy_error",
                            "message": error_message,
                        },
                    },
                    detail="proxy_error",
                )
            finally:
                response_time_ms = ProxyService._resolve_stream_response_time_ms(start_time, cache_state)
                try:
                    merged_cache_info = ProxyService._merge_conversation_shadow_into_cache_info(
                        cache_state.get("cache_info"),
                        conversation_shadow_info,
                    )
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        error_cache_info = merged_cache_info or ProxyService._extract_cache_info_from_error(stream_error)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                            cache_info=error_cache_info,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                            actual_model=request_data.get("model"),
                            cache_info=merged_cache_info,
                            conversation_state_info=conversation_shadow_info,
                        )
                except Exception as accounting_err:
                    logger.error("Post-stream accounting error: %s", accounting_err)
                ProxyService._log_anthropic_stream_debug(
                    "anthropic_via_responses",
                    request_id,
                    requested_model,
                    actual_model=request_data.get("model"),
                    channel=channel,
                    client_ip=client_ip,
                    status="error" if stream_error else "success",
                    event_sequence=client_event_sequence,
                    event_counts=client_event_counts,
                    upstream_sequence=upstream_event_sequence,
                    upstream_counts=upstream_event_counts,
                    extra=stream_debug_extra,
                )

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
    async def _non_stream_anthropic_via_responses_request(
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
        conversation_shadow_info: Optional[dict[str, Any]] = None,
    ) -> JSONResponse:
        """Send an Anthropic request through an OpenAI Responses upstream."""
        start_time = time.time()
        base_url = channel.base_url.rstrip("/")
        url = f"{base_url}/responses"
        headers = ProxyService._build_headers(channel, "openai", request_headers=request_headers)
        responses_request = ProxyService._convert_anthropic_request_to_responses(
            request_data,
            requested_model=requested_model,
        )
        responses_request["stream"] = False

        async def upstream_call():
            timeout = httpx.Timeout(
                _UPSTREAM_TIMEOUT,
                connect=_UPSTREAM_CONNECT_TIMEOUT,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=responses_request, headers=headers)

            if resp.status_code != 200:
                raise Exception(
                    f"Upstream returned HTTP {resp.status_code}: "
                    f"{resp.text[:500]}"
                )

            response_body, input_tokens, output_tokens = ProxyService._parse_non_stream_responses_body(
                resp.text
            )
            response_body = ProxyService._rewrite_response_model(response_body, requested_model)
            anthropic_response = ProxyService._convert_responses_response_to_anthropic(
                response_body
            )
            return {
                "response": anthropic_response,
                "model": request_data.get("model"),
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                },
            }

        cache_response, cache_info = await CacheMiddleware.wrap_request(
            request_body=responses_request,
            headers=request_headers or {},
            user=user,
            db=db,
            upstream_call=upstream_call,
            unified_model=unified_model,
            request_format="responses",
            requested_model=requested_model,
        )

        response_time_ms = ProxyService._calculate_elapsed_ms(start_time)
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)
        merged_cache_info = ProxyService._merge_conversation_shadow_into_cache_info(
            cache_info,
            conversation_shadow_info,
        )

        billing_input_tokens, billing_output_tokens = CacheMiddleware.get_billing_tokens(
            cache_info=merged_cache_info,
            user=user,
            actual_tokens={
                "input_tokens": actual_input_tokens,
                "output_tokens": actual_output_tokens,
            },
        )

        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
            actual_model=request_data.get("model"),
            cache_info=merged_cache_info,
            conversation_state_info=conversation_shadow_info,
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
        request_headers: Optional[dict[str, str]] = None,
        force_compat: bool = False,
        conversation_shadow_info: Optional[dict[str, Any]] = None,
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
        original_request_data = copy.deepcopy(request_data)
        stream_event_sequence: list[str] = []
        stream_event_counts: dict[str, int] = {}
        stream_debug_extra: dict[str, Any] = {
            "bridge": "anthropic_passthrough",
            "completed": False,
            "stop_reason": None,
        }

        billing_input_tokens = 0
        billing_output_tokens = 0
        prompt_cache_state: dict[str, Any] = {}
        conversation_runtime_info = copy.deepcopy(conversation_shadow_info) if conversation_shadow_info else None
        if conversation_runtime_info:
            conversation_runtime_info["upstream_session_mode"] = UpstreamSessionStrategyService.get_session_mode(channel)
        active_compacted_request = (
            copy.deepcopy(conversation_shadow_info.get("_conversation_compacted_request"))
            if CompressionGuardService.should_apply_stream_compaction(conversation_shadow_info)
            else None
        )

        def billing_callback(input_tok: int, output_tok: int, is_hit: bool):
            nonlocal billing_input_tokens, billing_output_tokens
            billing_input_tokens = input_tok
            billing_output_tokens = output_tok

        async def upstream_call(collector, collected_usage):
            """上游流式调用，同时通过 collector 收集 chunks"""
            timeout = httpx.Timeout(_UPSTREAM_TIMEOUT, connect=_UPSTREAM_CONNECT_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                compression_fallback_reason: Optional[str] = None
                request_attempts: list[dict[str, Any]] = []
                if active_compacted_request:
                    compacted_request = copy.deepcopy(active_compacted_request)
                    compacted_request["model"] = request_data.get("model", requested_model)
                    compacted_request["stream"] = True
                    request_attempts.append({
                        "label": "compacted",
                        "request_data": compacted_request,
                        "is_compacted": True,
                    })
                request_attempts.append({
                    "label": "full",
                    "request_data": copy.deepcopy(original_request_data),
                    "is_compacted": False,
                })

                for request_attempt_index, request_attempt in enumerate(request_attempts):
                    prompt_cache_variants = AnthropicPromptCacheService.build_request_variants(
                        db,
                        request_attempt["request_data"],
                        request_headers=request_headers,
                    )
                    prompt_fallback_reason: Optional[str] = None
                    should_retry_full = False

                    for variant_index, variant in enumerate(prompt_cache_variants):
                        input_tokens = 0
                        output_tokens = 0
                        usage_state: dict[str, Any] = {}
                        current_headers = dict(headers)
                        current_headers.update(variant.get("header_overrides") or {})

                        async with client.stream(
                            "POST",
                            url,
                            json=variant["request_data"],
                            headers=current_headers,
                        ) as response:
                            if response.status_code != 200:
                                body = await response.aread()
                                body_text = body.decode("utf-8", errors="replace")[:500]
                                if AnthropicPromptCacheService.should_retry_with_fallback(
                                    status_code=response.status_code,
                                    response_text=body_text,
                                    attempt_meta=variant["meta"],
                                    has_more_variants=variant_index < len(prompt_cache_variants) - 1,
                                ):
                                    prompt_fallback_reason = f"HTTP {response.status_code}: {body_text}"
                                    logger.warning(
                                        "Anthropic prompt cache fallback request_id=%s channel=%s channel_id=%s "
                                        "variant=%s reason=%s",
                                        request_id,
                                        channel.name,
                                        channel.id,
                                        variant["meta"].get("label"),
                                        prompt_fallback_reason,
                                    )
                                    continue

                                if request_attempt["is_compacted"] and CompressionGuardService.can_retry_stream_before_first_byte():
                                    compression_fallback_reason = (
                                        f"compressed_request HTTP {response.status_code}: {body_text}"
                                    )
                                    should_retry_full = True
                                    break

                                raise Exception(
                                    f"Upstream returned HTTP {response.status_code}: {body_text}"
                                )

                            prompt_cache_state["attempt_meta"] = copy.deepcopy(variant["meta"])
                            prompt_cache_state["fallback_triggered"] = bool(variant_index > 0)
                            prompt_cache_state["fallback_reason"] = prompt_fallback_reason

                            if conversation_runtime_info:
                                if request_attempt["is_compacted"]:
                                    conversation_runtime_info["compression_mode"] = "stream_active"
                                    conversation_runtime_info["compression_status"] = "ACTIVE_APPLIED"
                                    conversation_runtime_info["compression_fallback_reason"] = None
                                elif active_compacted_request and request_attempt_index > 0:
                                    conversation_runtime_info["compression_mode"] = "stream_active"
                                    conversation_runtime_info["compression_status"] = "ACTIVE_FALLBACK_FULL"
                                    conversation_runtime_info["compression_fallback_reason"] = compression_fallback_reason
                                    conversation_runtime_info["_conversation_mark_cooldown"] = True
                                commit_payload = conversation_runtime_info.get("_conversation_shadow_commit") or {}
                                commit_payload["compression_mode"] = conversation_runtime_info.get("compression_mode")
                                conversation_runtime_info["_conversation_shadow_commit"] = commit_payload

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
                                        chunk_detail = None
                                        if chunk_type == "content_block_start":
                                            chunk_detail = str(
                                                (chunk.get("content_block") or {}).get("type", "") or ""
                                            )
                                        elif chunk_type == "content_block_delta":
                                            delta = chunk.get("delta") or {}
                                            chunk_detail = str(
                                                delta.get("type")
                                                or ("text_delta" if delta.get("text") else "")
                                                or ("thinking_delta" if delta.get("thinking") else "")
                                            )
                                        elif chunk_type == "message_delta":
                                            chunk_detail = str(
                                                (chunk.get("delta") or {}).get("stop_reason", "") or ""
                                            )
                                        ProxyService._record_stream_debug_event(
                                            stream_event_sequence,
                                            stream_event_counts,
                                            str(chunk_type or current_event or "unknown"),
                                            chunk_detail,
                                        )

                                        if chunk_type == "message_start":
                                            msg = chunk.get("message", {})
                                            usage = msg.get("usage", {})
                                            ProxyService._merge_anthropic_usage_snapshot(
                                                usage_state,
                                                usage,
                                            )
                                            input_tokens = int(usage.get("input_tokens", 0) or 0)

                                        elif chunk_type == "message_delta":
                                            usage = chunk.get("usage", {})
                                            ProxyService._merge_anthropic_usage_snapshot(
                                                usage_state,
                                                usage,
                                            )
                                            output_tokens = int(
                                                usage.get("output_tokens", output_tokens) or output_tokens
                                            )
                                            if usage.get("input_tokens") is not None:
                                                input_tokens = int(usage.get("input_tokens") or 0)
                                            collected_usage["prompt_tokens"] = input_tokens
                                            collected_usage["completion_tokens"] = output_tokens
                                            stream_debug_extra["stop_reason"] = (
                                                (chunk.get("delta") or {}).get("stop_reason")
                                                or stream_debug_extra.get("stop_reason")
                                            )

                                        elif chunk_type == "content_block_delta":
                                            delta = chunk.get("delta", {})
                                            text = delta.get("text", "")
                                            thinking = delta.get("thinking", "")
                                            if text:
                                                collector.add_chunk(text)
                                                if collected_usage.get("_first_stream_output_time") is None:
                                                    collected_usage["_first_stream_output_time"] = time.time()
                                            if thinking:
                                                collector.add_chunk(thinking)

                                        elif chunk_type == "message_stop":
                                            collector.add_chunk("", "end_turn")
                                            stream_debug_extra["completed"] = True

                                    except (json.JSONDecodeError, TypeError):
                                        pass

                                    yield f"data: {data_str}\n\n"

                                    if current_event == "message_stop":
                                        break
                                else:
                                    yield f"{line}\n"

                            usage_summary = AnthropicPromptCacheService.extract_usage_summary(
                                usage_state,
                                attempt_meta=variant["meta"],
                            )
                            prompt_cache_state["usage_summary"] = usage_summary
                            billing_callback(
                                ProxyService._resolve_prompt_cache_billing_input_tokens(
                                    db,
                                    usage_summary,
                                ),
                                int(usage_summary.get("output_tokens", 0) or 0),
                                False,
                            )
                            return

                    if should_retry_full:
                        logger.warning(
                            "Conversation compaction stream fallback to full request_id=%s channel=%s channel_id=%s reason=%s",
                            request_id,
                            channel.name,
                            channel.id,
                            compression_fallback_reason,
                        )
                        continue

                raise Exception(compression_fallback_reason or "Anthropic prompt cache request failed")

        async def event_generator():
            stream_error = None
            cache_state: dict[str, Any] = {}

            try:
                async for sse_line in StreamCacheMiddleware.wrap_stream_request(
                    request_body=original_request_data,
                    headers=request_headers or {},
                    user=user,
                    db=db,
                    upstream_call=upstream_call,
                    unified_model=unified_model,
                    protocol="anthropic",
                    request_format="anthropic_messages",
                    model=model_name,
                    billing_callback=billing_callback,
                    cache_state=cache_state,
                ):
                    yield sse_line

            except Exception as e:
                stream_error = e
                mapped_request_error = ProxyService._map_upstream_request_error(e)
                error_message = mapped_request_error.detail if mapped_request_error else f"Stream error: {str(e)}"
                logger.error("Anthropic stream error on channel %s: %s", channel.name, e)
                ProxyService._record_stream_debug_event(
                    stream_event_sequence,
                    stream_event_counts,
                    "error",
                    "proxy_error",
                )
                error_payload = json.dumps({
                    "type": "error",
                    "error": {
                        "type": "proxy_error",
                        "message": error_message,
                    },
                })
                yield f"event: error\ndata: {error_payload}\n\n"
            finally:
                response_time_ms = ProxyService._resolve_stream_response_time_ms(start_time, cache_state)
                try:
                    merged_cache_info = ProxyService._merge_prompt_cache_state_into_cache_info(
                        cache_state.get("cache_info"),
                        prompt_cache_state,
                    )
                    merged_cache_info = ProxyService._merge_conversation_shadow_into_cache_info(
                        merged_cache_info,
                        conversation_runtime_info or conversation_shadow_info,
                    )
                    if stream_error:
                        mapped_request_error = ProxyService._map_upstream_request_error(stream_error)
                        if not mapped_request_error:
                            ProxyService._record_channel_failure(db, channel)
                        error_cache_info = merged_cache_info or ProxyService._extract_cache_info_from_error(stream_error)
                        ProxyService._log_failed_request(
                            db, user, api_key_record, request_id, requested_model,
                            client_ip, True,
                            mapped_request_error.detail if mapped_request_error else str(stream_error),
                            channel=channel,
                            response_time_ms=response_time_ms,
                            cache_info=error_cache_info,
                        )
                    else:
                        ProxyService._record_success(db, channel)
                        ProxyService._deduct_balance_and_log(
                            db, user, api_key_record, unified_model, request_id,
                            requested_model, billing_input_tokens, billing_output_tokens, channel,
                            client_ip, response_time_ms, is_stream=True,
                            actual_model=request_data.get("model"),
                            cache_info=merged_cache_info,
                            conversation_state_info=conversation_runtime_info or conversation_shadow_info,
                        )
                except Exception as accounting_err:
                    logger.error("Post-stream accounting error: %s", accounting_err)
                ProxyService._log_anthropic_stream_debug(
                    "anthropic_passthrough",
                    request_id,
                    requested_model,
                    actual_model=request_data.get("model"),
                    channel=channel,
                    client_ip=client_ip,
                    status="error" if stream_error else "success",
                    event_sequence=stream_event_sequence,
                    event_counts=stream_event_counts,
                    extra=stream_debug_extra,
                )

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
        conversation_shadow_info: Optional[dict[str, Any]] = None,
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
        original_request_data = copy.deepcopy(request_data)
        prompt_cache_state: dict[str, Any] = {}
        conversation_runtime_info = copy.deepcopy(conversation_shadow_info) if conversation_shadow_info else None
        if conversation_runtime_info:
            conversation_runtime_info["upstream_session_mode"] = UpstreamSessionStrategyService.get_session_mode(channel)
        active_compacted_request = (
            copy.deepcopy(conversation_shadow_info.get("_conversation_compacted_request"))
            if CompressionGuardService.should_apply_non_stream_compaction(
                conversation_shadow_info,
                is_stream=False,
            )
            else None
        )

        # Define upstream call function for passthrough middleware
        async def upstream_call():
            timeout = httpx.Timeout(
                _UPSTREAM_TIMEOUT,
                connect=_UPSTREAM_CONNECT_TIMEOUT,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                compression_fallback_reason: Optional[str] = None
                request_attempts: list[dict[str, Any]] = []
                if active_compacted_request:
                    compacted_request = copy.deepcopy(active_compacted_request)
                    compacted_request["model"] = request_data.get("model", requested_model)
                    compacted_request["stream"] = False
                    request_attempts.append({
                        "label": "compacted",
                        "request_data": compacted_request,
                        "is_compacted": True,
                    })
                request_attempts.append({
                    "label": "full",
                    "request_data": copy.deepcopy(original_request_data),
                    "is_compacted": False,
                })

                for request_attempt_index, request_attempt in enumerate(request_attempts):
                    request_payload = request_attempt["request_data"]
                    prompt_cache_variants = AnthropicPromptCacheService.build_request_variants(
                        db,
                        request_payload,
                        request_headers=request_headers,
                    )
                    prompt_fallback_reason: Optional[str] = None
                    should_retry_full = False

                    for variant_index, variant in enumerate(prompt_cache_variants):
                        current_headers = dict(headers)
                        current_headers.update(variant.get("header_overrides") or {})
                        resp = await client.post(
                            url,
                            json=variant["request_data"],
                            headers=current_headers,
                        )

                        if resp.status_code != 200:
                            body_text = resp.text[:500]
                            if AnthropicPromptCacheService.should_retry_with_fallback(
                                status_code=resp.status_code,
                                response_text=body_text,
                                attempt_meta=variant["meta"],
                                has_more_variants=variant_index < len(prompt_cache_variants) - 1,
                            ):
                                prompt_fallback_reason = f"HTTP {resp.status_code}: {body_text}"
                                logger.warning(
                                    "Anthropic prompt cache fallback request_id=%s channel=%s channel_id=%s "
                                    "variant=%s reason=%s",
                                    request_id,
                                    channel.name,
                                    channel.id,
                                    variant["meta"].get("label"),
                                    prompt_fallback_reason,
                                )
                                continue

                            if request_attempt["is_compacted"] and CompressionGuardService.should_fallback_to_full_request(
                                status_code=resp.status_code,
                                response_text=body_text,
                            ):
                                compression_fallback_reason = (
                                    f"compressed_request HTTP {resp.status_code}: {body_text}"
                                )
                                should_retry_full = True
                                break

                            raise Exception(
                                f"Upstream returned HTTP {resp.status_code}: "
                                f"{body_text}"
                            )

                        prompt_cache_state["attempt_meta"] = copy.deepcopy(variant["meta"])
                        prompt_cache_state["fallback_triggered"] = bool(variant_index > 0)
                        prompt_cache_state["fallback_reason"] = prompt_fallback_reason

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

                        usage_summary = AnthropicPromptCacheService.extract_usage_summary(
                            response_body.get("usage") or {},
                            attempt_meta=variant["meta"],
                        )
                        prompt_cache_state["usage_summary"] = usage_summary

                        if conversation_runtime_info:
                            if request_attempt["is_compacted"]:
                                conversation_runtime_info["compression_mode"] = "non_stream_active"
                                conversation_runtime_info["compression_status"] = "ACTIVE_APPLIED"
                                conversation_runtime_info["compression_fallback_reason"] = None
                            elif active_compacted_request and request_attempt_index > 0:
                                conversation_runtime_info["compression_mode"] = "non_stream_active"
                                conversation_runtime_info["compression_status"] = "ACTIVE_FALLBACK_FULL"
                                conversation_runtime_info["compression_fallback_reason"] = compression_fallback_reason
                                conversation_runtime_info["_conversation_mark_cooldown"] = True
                            commit_payload = conversation_runtime_info.get("_conversation_shadow_commit") or {}
                            commit_payload["compression_mode"] = conversation_runtime_info.get("compression_mode")
                            conversation_runtime_info["_conversation_shadow_commit"] = commit_payload

                        return {
                            "response": response_body,
                            "model": request_data.get("model"),
                            "usage": {
                                "prompt_tokens": usage_summary.get("input_tokens", 0),
                                "completion_tokens": usage_summary.get("output_tokens", 0),
                                "cache_read_input_tokens": usage_summary.get("cache_read_input_tokens", 0),
                                "cache_creation_input_tokens": usage_summary.get("cache_creation_input_tokens", 0),
                                "logical_input_tokens": usage_summary.get("logical_input_tokens", 0),
                            },
                        }

                    if should_retry_full:
                        logger.warning(
                            "Conversation compaction fallback to full request_id=%s channel=%s channel_id=%s reason=%s",
                            request_id,
                            channel.name,
                            channel.id,
                            compression_fallback_reason,
                        )
                        continue

                raise Exception(compression_fallback_reason or "Anthropic request failed")

        # Shared passthrough middleware contract
        try:
            cache_response, cache_info = await CacheMiddleware.wrap_request(
                request_body=original_request_data,
                headers=request_headers or {},
                user=user,
                db=db,
                upstream_call=upstream_call,
                unified_model=unified_model,
                request_format="anthropic_messages",
                requested_model=requested_model,
            )
        except Exception as exc:
            merged_error_cache_info = ProxyService._merge_conversation_shadow_into_cache_info(
                ProxyService._extract_cache_info_from_error(exc),
                conversation_shadow_info,
            )
            if merged_error_cache_info:
                setattr(exc, "_request_cache_info", merged_error_cache_info)
            raise

        response_time_ms = ProxyService._calculate_elapsed_ms(start_time)

        # Extract response body and tokens
        response_body = cache_response.get("response", cache_response)
        actual_input_tokens = cache_response.get("usage", {}).get("prompt_tokens", 0)
        actual_output_tokens = cache_response.get("usage", {}).get("completion_tokens", 0)
        usage_summary = prompt_cache_state.get("usage_summary") or {
            "input_tokens": actual_input_tokens,
            "output_tokens": actual_output_tokens,
            "logical_input_tokens": actual_input_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_creation_5m_input_tokens": 0,
            "cache_creation_1h_input_tokens": 0,
            "prompt_cache_status": "BYPASS",
        }
        merged_cache_info = ProxyService._merge_prompt_cache_state_into_cache_info(
            cache_info,
            prompt_cache_state,
        )
        merged_cache_info = ProxyService._merge_conversation_shadow_into_cache_info(
            merged_cache_info,
            conversation_runtime_info or conversation_shadow_info,
        )

        billing_input_tokens = ProxyService._resolve_prompt_cache_billing_input_tokens(
            db,
            usage_summary,
        )
        billing_output_tokens = int(usage_summary.get("output_tokens", actual_output_tokens) or 0)

        # Record success and do accounting with billing tokens
        ProxyService._record_success(db, channel)
        ProxyService._deduct_balance_and_log(
            db, user, api_key_record, unified_model, request_id,
            requested_model, billing_input_tokens, billing_output_tokens, channel,
            client_ip, response_time_ms, is_stream=False,
            actual_model=request_data.get("model"),
            cache_info=merged_cache_info,
            conversation_state_info=conversation_runtime_info or conversation_shadow_info,
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
        usage_state: dict[str, Any] = {}
        msg_id = None
        msg_model = None
        stop_reason = None
        content_blocks: dict[int, dict] = {}

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
                    ProxyService._merge_anthropic_usage_snapshot(usage_state, usage)
                    input_tokens = usage.get("input_tokens", 0)

                elif chunk_type == "content_block_start":
                    block_index = int(chunk.get("index", 0) or 0)
                    content_block = chunk.get("content_block") or {}
                    if isinstance(content_block, dict):
                        content_blocks[block_index] = copy.deepcopy(content_block)

                elif chunk_type == "content_block_delta":
                    block_index = int(chunk.get("index", 0) or 0)
                    delta = chunk.get("delta", {})
                    block = content_blocks.setdefault(
                        block_index,
                        {"type": "text", "text": ""},
                    )

                    text = delta.get("text")
                    if text:
                        block["type"] = block.get("type") or "text"
                        block["text"] = f"{block.get('text', '')}{text}"

                    thinking = delta.get("thinking")
                    if thinking:
                        block["type"] = block.get("type") or "thinking"
                        block["thinking"] = f"{block.get('thinking', '')}{thinking}"

                    partial_json = delta.get("partial_json")
                    if partial_json is not None:
                        block["type"] = block.get("type") or "tool_use"
                        block["_partial_json"] = f"{block.get('_partial_json', '')}{partial_json}"

                elif chunk_type == "message_delta":
                    delta = chunk.get("delta", {})
                    stop_reason = delta.get("stop_reason", stop_reason)
                    usage = chunk.get("usage", {})
                    ProxyService._merge_anthropic_usage_snapshot(usage_state, usage)
                    output_tokens = usage.get("output_tokens", output_tokens)
                    if "input_tokens" in usage and usage["input_tokens"]:
                        input_tokens = usage["input_tokens"]

                elif chunk_type == "message_stop":
                    break

            except (json.JSONDecodeError, TypeError):
                pass

        ordered_blocks: list[dict] = []
        for block_index in sorted(content_blocks.keys()):
            block = copy.deepcopy(content_blocks[block_index])
            partial_json = block.pop("_partial_json", None)
            if partial_json is not None:
                block["input"] = ProxyService._parse_tool_arguments(partial_json)

            block_type = str(block.get("type", "") or "")
            if block_type == "text":
                ordered_blocks.append({
                    "type": "text",
                    "text": str(block.get("text", "") or ""),
                })
            elif block_type in {"thinking", "redacted_thinking"}:
                ordered_blocks.append({
                    "type": block_type,
                    "thinking": str(block.get("thinking", "") or block.get("text", "") or ""),
                })
            elif block_type == "tool_use":
                ordered_blocks.append({
                    "type": "tool_use",
                    "id": str(block.get("id") or f"toolu_{block_index}"),
                    "name": str(block.get("name", "") or "tool"),
                    "input": copy.deepcopy(block.get("input") or {}),
                })
            elif block:
                ordered_blocks.append(block)

        if not ordered_blocks:
            ordered_blocks = [{"type": "text", "text": ""}]

        response_body = {
            "id": msg_id or "msg-unknown",
            "type": "message",
            "role": "assistant",
            "content": ordered_blocks,
            "model": msg_model or "unknown",
            "stop_reason": stop_reason or "end_turn",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": int(usage_state.get("cache_read_input_tokens", 0) or 0),
                "cache_creation_input_tokens": int(usage_state.get("cache_creation_input_tokens", 0) or 0),
                "cache_creation_5m_input_tokens": int(
                    usage_state.get("cache_creation_5m_input_tokens", 0) or 0
                ),
                "cache_creation_1h_input_tokens": int(
                    usage_state.get("cache_creation_1h_input_tokens", 0) or 0
                ),
                "cache_creation": copy.deepcopy(usage_state.get("cache_creation") or {}),
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
        actual_model: Optional[str] = None,
        cache_info: Optional[dict[str, Any]] = None,
        conversation_state_info: Optional[dict[str, Any]] = None,
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

            cache_log_fields = RequestCacheSummaryService.build_request_log_fields(cache_info)
            shadow_commit = None
            if cache_info and isinstance(cache_info.get("_conversation_shadow_commit"), dict):
                shadow_commit = cache_info.get("_conversation_shadow_commit")
            elif (
                conversation_state_info
                and isinstance(conversation_state_info.get("_conversation_shadow_commit"), dict)
            ):
                shadow_commit = conversation_state_info.get("_conversation_shadow_commit")

            committed_session_id = ConversationSessionService.commit_success_state(
                db,
                user_id=user.id,
                requested_model=requested_model,
                protocol_type=channel.protocol_type or "",
                channel_id=channel.id,
                shadow_commit=shadow_commit,
            )
            if committed_session_id and not cache_log_fields.get("conversation_session_id"):
                cache_log_fields["conversation_session_id"] = committed_session_id
                if cache_info is not None:
                    cache_info["conversation_session_id"] = committed_session_id
                if conversation_state_info is not None:
                    conversation_state_info["conversation_session_id"] = committed_session_id

            # Write consumption record (for both modes)
            logical_input_tokens = int(
                cache_log_fields.get("logical_input_tokens") or input_tokens
            )
            consumption = ConsumptionRecord(
                user_id=user.id,
                request_id=request_id,
                model_name=requested_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                logical_input_tokens=logical_input_tokens,
                upstream_input_tokens=int(cache_log_fields.get("upstream_input_tokens", 0) or 0),
                upstream_cache_read_input_tokens=int(
                    cache_log_fields.get("upstream_cache_read_input_tokens", 0) or 0
                ),
                upstream_cache_creation_input_tokens=int(
                    cache_log_fields.get("upstream_cache_creation_input_tokens", 0) or 0
                ),
                upstream_prompt_cache_status=cache_log_fields.get("upstream_prompt_cache_status"),
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
                actual_model=actual_model or unified_model.model_name,
                protocol_type=channel.protocol_type,
                is_stream=1 if is_stream else 0,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                response_time_ms=response_time_ms,
                cache_status=cache_log_fields["cache_status"],
                cache_hit_segments=cache_log_fields["cache_hit_segments"],
                cache_miss_segments=cache_log_fields["cache_miss_segments"],
                cache_bypass_segments=cache_log_fields["cache_bypass_segments"],
                cache_reused_tokens=cache_log_fields["cache_reused_tokens"],
                cache_new_tokens=cache_log_fields["cache_new_tokens"],
                cache_reused_chars=cache_log_fields["cache_reused_chars"],
                cache_new_chars=cache_log_fields["cache_new_chars"],
                logical_input_tokens=logical_input_tokens,
                upstream_input_tokens=cache_log_fields["upstream_input_tokens"],
                upstream_cache_read_input_tokens=cache_log_fields["upstream_cache_read_input_tokens"],
                upstream_cache_creation_input_tokens=cache_log_fields["upstream_cache_creation_input_tokens"],
                upstream_cache_creation_5m_input_tokens=cache_log_fields["upstream_cache_creation_5m_input_tokens"],
                upstream_cache_creation_1h_input_tokens=cache_log_fields["upstream_cache_creation_1h_input_tokens"],
                upstream_prompt_cache_status=cache_log_fields["upstream_prompt_cache_status"],
                conversation_session_id=cache_log_fields["conversation_session_id"],
                conversation_match_status=cache_log_fields["conversation_match_status"],
                compression_mode=cache_log_fields["compression_mode"],
                compression_status=cache_log_fields["compression_status"],
                original_estimated_input_tokens=cache_log_fields["original_estimated_input_tokens"],
                compressed_estimated_input_tokens=cache_log_fields["compressed_estimated_input_tokens"],
                compression_saved_estimated_tokens=cache_log_fields["compression_saved_estimated_tokens"],
                compression_ratio=Decimal(str(cache_log_fields["compression_ratio"])),
                compression_fallback_reason=cache_log_fields["compression_fallback_reason"],
                upstream_session_mode=cache_log_fields["upstream_session_mode"],
                upstream_session_id=cache_log_fields["upstream_session_id"],
                status="success",
                error_message=None,
                client_ip=client_ip,
            )
            db.add(req_log)

            RequestCacheSummaryService.persist_request_cache_summary(
                db,
                request_id=request_id,
                user_id=user.id,
                requested_model=requested_model,
                protocol_type=channel.protocol_type,
                cache_info=cache_info,
            )
            if cache_info and cache_info.get("_conversation_mark_cooldown"):
                ConversationSessionService.mark_session_cooldown_by_session_id(
                    db,
                    cache_log_fields.get("conversation_session_id") or committed_session_id,
                )

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
        cache_info: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a failed request without deducting balance."""
        try:
            cache_log_fields = RequestCacheSummaryService.build_request_log_fields(cache_info)
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
                cache_status=cache_log_fields["cache_status"],
                cache_hit_segments=cache_log_fields["cache_hit_segments"],
                cache_miss_segments=cache_log_fields["cache_miss_segments"],
                cache_bypass_segments=cache_log_fields["cache_bypass_segments"],
                cache_reused_tokens=cache_log_fields["cache_reused_tokens"],
                cache_new_tokens=cache_log_fields["cache_new_tokens"],
                cache_reused_chars=cache_log_fields["cache_reused_chars"],
                cache_new_chars=cache_log_fields["cache_new_chars"],
                logical_input_tokens=int(cache_log_fields.get("logical_input_tokens", 0) or 0),
                upstream_input_tokens=cache_log_fields["upstream_input_tokens"],
                upstream_cache_read_input_tokens=cache_log_fields["upstream_cache_read_input_tokens"],
                upstream_cache_creation_input_tokens=cache_log_fields["upstream_cache_creation_input_tokens"],
                upstream_cache_creation_5m_input_tokens=cache_log_fields["upstream_cache_creation_5m_input_tokens"],
                upstream_cache_creation_1h_input_tokens=cache_log_fields["upstream_cache_creation_1h_input_tokens"],
                upstream_prompt_cache_status=cache_log_fields["upstream_prompt_cache_status"],
                conversation_session_id=cache_log_fields["conversation_session_id"],
                conversation_match_status=cache_log_fields["conversation_match_status"],
                compression_mode=cache_log_fields["compression_mode"],
                compression_status=cache_log_fields["compression_status"],
                original_estimated_input_tokens=cache_log_fields["original_estimated_input_tokens"],
                compressed_estimated_input_tokens=cache_log_fields["compressed_estimated_input_tokens"],
                compression_saved_estimated_tokens=cache_log_fields["compression_saved_estimated_tokens"],
                compression_ratio=Decimal(str(cache_log_fields["compression_ratio"])),
                compression_fallback_reason=cache_log_fields["compression_fallback_reason"],
                upstream_session_mode=cache_log_fields["upstream_session_mode"],
                upstream_session_id=cache_log_fields["upstream_session_id"],
                status="error",
                error_message=error_message[:2000] if error_message else None,
                client_ip=client_ip,
            )
            db.add(req_log)

            RequestCacheSummaryService.persist_request_cache_summary(
                db,
                request_id=request_id,
                user_id=user.id,
                requested_model=requested_model,
                protocol_type=channel.protocol_type if channel else None,
                cache_info=cache_info,
            )
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
