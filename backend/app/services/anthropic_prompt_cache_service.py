"""Anthropic prompt caching helpers.

Only injects official prompt-cache metadata and never rewrites business text,
tool definitions, or message ordering.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.health_service import get_system_config

logger = logging.getLogger(__name__)


class AnthropicPromptCacheService:
    """Build Anthropic prompt-cache request variants and parse upstream usage."""

    _ERROR_HINTS = (
        "cache_control",
        "prompt cache",
        "prompt caching",
        "ephemeral",
        "ttl",
        "anthropic-beta",
        "improperly formed request",
        "invalid_request_error",
    )

    @staticmethod
    def is_enabled(db: Session) -> bool:
        """Return whether Anthropic prompt caching is enabled."""
        return bool(get_system_config(db, "anthropic_prompt_cache_enabled", False))

    @staticmethod
    def get_user_visible(db: Session) -> bool:
        """Return whether prompt cache usage is visible on user pages."""
        return bool(get_system_config(db, "anthropic_prompt_cache_user_visible", False))

    @staticmethod
    def get_billing_mode(db: Session) -> str:
        """Return billing mode for Anthropic prompt cache traffic."""
        mode = str(get_system_config(db, "anthropic_prompt_cache_billing_mode", "logical") or "logical")
        return mode if mode in {"logical", "actual_upstream"} else "logical"

    @staticmethod
    def build_request_variants(
        db: Session,
        request_data: dict[str, Any],
        request_headers: Optional[dict[str, str]] = None,
    ) -> list[dict[str, Any]]:
        """Build request variants for prompt-cache main path and fallbacks."""
        base_variant = {
            "request_data": copy.deepcopy(request_data),
            "header_overrides": {},
            "meta": {
                "attempted": False,
                "source": "system",
                "skip_reason": "disabled",
                "applied_static_breakpoint": False,
                "applied_history_breakpoint": False,
                "static_ttl": None,
                "history_ttl": None,
                "beta_header": None,
            },
        }

        if not AnthropicPromptCacheService.is_enabled(db):
            return [base_variant]

        if AnthropicPromptCacheService._has_existing_cache_control(request_data):
            base_variant["meta"] = {
                "attempted": False,
                "source": "user",
                "skip_reason": "user_cache_control_present",
                "applied_static_breakpoint": False,
                "applied_history_breakpoint": False,
                "static_ttl": None,
                "history_ttl": None,
                "beta_header": None,
            }
            return [base_variant]

        static_ttl = AnthropicPromptCacheService._normalize_ttl(
            get_system_config(db, "anthropic_prompt_cache_static_ttl", "5m")
        )
        history_enabled = bool(get_system_config(db, "anthropic_prompt_cache_history_enabled", True))
        history_ttl = AnthropicPromptCacheService._normalize_ttl(
            get_system_config(db, "anthropic_prompt_cache_history_ttl", "5m")
        )
        beta_header = str(
            get_system_config(db, "anthropic_prompt_cache_beta_header", "extended-cache-ttl-2025-04-11")
            or ""
        ).strip()

        variants: list[dict[str, Any]] = []
        full_variant = AnthropicPromptCacheService._build_variant(
            request_data=request_data,
            request_headers=request_headers,
            static_ttl=static_ttl,
            history_enabled=history_enabled,
            history_ttl=history_ttl,
            beta_header=beta_header,
            label="full",
        )
        if full_variant["meta"]["attempted"]:
            variants.append(full_variant)

            if static_ttl == "1h":
                fallback_variant = AnthropicPromptCacheService._build_variant(
                    request_data=request_data,
                    request_headers=request_headers,
                    static_ttl="5m",
                    history_enabled=history_enabled,
                    history_ttl=history_ttl,
                    beta_header="",
                    label="fallback_5m",
                )
                if (
                    fallback_variant["meta"]["attempted"]
                    and AnthropicPromptCacheService._variant_signature(fallback_variant)
                    != AnthropicPromptCacheService._variant_signature(full_variant)
                ):
                    variants.append(fallback_variant)

        no_cache_variant = copy.deepcopy(base_variant)
        no_cache_variant["meta"] = {
            "attempted": False,
            "source": "system",
            "skip_reason": "fallback_no_cache",
            "applied_static_breakpoint": False,
            "applied_history_breakpoint": False,
            "static_ttl": None,
            "history_ttl": None,
            "beta_header": None,
        }
        variants.append(no_cache_variant)

        if not variants or not variants[0]["meta"]["attempted"]:
            base_variant["meta"]["skip_reason"] = "no_safe_breakpoint"
            return [base_variant]

        return variants

    @staticmethod
    def should_retry_with_fallback(
        *,
        status_code: int,
        response_text: str,
        attempt_meta: dict[str, Any],
        has_more_variants: bool,
    ) -> bool:
        """Return whether an upstream error should retry with a less aggressive variant."""
        if not has_more_variants or not attempt_meta.get("attempted"):
            return False
        if status_code not in {400, 403, 422}:
            return False

        lowered = (response_text or "").lower()
        return any(hint in lowered for hint in AnthropicPromptCacheService._ERROR_HINTS)

    @staticmethod
    def extract_usage_summary(
        usage: Optional[dict[str, Any]],
        *,
        attempt_meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Parse Anthropic usage into a stable prompt-cache summary."""
        usage = usage or {}
        cache_creation = usage.get("cache_creation") or {}
        cache_creation_5m = int(
            cache_creation.get("ephemeral_5m_input_tokens")
            or usage.get("cache_creation_5m_input_tokens")
            or 0
        )
        cache_creation_1h = int(
            cache_creation.get("ephemeral_1h_input_tokens")
            or usage.get("cache_creation_1h_input_tokens")
            or 0
        )
        cache_creation_total = int(
            usage.get("cache_creation_input_tokens")
            or (cache_creation_5m + cache_creation_1h)
            or 0
        )
        cache_read = int(usage.get("cache_read_input_tokens") or 0)
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        logical_input_tokens = input_tokens + cache_read + cache_creation_total

        attempted = bool((attempt_meta or {}).get("attempted"))
        if cache_read > 0 and cache_creation_total > 0:
            status = "MIXED"
        elif cache_read > 0:
            status = "READ"
        elif cache_creation_total > 0:
            status = "WRITE"
        elif attempted:
            status = "NONE"
        else:
            status = "BYPASS"

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "logical_input_tokens": logical_input_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation_total,
            "cache_creation_5m_input_tokens": cache_creation_5m,
            "cache_creation_1h_input_tokens": cache_creation_1h,
            "prompt_cache_status": status,
        }

    @staticmethod
    def merge_into_cache_info(
        cache_info: Optional[dict[str, Any]],
        *,
        attempt_meta: Optional[dict[str, Any]],
        usage_summary: Optional[dict[str, Any]] = None,
        fallback_triggered: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Merge prompt-cache request/usage info into the shared cache_info payload."""
        merged = copy.deepcopy(cache_info or {})
        details = copy.deepcopy(merged.get("details") or {})
        usage_summary = usage_summary or AnthropicPromptCacheService.extract_usage_summary(
            {},
            attempt_meta=attempt_meta,
        )
        prompt_cache_details = {
            "attempted": bool((attempt_meta or {}).get("attempted")),
            "source": (attempt_meta or {}).get("source"),
            "skip_reason": (attempt_meta or {}).get("skip_reason"),
            "applied_static_breakpoint": bool((attempt_meta or {}).get("applied_static_breakpoint")),
            "applied_history_breakpoint": bool((attempt_meta or {}).get("applied_history_breakpoint")),
            "static_ttl": (attempt_meta or {}).get("static_ttl"),
            "history_ttl": (attempt_meta or {}).get("history_ttl"),
            "beta_header": (attempt_meta or {}).get("beta_header"),
            "fallback_triggered": fallback_triggered,
            "fallback_reason": fallback_reason,
            "usage": usage_summary,
        }
        details["anthropic_prompt_cache"] = prompt_cache_details
        merged["details"] = details
        merged["logical_input_tokens"] = int(usage_summary.get("logical_input_tokens", 0) or 0)
        merged["upstream_input_tokens"] = int(usage_summary.get("input_tokens", 0) or 0)
        merged["upstream_cache_read_input_tokens"] = int(
            usage_summary.get("cache_read_input_tokens", 0) or 0
        )
        merged["upstream_cache_creation_input_tokens"] = int(
            usage_summary.get("cache_creation_input_tokens", 0) or 0
        )
        merged["upstream_cache_creation_5m_input_tokens"] = int(
            usage_summary.get("cache_creation_5m_input_tokens", 0) or 0
        )
        merged["upstream_cache_creation_1h_input_tokens"] = int(
            usage_summary.get("cache_creation_1h_input_tokens", 0) or 0
        )
        merged["upstream_prompt_cache_status"] = usage_summary.get("prompt_cache_status")
        return merged

    @staticmethod
    def _build_variant(
        *,
        request_data: dict[str, Any],
        request_headers: Optional[dict[str, str]],
        static_ttl: str,
        history_enabled: bool,
        history_ttl: str,
        beta_header: str,
        label: str,
    ) -> dict[str, Any]:
        variant_request = copy.deepcopy(request_data)
        applied_static = AnthropicPromptCacheService._inject_static_breakpoint(
            variant_request,
            static_ttl=static_ttl,
        )
        applied_history = False
        if history_enabled:
            applied_history = AnthropicPromptCacheService._inject_history_breakpoint(
                variant_request,
                history_ttl=history_ttl,
            )

        requires_beta = static_ttl == "1h" and applied_static
        header_overrides: dict[str, str] = {}
        if requires_beta and beta_header:
            header_overrides["anthropic-beta"] = AnthropicPromptCacheService._merge_beta_header(
                request_headers,
                beta_header,
            )

        return {
            "request_data": variant_request,
            "header_overrides": header_overrides,
            "meta": {
                "attempted": bool(applied_static or applied_history),
                "source": "system",
                "skip_reason": None if (applied_static or applied_history) else f"{label}_no_safe_breakpoint",
                "applied_static_breakpoint": applied_static,
                "applied_history_breakpoint": applied_history,
                "static_ttl": static_ttl if applied_static else None,
                "history_ttl": history_ttl if applied_history else None,
                "beta_header": beta_header if requires_beta and beta_header else None,
                "label": label,
            },
        }

    @staticmethod
    def _has_existing_cache_control(request_data: dict[str, Any]) -> bool:
        """Return whether the client already supplied cache-control metadata."""
        if "cache_control" in request_data:
            return True

        tools = request_data.get("tools")
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict) and "cache_control" in tool:
                    return True

        system_value = request_data.get("system")
        system_blocks = system_value if isinstance(system_value, list) else [system_value]
        for block in system_blocks:
            if isinstance(block, dict) and "cache_control" in block:
                return True

        messages = request_data.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "cache_control" in block:
                            return True
                elif isinstance(content, dict) and "cache_control" in content:
                    return True
        return False

    @staticmethod
    def _inject_static_breakpoint(request_data: dict[str, Any], *, static_ttl: str) -> bool:
        """Inject a static-prefix breakpoint on the last safe tool/system block."""
        tools = request_data.get("tools")
        if isinstance(tools, list):
            for tool in reversed(tools):
                if isinstance(tool, dict) and "cache_control" not in tool:
                    tool["cache_control"] = AnthropicPromptCacheService._build_cache_control(static_ttl)
                    return True

        system_value = request_data.get("system")
        if isinstance(system_value, list):
            for block in reversed(system_value):
                if AnthropicPromptCacheService._is_cacheable_block(block):
                    block["cache_control"] = AnthropicPromptCacheService._build_cache_control(static_ttl)
                    return True
        elif AnthropicPromptCacheService._is_cacheable_block(system_value):
            system_value["cache_control"] = AnthropicPromptCacheService._build_cache_control(static_ttl)
            return True

        return False

    @staticmethod
    def _inject_history_breakpoint(request_data: dict[str, Any], *, history_ttl: str) -> bool:
        """Inject a rolling-history breakpoint on the latest cacheable user block."""
        messages = request_data.get("messages")
        if not isinstance(messages, list):
            return False

        for message in reversed(messages):
            if not isinstance(message, dict) or str(message.get("role") or "") != "user":
                continue

            content = message.get("content")
            if isinstance(content, list):
                for block in reversed(content):
                    if AnthropicPromptCacheService._is_cacheable_block(block):
                        block["cache_control"] = AnthropicPromptCacheService._build_cache_control(history_ttl)
                        return True
            elif AnthropicPromptCacheService._is_cacheable_block(content):
                content["cache_control"] = AnthropicPromptCacheService._build_cache_control(history_ttl)
                return True
            break

        return False

    @staticmethod
    def _is_cacheable_block(block: Any) -> bool:
        """Return whether a content block can safely accept cache_control."""
        if not isinstance(block, dict):
            return False
        if "cache_control" in block:
            return False
        block_type = str(block.get("type") or "")
        return block_type not in {"thinking", "redacted_thinking"}

    @staticmethod
    def _build_cache_control(ttl: str) -> dict[str, str]:
        """Build Anthropic cache_control metadata for a supported TTL."""
        cache_control = {"type": "ephemeral"}
        if ttl == "1h":
            cache_control["ttl"] = "1h"
        return cache_control

    @staticmethod
    def _normalize_ttl(value: Any) -> str:
        """Normalize TTL config to 5m/1h."""
        normalized = str(value or "5m").strip().lower()
        return "1h" if normalized == "1h" else "5m"

    @staticmethod
    def _merge_beta_header(
        request_headers: Optional[dict[str, str]],
        beta_header: str,
    ) -> str:
        """Merge prompt-cache beta header into forwarded anthropic-beta values."""
        values: list[str] = []
        source_headers = request_headers or {}
        source_value = source_headers.get("anthropic-beta") or source_headers.get("Anthropic-Beta")
        if isinstance(source_value, str):
            values.extend(
                item.strip() for item in source_value.split(",") if item and item.strip()
            )
        if beta_header and beta_header not in values:
            values.append(beta_header)
        return ",".join(values)

    @staticmethod
    def _variant_signature(variant: dict[str, Any]) -> str:
        """Serialize a variant so duplicate fallback attempts can be removed."""
        payload = {
            "request_data": variant.get("request_data") or {},
            "header_overrides": variant.get("header_overrides") or {},
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
