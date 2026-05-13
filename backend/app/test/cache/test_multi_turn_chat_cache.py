"""Manual cache test for repeated and multi-turn chat completion requests."""

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
OUTPUT_DIR = Path("backend/app/test/cache/output")

# Use a large stable prefix so later requests can reuse the same prompt prefix.
LONG_SHARED_CONTEXT = "\n".join(
    [
        "你是一个严格的中文助手，需要保持简洁、准确、结构化输出。",
        "以下是长期共享背景资料，请在整个会话里都视为固定前缀。",
    ]
    + [
        (
            f"背景段落{i:03d}：缓存测试需要一个稳定且足够长的上下文前缀。"
            "这段内容会在后续多次请求中保持不变，用来观察 cached_tokens 是否增加。"
            "请记住你正在参与缓存验证，不要主动省略上下文，不要改写系统规则。"
        )
        for i in range(1, 81)
    ]
)

USER_TURNS = [
    "请先只回复“收到第1轮”。",
    "请基于相同上下文，只回复“收到第2轮”。",
    "请继续保持相同风格，只回复“收到第3轮”。",
]


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
            body = response.read().decode("utf-8")
            return json.loads(body)
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


def extract_usage_summary(result: dict) -> dict:
    usage = result.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "cached_tokens": prompt_details.get("cached_tokens", 0),
        "reasoning_tokens": completion_details.get("reasoning_tokens", 0),
    }


def print_round_result(label: str, messages: list[dict], result: dict) -> None:
    summary = extract_usage_summary(result)
    assistant_text = extract_assistant_text(result)

    print(f"\n=== {label} ===")
    print(f"message_count: {len(messages)}")
    print(f"request_id: {result.get('id')}")
    print(f"assistant_reply: {assistant_text}")
    print("usage:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def save_report(report: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"multi_turn_cache_report_{int(time.time())}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    print(f"Request URL: {url}")
    print(f"Model: {MODEL}")
    print(f"Shared context chars: {len(LONG_SHARED_CONTEXT)}")

    report: list[dict] = []
    base_messages = [{"role": "system", "content": LONG_SHARED_CONTEXT}]

    first_turn_messages = base_messages + [{"role": "user", "content": USER_TURNS[0]}]
    first_payload = {"model": MODEL, "messages": first_turn_messages}
    first_result = post_json(url, first_payload, API_KEY)
    print_round_result("round_1_warmup", first_turn_messages, first_result)
    report.append(
        {
            "label": "round_1_warmup",
            "messages": first_turn_messages,
            "assistant_reply": extract_assistant_text(first_result),
            "usage": extract_usage_summary(first_result),
            "raw_response": first_result,
        }
    )

    repeat_result = post_json(url, first_payload, API_KEY)
    print_round_result("round_2_repeat_same_prompt", first_turn_messages, repeat_result)
    report.append(
        {
            "label": "round_2_repeat_same_prompt",
            "messages": first_turn_messages,
            "assistant_reply": extract_assistant_text(repeat_result),
            "usage": extract_usage_summary(repeat_result),
            "raw_response": repeat_result,
        }
    )

    conversation_messages = list(first_turn_messages)
    conversation_messages.append(
        {"role": "assistant", "content": extract_assistant_text(repeat_result)}
    )

    for index, user_turn in enumerate(USER_TURNS[1:], start=2):
        conversation_messages.append({"role": "user", "content": user_turn})
        payload = {"model": MODEL, "messages": conversation_messages}
        result = post_json(url, payload, API_KEY)
        label = f"round_{index + 1}_multi_turn"
        print_round_result(label, conversation_messages, result)
        report.append(
            {
                "label": label,
                "messages": list(conversation_messages),
                "assistant_reply": extract_assistant_text(result),
                "usage": extract_usage_summary(result),
                "raw_response": result,
            }
        )
        conversation_messages.append(
            {"role": "assistant", "content": extract_assistant_text(result)}
        )

    output_path = save_report(report)
    print(f"\nSaved report: {output_path}")


if __name__ == "__main__":
    main()
