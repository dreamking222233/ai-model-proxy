"""Manual cache test for a single-turn chat completion request."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request


BASE_URL = os.getenv("CACHE_TEST_BASE_URL", "http://43.156.153.12:8317")
API_KEY = os.getenv("CACHE_TEST_API_KEY", "sk-uWQMveW4dEb4TCxMJ")
ENDPOINT = "/v1/chat/completions"
MODEL = "gpt-5.5"
USER_MESSAGE = "你好"
REQUEST_TIMEOUT = int(os.getenv("CACHE_TEST_TIMEOUT", "120"))


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


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": USER_MESSAGE},
        ],
    }

    print(f"Request URL: {url}")
    print(f"Model: {MODEL}")
    print(f"User message: {USER_MESSAGE}")

    result = post_json(url, payload, API_KEY)
    usage = result.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    message = (
        (((result.get("choices") or [{}])[0]).get("message") or {}).get("content")
    )

    print("\nAssistant reply:")
    print(message)
    print("\nUsage:")
    print(json.dumps(usage, ensure_ascii=False, indent=2))
    print(f"\nCached prompt tokens: {prompt_details.get('cached_tokens', 0)}")


if __name__ == "__main__":
    main()
