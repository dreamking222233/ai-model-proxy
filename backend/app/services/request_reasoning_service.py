"""Small, validated reasoning snapshots; never retain request contents."""
from __future__ import annotations

import json
from typing import Any


class RequestReasoningService:
    EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "auto"}
    MODES = {"default", "disabled", "enabled", "adaptive", "auto"}

    @staticmethod
    def _label(value: Any, allowed: set[str]) -> str | None:
        if isinstance(value, str) and value.strip().lower() in allowed:
            return value.strip().lower()
        return None

    @staticmethod
    def _budget(value: Any) -> int | None:
        # bool is an int subclass; do not turn invalid configuration into a budget.
        if type(value) is int and -1 <= value <= 2147483647:
            return value
        return None

    @staticmethod
    def extract(request_data: dict | None) -> dict:
        data = request_data if isinstance(request_data, dict) else {}
        # Passthrough WebSocket frames may wrap their request in ``response``.
        if data.get("type") in {"response.create", "response.append"} and isinstance(data.get("response"), dict):
            data = data["response"]
        thinking = data.get("thinking")
        thinking = thinking if isinstance(thinking, dict) else {}
        mode = RequestReasoningService._label(thinking.get("type"), RequestReasoningService.MODES)
        if mode == "disabled":
            return {"mode": "disabled"}

        reasoning = data.get("reasoning")
        reasoning = reasoning if isinstance(reasoning, dict) else {}
        output_config = data.get("output_config")
        output_config = output_config if isinstance(output_config, dict) else {}
        effort = next((label for value in (
            reasoning.get("effort"), data.get("reasoning_effort"),
            output_config.get("effort"), thinking.get("effort"),
        ) if (label := RequestReasoningService._label(value, RequestReasoningService.EFFORTS))), None)
        budget = RequestReasoningService._budget(thinking.get("budget_tokens"))
        if budget is not None and budget <= 0:
            budget = None  # Claude enabled thinking requires a positive budget.

        generation = data.get("generationConfig") or data.get("generation_config")
        generation = generation if isinstance(generation, dict) else {}
        google_thinking = generation.get("thinkingConfig") or generation.get("thinking_config")
        google_thinking = google_thinking if isinstance(google_thinking, dict) else {}
        if not effort:
            effort = RequestReasoningService._label(
                google_thinking.get("thinkingLevel", google_thinking.get("thinking_level")),
                RequestReasoningService.EFFORTS,
            )
        if budget is None:
            google_budget = RequestReasoningService._budget(
                google_thinking.get("thinkingBudget", google_thinking.get("thinking_budget"))
            )
            if google_budget == -1:
                mode = "auto"
            elif google_budget == 0:
                mode = "disabled"
            budget = google_budget
        if budget is not None and budget > 0 and not mode:
            mode = "enabled"
        if mode == "disabled":
            return {"mode": "disabled"}
        snapshot = {}
        if effort:
            snapshot["effort"] = effort
        if mode:
            snapshot["mode"] = mode
        if budget is not None and budget >= 0:
            snapshot["budget_tokens"] = budget
        return snapshot or {"mode": "default"}

    @staticmethod
    def load(value: Any) -> dict | None:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
        if not isinstance(value, dict):
            return None
        result = {}
        effort = RequestReasoningService._label(value.get("effort"), RequestReasoningService.EFFORTS)
        mode = RequestReasoningService._label(value.get("mode"), RequestReasoningService.MODES)
        budget = RequestReasoningService._budget(value.get("budget_tokens"))
        if effort:
            result["effort"] = effort
        if mode:
            result["mode"] = mode
        if budget is not None and budget >= 0:
            result["budget_tokens"] = budget
        return result or None

    @staticmethod
    def with_snapshot(context: dict | None, request_data: dict | None) -> dict:
        # A fresh context per attempt/turn prevents concurrent streams sharing snapshots.
        return {**(context or {}), "reasoning_snapshot": RequestReasoningService.extract(request_data)}

    @staticmethod
    def refresh_forwarded_snapshot(context: dict | None, request_data: dict) -> dict:
        # Dispatch has already allocated a context for this attempt. Keep the outer
        # failure logger in sync when a bridge changes the forwarded configuration.
        context = context if context is not None else {}
        context["reasoning_snapshot"] = RequestReasoningService.extract(request_data)
        return context

    @staticmethod
    def log_fields(context: dict | None) -> dict:
        snapshot = RequestReasoningService.load((context or {}).get("reasoning_snapshot"))
        return {"reasoning_snapshot": json.dumps(snapshot, separators=(",", ":")) if snapshot else None}
