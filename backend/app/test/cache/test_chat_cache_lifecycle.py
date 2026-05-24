"""Manual cache lifecycle test for chat completion requests.

Scenarios covered:
1. Warm up a long stable prefix.
2. Repeat the exact same request immediately.
3. Repeat the same request after a short delay.
4. Continue the conversation with the same long prefix.
5. Send a new user turn with the same long prefix but without history.
6. Slightly change the prefix to observe cache miss / reduced hit.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = os.getenv("CACHE_TEST_BASE_URL", "http://43.156.153.12:8317")
API_KEY = os.getenv("CACHE_TEST_API_KEY", "sk-uWQMveW4dEb4TCxMJ")
ENDPOINT = "/v1/chat/completions"
MODEL = os.getenv("CACHE_TEST_MODEL", "gpt-5.5")
REQUEST_TIMEOUT = int(os.getenv("CACHE_TEST_TIMEOUT", "120"))
REPEAT_DELAY_SECONDS = float(os.getenv("CACHE_TEST_DELAY_SECONDS", "3"))
OUTPUT_DIR = Path("backend/app/test/cache/output")

LONG_SHARED_CONTEXT = "\n".join(
    [
        "你是一个严格的中文助手，需要保持简洁、准确、结构化输出。",
        "以下资料为本次缓存测试的长期共享背景，在每次请求里都尽量保持不变。",
    ]
    + [
        (
            f"共享上下文{i:03d}：这是一段稳定前缀，用于测试 prompt cache 的创建与复用。"
            "如果你看到这段话，说明请求携带了同一批前缀内容。请不要重写规则，不要省略设定。"
        )
        for i in range(1, 81)
    ]
)

CHANGED_SHARED_CONTEXT = LONG_SHARED_CONTEXT + "\n附加变更：这一行是故意新增的前缀变化，用于观察缓存命中下降。"


def post_json(url: str, payload: dict, api_key: str) -> dict:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
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


def extract_assistant_text(result: dict) -> str:
    return ((((result.get("choices") or [{}])[0]).get("message") or {}).get("content")) or ""


def extract_usage(result: dict) -> dict:
    usage = result.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    cached_tokens = int(prompt_details.get("cached_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
        "cached_tokens": cached_tokens,
        "cache_hit_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else 0,
        "reasoning_tokens": int(completion_details.get("reasoning_tokens", 0) or 0),
    }


def run_case(url: str, label: str, messages: list[dict]) -> dict:
    payload = {"model": MODEL, "messages": messages}
    started_at = time.time()
    result = post_json(url, payload, API_KEY)
    elapsed = round(time.time() - started_at, 3)
    usage = extract_usage(result)
    assistant_reply = extract_assistant_text(result)

    print(f"\n=== {label} ===")
    print(f"message_count: {len(messages)}")
    print(f"elapsed_seconds: {elapsed}")
    print(f"request_id: {result.get('id')}")
    print(f"assistant_reply: {assistant_reply}")
    print("usage:")
    print(json.dumps(usage, ensure_ascii=False, indent=2))

    return {
        "label": label,
        "elapsed_seconds": elapsed,
        "messages": messages,
        "assistant_reply": assistant_reply,
        "usage": usage,
        "raw_response": result,
    }


def save_report(report: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"chat_cache_lifecycle_{int(time.time())}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    report: list[dict] = []

    print(f"Request URL: {url}")
    print(f"Model: {MODEL}")
    print(f"Shared context chars: {len(LONG_SHARED_CONTEXT)}")
    print(f"Repeat delay seconds: {REPEAT_DELAY_SECONDS}")

    base_messages = [
        {"role": "system", "content": LONG_SHARED_CONTEXT},
    ]

    first_turn_messages = base_messages + [
        {"role": "user", "content": "请只回复“生命周期-第1次”。"}
    ]
    case_1 = run_case(url, "case_1_warmup_create", first_turn_messages)
    report.append(case_1)

    case_2 = run_case(url, "case_2_immediate_repeat_same_prompt", first_turn_messages)
    report.append(case_2)

    if REPEAT_DELAY_SECONDS > 0:
        print(f"\nSleeping {REPEAT_DELAY_SECONDS} seconds before delayed repeat...")
        time.sleep(REPEAT_DELAY_SECONDS)

    case_3 = run_case(url, "case_3_delayed_repeat_same_prompt", first_turn_messages)
    report.append(case_3)

    multi_turn_messages = first_turn_messages + [
        {"role": "assistant", "content": case_3["assistant_reply"]},
        {"role": "user", "content": "请只回复“生命周期-第2次”。"}
    ]
    case_4 = run_case(url, "case_4_multi_turn_same_prefix", multi_turn_messages)
    report.append(case_4)

    same_prefix_new_turn_messages = base_messages + [
        {"role": "user", "content": "请只回复“生命周期-新分支”。"}
    ]
    case_5 = run_case(url, "case_5_same_prefix_new_user_turn", same_prefix_new_turn_messages)
    report.append(case_5)

    changed_prefix_messages = [
        {"role": "system", "content": CHANGED_SHARED_CONTEXT},
        {"role": "user", "content": "请只回复“生命周期-前缀变更”。"},
    ]
    case_6 = run_case(url, "case_6_changed_prefix_compare", changed_prefix_messages)
    report.append(case_6)

    output_path = save_report(report)
    print(f"\nSaved report: {output_path}")


if __name__ == "__main__":
    main()
