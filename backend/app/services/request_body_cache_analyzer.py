"""Request-body cache analyzer for Anthropic/OpenAI/Responses payloads."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any


class RequestBodyCacheAnalyzer:
    """Split request bodies into stable cacheable segments and summarize duplicates."""

    _PREVIEW_CHARS = 220
    _EST_CHARS_PER_TOKEN = 2.5

    @staticmethod
    def stable_dump(value: Any) -> str:
        """Serialize values consistently for hashing and size calculations."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except TypeError:
            return str(value)

    @staticmethod
    def hash_value(value: Any) -> str:
        """Return a SHA256 hash for a request segment."""
        return hashlib.sha256(
            RequestBodyCacheAnalyzer.stable_dump(value).encode("utf-8", errors="replace")
        ).hexdigest()

    @staticmethod
    def size_chars(value: Any) -> int:
        """Return serialized character length for a request segment."""
        return len(RequestBodyCacheAnalyzer.stable_dump(value))

    @staticmethod
    def estimate_tokens(value: Any) -> int:
        """Estimate tokens from serialized character length."""
        size_chars = RequestBodyCacheAnalyzer.size_chars(value)
        if size_chars <= 0:
            return 0
        return max(1, int(size_chars / RequestBodyCacheAnalyzer._EST_CHARS_PER_TOKEN))

    @staticmethod
    def build_preview(value: Any) -> str:
        """Build a short readable preview for logs and cache summaries."""
        raw = RequestBodyCacheAnalyzer.stable_dump(value)
        if len(raw) <= RequestBodyCacheAnalyzer._PREVIEW_CHARS:
            return raw
        remainder = len(raw) - RequestBodyCacheAnalyzer._PREVIEW_CHARS
        return f"{raw[:RequestBodyCacheAnalyzer._PREVIEW_CHARS]}...<truncated {remainder} chars>"

    @staticmethod
    def _build_segment(
        request_format: str,
        segment_type: str,
        scope: str,
        payload: Any,
    ) -> dict[str, Any]:
        """Build a normalized segment description."""
        return {
            "request_format": request_format,
            "segment_type": segment_type,
            "scope": scope,
            "payload": payload,
            "hash": RequestBodyCacheAnalyzer.hash_value(payload),
            "size_chars": RequestBodyCacheAnalyzer.size_chars(payload),
            "estimated_tokens": RequestBodyCacheAnalyzer.estimate_tokens(payload),
            "preview": RequestBodyCacheAnalyzer.build_preview(payload),
        }

    @staticmethod
    def _extract_anthropic_segments(request_body: dict[str, Any]) -> list[dict[str, Any]]:
        """Split Anthropic Messages API request into stable segments."""
        segments: list[dict[str, Any]] = []
        request_format = "anthropic_messages"

        system_value = request_body.get("system")
        if isinstance(system_value, list):
            for index, block in enumerate(system_value):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "system_block",
                        f"system[{index}]",
                        block,
                    )
                )
        elif system_value is not None:
            segments.append(
                RequestBodyCacheAnalyzer._build_segment(
                    request_format,
                    "system_block",
                    "system[0]",
                    system_value,
                )
            )

        tools = request_body.get("tools")
        if isinstance(tools, list):
            for index, tool in enumerate(tools):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "tool_definition",
                        f"tools[{index}]",
                        tool,
                    )
                )

        messages = request_body.get("messages")
        if not isinstance(messages, list):
            return segments

        for msg_index, message in enumerate(messages):
            if not isinstance(message, dict):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "message",
                        f"messages[{msg_index}]",
                        message,
                    )
                )
                continue

            role = str(message.get("role", "") or "")
            content = message.get("content")
            if isinstance(content, list):
                for block_index, block in enumerate(content):
                    payload = {"role": role, "content_block": block}
                    segments.append(
                        RequestBodyCacheAnalyzer._build_segment(
                            request_format,
                            "message_content_block",
                            f"messages[{msg_index}].content[{block_index}]",
                            payload,
                        )
                    )
            else:
                payload = {"role": role, "content": content}
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "message",
                        f"messages[{msg_index}]",
                        payload,
                    )
                )

        return segments

    @staticmethod
    def _extract_openai_chat_segments(request_body: dict[str, Any]) -> list[dict[str, Any]]:
        """Split OpenAI chat-completions request into stable segments."""
        segments: list[dict[str, Any]] = []
        request_format = "openai_chat"

        if request_body.get("system") is not None:
            segments.append(
                RequestBodyCacheAnalyzer._build_segment(
                    request_format,
                    "system_message",
                    "system",
                    request_body.get("system"),
                )
            )

        tools = request_body.get("tools")
        if isinstance(tools, list):
            for index, tool in enumerate(tools):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "tool_definition",
                        f"tools[{index}]",
                        tool,
                    )
                )

        functions = request_body.get("functions")
        if isinstance(functions, list):
            for index, function in enumerate(functions):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "tool_definition",
                        f"functions[{index}]",
                        function,
                    )
                )

        messages = request_body.get("messages")
        if not isinstance(messages, list):
            return segments

        for msg_index, message in enumerate(messages):
            if not isinstance(message, dict):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "message",
                        f"messages[{msg_index}]",
                        message,
                    )
                )
                continue

            role = str(message.get("role", "") or "")
            content = message.get("content")
            if role in {"system", "developer"}:
                payload = {"role": role, "content": content}
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "system_message",
                        f"messages[{msg_index}]",
                        payload,
                    )
                )
            elif isinstance(content, list):
                for block_index, block in enumerate(content):
                    payload = {"role": role, "content_block": block}
                    segments.append(
                        RequestBodyCacheAnalyzer._build_segment(
                            request_format,
                            "message_content_block",
                            f"messages[{msg_index}].content[{block_index}]",
                            payload,
                        )
                    )
            else:
                payload = {"role": role, "content": content}
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "message",
                        f"messages[{msg_index}]",
                        payload,
                    )
                )

            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list):
                for call_index, tool_call in enumerate(tool_calls):
                    payload = {"role": role, "tool_call": tool_call}
                    segments.append(
                        RequestBodyCacheAnalyzer._build_segment(
                            request_format,
                            "tool_call",
                            f"messages[{msg_index}].tool_calls[{call_index}]",
                            payload,
                        )
                    )

        return segments

    @staticmethod
    def _extract_responses_segments(request_body: dict[str, Any]) -> list[dict[str, Any]]:
        """Split Responses API request into stable segments."""
        segments: list[dict[str, Any]] = []
        request_format = "responses"

        for field_name in ("instructions", "system"):
            if request_body.get(field_name) is not None:
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "instructions",
                        field_name,
                        request_body.get(field_name),
                    )
                )

        tools = request_body.get("tools")
        if isinstance(tools, list):
            for index, tool in enumerate(tools):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "tool_definition",
                        f"tools[{index}]",
                        tool,
                    )
                )

        input_value = request_body.get("input")
        if isinstance(input_value, list):
            for index, item in enumerate(input_value):
                segments.append(
                    RequestBodyCacheAnalyzer._build_segment(
                        request_format,
                        "input_item",
                        f"input[{index}]",
                        item,
                    )
                )
        elif input_value is not None:
            segments.append(
                RequestBodyCacheAnalyzer._build_segment(
                    request_format,
                    "input_item",
                    "input",
                    input_value,
                )
            )

        return segments

    @staticmethod
    def extract_segments(request_body: dict[str, Any], request_format: str) -> list[dict[str, Any]]:
        """Extract atomic request segments for the given request format."""
        if request_format == "anthropic_messages":
            return RequestBodyCacheAnalyzer._extract_anthropic_segments(request_body)
        if request_format == "responses":
            return RequestBodyCacheAnalyzer._extract_responses_segments(request_body)
        return RequestBodyCacheAnalyzer._extract_openai_chat_segments(request_body)

    @staticmethod
    def summarize_duplicate_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
        """Summarize exact duplicate atomic segments within one request."""
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for segment in segments:
            grouped[segment["hash"]].append(segment)

        samples = []
        duplicate_groups = 0
        duplicate_instances = 0
        duplicate_chars = 0

        for bucket in grouped.values():
            if len(bucket) <= 1:
                continue
            duplicate_groups += 1
            duplicate_instances += len(bucket) - 1
            duplicate_chars += (len(bucket) - 1) * int(bucket[0]["size_chars"])
            samples.append(
                {
                    "segment_type": bucket[0]["segment_type"],
                    "count": len(bucket),
                    "size_chars": bucket[0]["size_chars"],
                    "preview": bucket[0]["preview"],
                    "locations": [item["scope"] for item in bucket[:4]],
                }
            )

        samples.sort(key=lambda item: (item["size_chars"], item["count"]), reverse=True)
        return {
            "segment_count": len(segments),
            "duplicate_groups": duplicate_groups,
            "duplicate_instances": duplicate_instances,
            "duplicate_chars": duplicate_chars,
            "samples": samples[:5],
        }
