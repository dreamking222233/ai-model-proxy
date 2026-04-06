#!/usr/bin/env python3
import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

import httpx


DEFAULT_BASE_URL = "http://localhost:8085"
DEFAULT_API_KEY = "sk-8f698230bcb52e4c210b039e5cfcac6c66396dfa3d6ee78c"
DEFAULT_MODEL = "claude-opus-4-6"


async def stream_messages(base_url: str, api_key: str, payload: dict) -> tuple[list[tuple[str, dict]], dict]:
    url = f"{base_url}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    events: list[tuple[str, dict]] = []
    response_headers: dict = {}

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response_headers = dict(response.headers)
            if response.status_code != 200:
                body = await response.aread()
                raise RuntimeError(f"HTTP {response.status_code}: {body.decode(errors='ignore')}")

            current_event = "message"
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event: "):
                    current_event = line[7:]
                    continue
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                payload_obj = json.loads(data_str)
                events.append((current_event, payload_obj))

    return events, response_headers


def summarize_events(events: list[tuple[str, dict]]) -> dict:
    summary = {
        "event_names": [],
        "tool_use_names": [],
        "tool_use_ids": [],
        "stop_reason": None,
        "text_fragments": [],
        "json_deltas": [],
        "errors": [],
    }
    for event_name, payload in events:
        summary["event_names"].append(event_name)
        if event_name == "content_block_start":
            block = payload.get("content_block") or {}
            if block.get("type") == "tool_use":
                summary["tool_use_names"].append(block.get("name"))
                summary["tool_use_ids"].append(block.get("id"))
        elif event_name == "content_block_delta":
            delta = payload.get("delta") or {}
            if delta.get("type") == "text_delta":
                summary["text_fragments"].append(delta.get("text", ""))
            elif delta.get("type") == "input_json_delta":
                summary["json_deltas"].append(delta.get("partial_json", ""))
        elif event_name == "message_delta":
            summary["stop_reason"] = (payload.get("delta") or {}).get("stop_reason")
        elif event_name == "error":
            summary["errors"].append((payload.get("error") or {}).get("message"))
    return summary


def build_text_payload(model: str) -> dict:
    return {
        "model": model,
        "max_tokens": 128,
        "stream": True,
        "messages": [
            {"role": "user", "content": "请用一句话说明桥接层回归测试的目的。"}
        ],
    }


def build_tool_payload(model: str) -> dict:
    return {
        "model": model,
        "max_tokens": 256,
        "stream": True,
        "tools": [
            {
                "name": "get_status",
                "description": "Return a short bridge status summary.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"}
                    },
                    "required": ["topic"],
                },
            }
        ],
        "tool_choice": {"type": "tool", "name": "get_status"},
        "messages": [
            {
                "role": "user",
                "content": "调用 get_status 工具，topic 传 bridge-streaming。不要输出其他文本。",
            }
        ],
    }


def build_image_payload(model: str, image_path: Path) -> dict:
    image_bytes = image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    suffix = image_path.suffix.lower().lstrip(".") or "png"
    if suffix == "jpg":
        suffix = "jpeg"
    media_type = f"image/{suffix}"
    return {
        "model": model,
        "max_tokens": 128,
        "stream": True,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请简要描述这张图片。"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                ],
            }
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Anthropic via Responses bridge behavior.")
    parser.add_argument("scenario", choices=["text", "tool", "image"])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--image-path")
    args = parser.parse_args()

    if args.scenario == "text":
        payload = build_text_payload(args.model)
    elif args.scenario == "tool":
        payload = build_tool_payload(args.model)
    else:
        if not args.image_path:
            raise SystemExit("--image-path is required for image scenario")
        payload = build_image_payload(args.model, Path(args.image_path))

    started_at = time.time()
    events, headers = await stream_messages(args.base_url, args.api_key, payload)
    summary = summarize_events(events)
    result = {
        "elapsed_seconds": round(time.time() - started_at, 3),
        "response_headers": {
            key: headers[key]
            for key in headers
            if key.lower() in {"x-request-id", "x-cache-status", "content-type"}
        },
        "summary": summary,
        "event_count": len(events),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
