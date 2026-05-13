"""Manual cache test for Anthropic-style /v1/messages requests.

Scenarios:
1. Plain requests, relying on gateway-managed prompt cache if enabled.
2. Explicit prompt-cache metadata using Anthropic cache_control blocks.

The script prints usage fields such as:
- input_tokens
- output_tokens
- cache_read_input_tokens
- cache_creation_input_tokens

Those fields are the primary signal for whether prompt cache is available.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = os.getenv("CACHE_TEST_BASE_URL", "http://43.156.153.12:8080")
API_KEY = os.getenv("CACHE_TEST_API_KEY", "sk-qeBTyXmKefPLsYPBbX9Xk1hmW94EemEp")
ENDPOINT = "/v1/messages"
MODEL = os.getenv("CACHE_TEST_MODEL", "claude-sonnet-4.5-thinking")
REQUEST_TIMEOUT = int(os.getenv("CACHE_TEST_TIMEOUT", "180"))
REPEAT_DELAY_SECONDS = float(os.getenv("CACHE_TEST_DELAY_SECONDS", "3"))
OUTPUT_DIR = Path("backend/app/test/cache/output")

LONG_SHARED_CONTEXT = "\n".join(
    [
        "你是一个严格的中文助手，需要保持简洁、准确、结构化输出。",
        "以下资料是本次 Anthropic prompt cache 测试使用的长期稳定前缀。",
        "请不要改写规则，不要省略背景，也不要主动总结这些上下文。",
    ]
    + [
        (
            f"稳定前缀{i:03d}：这是用于观察 cache creation 与 cache read 的固定背景。"
            "后续请求会尽量复用完全相同的前缀内容，只修改末尾用户问题。"
        )
        for i in range(1, 91)
    ]
)

CHANGED_SHARED_CONTEXT = (
    LONG_SHARED_CONTEXT
    + "\n附加变更：这一行是人为插入的前缀扰动，用来观察缓存是否部分复用或直接失效。"
)


def post_json(
    url: str,
    payload: dict[str, Any],
    api_key: str,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "anthropic-version": "2023-06-01",
    }
    if extra_headers:
        headers.update(extra_headers)

    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} request failed:\n{error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"Request timed out after {REQUEST_TIMEOUT}s") from exc
    except socket.timeout as exc:
        raise RuntimeError(f"Request timed out after {REQUEST_TIMEOUT}s") from exc


def extract_text_blocks(result: dict[str, Any]) -> list[str]:
    content = result.get("content") or []
    texts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text:
                texts.append(text)
    return texts


def extract_usage(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage") or {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
    logical_input = int(usage.get("logical_input_tokens", 0) or 0)
    if logical_input <= 0:
        logical_input = input_tokens + cache_read + cache_creation
    return {
        "input_tokens": input_tokens,
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "logical_input_tokens": logical_input,
        "cache_hit_ratio": round(cache_read / logical_input, 4) if logical_input else 0,
    }


def print_case_result(label: str, response: dict[str, Any], elapsed: float) -> None:
    usage = extract_usage(response)
    text_reply = " | ".join(extract_text_blocks(response))
    print(f"\n=== {label} ===")
    print(f"elapsed_seconds: {elapsed}")
    print(f"request_id: {response.get('id')}")
    print(f"response_model: {response.get('model')}")
    print(f"assistant_text: {text_reply}")
    print("usage:")
    print(json.dumps(usage, ensure_ascii=False, indent=2))


def build_plain_payload(user_text: str, system_text: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "system": system_text,
        "messages": [{"role": "user", "content": user_text}],
    }


def build_explicit_cache_payload(user_text: str, system_text: str) -> dict[str, Any]:
    return {
        "model": MODEL,
        "system": [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_text}],
    }


def run_case(
    url: str,
    label: str,
    payload: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_at = time.time()
    response = post_json(url, payload, API_KEY, extra_headers=extra_headers)
    elapsed = round(time.time() - started_at, 3)
    print_case_result(label, response, elapsed)
    return {
        "label": label,
        "elapsed_seconds": elapsed,
        "payload": payload,
        "usage": extract_usage(response),
        "assistant_text_blocks": extract_text_blocks(response),
        "raw_response": response,
    }


def summarize_suite(suite_name: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    warmup = cases[0]["usage"]
    repeat = cases[1]["usage"] if len(cases) > 1 else {}
    delayed = cases[2]["usage"] if len(cases) > 2 else {}
    has_creation = any(int(case["usage"].get("cache_creation_input_tokens", 0) or 0) > 0 for case in cases)
    has_read = any(int(case["usage"].get("cache_read_input_tokens", 0) or 0) > 0 for case in cases)
    verdict = "unknown"
    if has_creation and has_read:
        verdict = "effective"
    elif has_creation and not has_read:
        verdict = "create_only"
    elif not has_creation and has_read:
        verdict = "read_only_unexpected"
    else:
        verdict = "not_detected"

    summary = {
        "suite": suite_name,
        "warmup_creation_tokens": warmup.get("cache_creation_input_tokens", 0),
        "repeat_read_tokens": repeat.get("cache_read_input_tokens", 0),
        "delayed_read_tokens": delayed.get("cache_read_input_tokens", 0),
        "verdict": verdict,
    }
    print(f"\n--- suite_summary: {suite_name} ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def save_report(report: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"anthropic_messages_cache_report_{int(time.time())}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    report: dict[str, Any] = {
        "request_url": url,
        "model": MODEL,
        "repeat_delay_seconds": REPEAT_DELAY_SECONDS,
        "shared_context_chars": len(LONG_SHARED_CONTEXT),
        "suites": {},
    }

    print(f"Request URL: {url}")
    print(f"Model: {MODEL}")
    print(f"Shared context chars: {len(LONG_SHARED_CONTEXT)}")
    print(f"Repeat delay seconds: {REPEAT_DELAY_SECONDS}")

    plain_cases: list[dict[str, Any]] = []
    plain_payload = build_plain_payload("请只回复“Anthropic-缓存-首次”。", LONG_SHARED_CONTEXT)
    plain_cases.append(run_case(url, "plain_case_1_warmup_create", plain_payload))
    plain_cases.append(run_case(url, "plain_case_2_immediate_repeat_same_prompt", plain_payload))

    if REPEAT_DELAY_SECONDS > 0:
        print(f"\nSleeping {REPEAT_DELAY_SECONDS} seconds before delayed repeat...")
        time.sleep(REPEAT_DELAY_SECONDS)

    plain_cases.append(run_case(url, "plain_case_3_delayed_repeat_same_prompt", plain_payload))
    plain_cases.append(
        run_case(
            url,
            "plain_case_4_same_prefix_new_user_turn",
            build_plain_payload("请只回复“Anthropic-缓存-新分支”。", LONG_SHARED_CONTEXT),
        )
    )
    plain_cases.append(
        run_case(
            url,
            "plain_case_5_changed_prefix_compare",
            build_plain_payload("请只回复“Anthropic-缓存-前缀变更”。", CHANGED_SHARED_CONTEXT),
        )
    )
    report["suites"]["plain_gateway_managed"] = {
        "cases": plain_cases,
        "summary": summarize_suite("plain_gateway_managed", plain_cases),
    }

    explicit_headers = {"anthropic-beta": "extended-cache-ttl-2025-04-11"}
    explicit_cases: list[dict[str, Any]] = []
    explicit_payload = build_explicit_cache_payload("请只回复“Anthropic-显式缓存-首次”。", LONG_SHARED_CONTEXT)
    explicit_cases.append(
        run_case(
            url,
            "explicit_case_1_warmup_create",
            explicit_payload,
            extra_headers=explicit_headers,
        )
    )
    explicit_cases.append(
        run_case(
            url,
            "explicit_case_2_immediate_repeat_same_prompt",
            explicit_payload,
            extra_headers=explicit_headers,
        )
    )

    if REPEAT_DELAY_SECONDS > 0:
        print(f"\nSleeping {REPEAT_DELAY_SECONDS} seconds before explicit delayed repeat...")
        time.sleep(REPEAT_DELAY_SECONDS)

    explicit_cases.append(
        run_case(
            url,
            "explicit_case_3_delayed_repeat_same_prompt",
            explicit_payload,
            extra_headers=explicit_headers,
        )
    )
    explicit_cases.append(
        run_case(
            url,
            "explicit_case_4_same_prefix_new_user_turn",
            build_explicit_cache_payload("请只回复“Anthropic-显式缓存-新分支”。", LONG_SHARED_CONTEXT),
            extra_headers=explicit_headers,
        )
    )
    report["suites"]["explicit_cache_control"] = {
        "cases": explicit_cases,
        "summary": summarize_suite("explicit_cache_control", explicit_cases),
    }

    output_path = save_report(report)
    print(f"\nSaved report: {output_path}")


if __name__ == "__main__":
    main()
