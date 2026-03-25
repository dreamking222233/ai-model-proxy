"""Safe history compaction estimation for Anthropic requests."""
from __future__ import annotations

import copy
import json
from typing import Any

from app.services.request_body_cache_analyzer import RequestBodyCacheAnalyzer


class HistoryCompactionService:
    """Build conservative compaction candidates and token estimates."""

    @staticmethod
    def _estimate_message_text_tokens(messages: list[dict[str, Any]] | None) -> int:
        """Estimate tokens from Anthropic-style messages."""
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
    def estimate_anthropic_input_tokens(request_data: dict[str, Any]) -> int:
        """Approximate Anthropic request input tokens."""
        total_tokens = HistoryCompactionService._estimate_message_text_tokens(
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
    def _is_tool_result_block(block: Any) -> bool:
        return isinstance(block, dict) and str(block.get("type") or "") == "tool_result"

    @staticmethod
    def _is_text_like_block(block: Any) -> bool:
        if isinstance(block, str):
            return bool(block.strip())
        if not isinstance(block, dict):
            return bool(str(block).strip())
        block_type = str(block.get("type") or "")
        if block_type in {"text", "input_text"}:
            return bool(str(block.get("text", "") or "").strip())
        return False

    @staticmethod
    def _message_contains_non_tool_result_content(message: Any) -> bool:
        if not isinstance(message, dict):
            return bool(str(message).strip())
        content = message.get("content")
        if isinstance(content, list):
            return any(
                not HistoryCompactionService._is_tool_result_block(block)
                and HistoryCompactionService._is_text_like_block(block)
                for block in content
            )
        return bool(str(content or "").strip())

    @staticmethod
    def group_completed_turns(messages: list[dict[str, Any]] | None) -> list[list[dict[str, Any]]]:
        """Group messages into completed turn buckets without splitting tool cycles."""
        if not isinstance(messages, list) or not messages:
            return []

        groups: list[list[dict[str, Any]]] = []
        current_group: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "") if isinstance(message, dict) else ""
            starts_new_turn = (
                role == "user"
                and HistoryCompactionService._message_contains_non_tool_result_content(message)
                and current_group
            )
            if starts_new_turn:
                groups.append(current_group)
                current_group = []
            current_group.append(copy.deepcopy(message))

        if current_group:
            groups.append(current_group)
        return groups

    @staticmethod
    def split_history_windows(
        request_data: dict[str, Any],
        *,
        recent_turns: int,
    ) -> dict[str, Any]:
        """Split Anthropic request messages into frozen history and recent exact window."""
        messages = request_data.get("messages")
        groups = HistoryCompactionService.group_completed_turns(messages)
        if not groups:
            return {
                "groups": [],
                "frozen_groups": [],
                "recent_groups": [],
                "frozen_messages": [],
                "recent_messages": [],
            }

        pending_group = groups[-1]
        completed_groups = groups[:-1]
        if recent_turns <= 0:
            exact_groups = [pending_group]
            frozen_groups = completed_groups
        else:
            exact_groups = completed_groups[-recent_turns:] + [pending_group]
            frozen_groups = completed_groups[:-recent_turns] if len(completed_groups) > recent_turns else []

        frozen_messages = [message for group in frozen_groups for message in group]
        recent_messages = [message for group in exact_groups for message in group]
        return {
            "groups": groups,
            "frozen_groups": frozen_groups,
            "recent_groups": exact_groups,
            "frozen_messages": frozen_messages,
            "recent_messages": recent_messages,
        }

    @staticmethod
    def _extract_message_summary(message: dict[str, Any]) -> dict[str, Any]:
        """Build a concise deterministic summary for one message."""
        role = str(message.get("role") or "")
        content = message.get("content")
        text_parts: list[str] = []
        tool_uses: list[str] = []
        tool_results: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    block_type = str(block.get("type") or "")
                    if block_type in {"text", "input_text"}:
                        text = str(block.get("text", "") or "").strip()
                        if text:
                            text_parts.append(text[:240])
                    elif block_type == "tool_use":
                        tool_uses.append(str(block.get("name") or "tool"))
                    elif block_type == "tool_result":
                        result_text = RequestBodyCacheAnalyzer.build_preview(
                            block.get("content") or block
                        )
                        tool_results.append(result_text[:240])
                elif isinstance(block, str) and block.strip():
                    text_parts.append(block.strip()[:240])
        elif content:
            text_parts.append(str(content).strip()[:240])

        return {
            "role": role,
            "text": text_parts,
            "tool_uses": tool_uses,
            "tool_results": tool_results,
        }

    @staticmethod
    def build_checkpoint_summary(
        frozen_groups: list[list[dict[str, Any]]],
        *,
        max_summary_tokens: int,
    ) -> dict[str, Any]:
        """Build a conservative structured summary for old completed turns."""
        turns = []
        summary_lines: list[str] = []
        for index, group in enumerate(frozen_groups, start=1):
            turn_summary = {
                "turn_index": index,
                "messages": [HistoryCompactionService._extract_message_summary(message) for message in group],
            }
            turns.append(turn_summary)
            for message in turn_summary["messages"]:
                role = message["role"] or "unknown"
                if message["text"]:
                    summary_lines.append(f"{role}: {' | '.join(message['text'])}")
                if message["tool_uses"]:
                    summary_lines.append(f"{role} tool_use: {', '.join(message['tool_uses'])}")
                if message["tool_results"]:
                    summary_lines.append(f"{role} tool_result: {' | '.join(message['tool_results'])}")

        summary_text = "\n".join(summary_lines)
        max_chars = max(400, int(max_summary_tokens * 2.5))
        if len(summary_text) > max_chars:
            summary_text = f"{summary_text[:max_chars]}...<truncated {len(summary_text) - max_chars} chars>"

        return {
            "kind": "conversation_checkpoint",
            "summary_text": summary_text,
            "turn_count": len(frozen_groups),
            "turns": turns[:12],
        }

    @staticmethod
    def rebuild_compacted_anthropic_request(
        request_data: dict[str, Any],
        *,
        summary_payload: dict[str, Any],
        recent_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a safe compacted request candidate for shadow estimation."""
        compacted_request = copy.deepcopy(request_data)
        system_value = compacted_request.get("system")
        summary_block = {
            "type": "text",
            "text": (
                "Conversation checkpoint for older completed history. "
                "Prefer exact recent messages if any conflict.\n"
                f"{summary_payload.get('summary_text', '')}"
            ).strip(),
        }
        if isinstance(system_value, list):
            compacted_request["system"] = list(system_value) + [summary_block]
        elif system_value is None:
            compacted_request["system"] = [summary_block]
        else:
            compacted_request["system"] = [system_value, summary_block]

        compacted_request["messages"] = copy.deepcopy(recent_messages)
        return compacted_request
