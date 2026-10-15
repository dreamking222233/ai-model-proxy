"""Evidence that a normalized usage is complete enough for simulation."""
from __future__ import annotations
from typing import Any


_TOKEN_KEYS = {
    "input_tokens", "prompt_tokens", "output_tokens", "completion_tokens", "total_tokens",
    "cache_read_input_tokens", "cache_read_tokens", "cached_tokens", "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens", "cache_creation_input_tokens", "cache_creation_5m_input_tokens",
    "cache_creation_1h_input_tokens", "cache_write_tokens", "cache_creation_tokens",
    "cache_write_input_tokens", "ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens",
}


def accounted_bucket(record, field: str, legacy_field: str) -> int:
    """Version 1 stores explicit billable zero; version 0 keeps legacy fallback."""
    value = getattr(record, field, None)
    if getattr(record, "usage_accounting_version", 0) == 1 and value is not None:
        return int(value)
    return int(value or getattr(record, legacy_field, 0) or 0)


def valid_token(value: Any) -> bool:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return False
    try:
        n = int(value)
        return n >= 0 and (not isinstance(value, float) or n == value) and (
            not isinstance(value, str) or str(n) == value.strip())
    except (ValueError, OverflowError, TypeError):
        return False


def usage_provenance(usage: dict, *, anthropic: bool = False) -> dict:
    """Optional cache fields may be absent; input and output must be explicit."""
    input_keys = ("input_tokens", "prompt_tokens", "prompt_cache_miss_tokens") if anthropic else (
        "input_tokens", "prompt_tokens")
    output_keys = ("output_tokens", "completion_tokens")
    invalid = any(key in _TOKEN_KEYS and value is not None and not valid_token(value)
                  for key, value in usage.items())
    for container in ("input_tokens_details", "prompt_tokens_details", "cache_creation"):
        detail = usage.get(container)
        if detail is not None and not isinstance(detail, dict):
            invalid = True
        elif isinstance(detail, dict):
            invalid |= any(key in _TOKEN_KEYS and value is not None and not valid_token(value)
                           for key, value in detail.items())
    def conflicts(values):
        return len({int(value) for value in values if valid_token(value)}) > 1
    invalid |= conflicts([usage.get(key) for key in output_keys])
    output_presence_keys = ("output_tokens",) if anthropic else output_keys
    if not anthropic:
        invalid |= conflicts([usage.get("input_tokens"), usage.get("prompt_tokens")])
    else:
        # Anthropic accounting consumes output_tokens; completion_tokens is not
        # mapped. It cannot prove a complete output or replace an earlier value.
        invalid |= valid_token(usage.get("completion_tokens")) and not valid_token(usage.get("output_tokens"))
        invalid |= conflicts([usage.get("input_tokens"), usage.get("prompt_cache_miss_tokens")])
    details = [usage] + [usage[key] for key in ("input_tokens_details", "prompt_tokens_details")
                         if isinstance(usage.get(key), dict)]
    invalid |= conflicts([detail.get(key) for detail in details for key in
                          ("cache_read_input_tokens", "cache_read_tokens", "cached_tokens", "prompt_cache_hit_tokens")])
    invalid |= conflicts([detail.get(key) for detail in details for key in
                          ("cache_creation_input_tokens", "cache_write_tokens", "cache_creation_tokens", "cache_write_input_tokens")])
    if anthropic:
        def first_count(values, default=0):
            return next((int(value) for value in values if valid_token(value)), default)
        read = first_count(detail.get(key) for detail in details for key in
                           ("cache_read_input_tokens", "cache_read_tokens", "cached_tokens", "prompt_cache_hit_tokens"))
        creation_detail = usage.get("cache_creation")
        creation_detail = creation_detail if isinstance(creation_detail, dict) else {}
        nested_creation = sum(first_count([creation_detail.get(key)]) for key in
                              ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"))
        creation = first_count((detail.get(key) for detail in details for key in
                                ("cache_creation_input_tokens", "cache_write_tokens", "cache_creation_tokens", "cache_write_input_tokens")),
                               default=nested_creation)
        # Check original exclusive counts before alias normalization can replace
        # input_tokens with prompt_tokens - read - creation and hide a conflict.
        exclusive = first_count([usage.get("input_tokens"), usage.get("prompt_cache_miss_tokens")], default=None)
        if exclusive is not None and valid_token(usage.get("prompt_tokens")):
            invalid |= exclusive + read + creation != int(usage["prompt_tokens"])
        if valid_token(usage.get("cache_creation_input_tokens")):
            invalid |= nested_creation > int(usage["cache_creation_input_tokens"])
    prior = usage.get("_simulation_provenance") or {}
    return {"input_present": any(valid_token(usage.get(k)) for k in input_keys) or prior.get("input_present", False),
            "output_present": any(valid_token(usage.get(k)) for k in output_presence_keys) or prior.get("output_present", False),
            "valid": not invalid and prior.get("valid", True), "source": "upstream"}
