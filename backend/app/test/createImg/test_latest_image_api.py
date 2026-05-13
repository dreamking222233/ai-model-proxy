"""Manual image generation test using the documented API protocol."""

import base64
import json
import struct
import time
from pathlib import Path
from typing import Optional, Tuple

import requests


BASE_URL = "http://43.155.142.220:8085"
API_KEY = "sk-702fff3c4760ba3a65a3cea58e025c0beff74d79323ddc2f"
ENDPOINT = "/v1/images/generations"

MODEL = "gpt-image-2"
PROMPT = "生成一个抖音女主播穿着OL职业装和白丝 裸色高跟鞋"
IMAGE_SIZE = "4K"
ASPECT_RATIO = "9:16"
QUALITY = "high"
IMAGE_COUNT = 1
OUTPUT_DIR = Path(__file__).resolve().parent / "generated_images"
REQUEST_TIMEOUT = 600
PIXEL_SIZE = None


def build_payload() -> dict:
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "response_format": "b64_json",
        "n": IMAGE_COUNT,
    }

    if PIXEL_SIZE:
        payload["size"] = PIXEL_SIZE
        payload["quality"] = QUALITY
    else:
        payload["image_size"] = IMAGE_SIZE
        payload["aspect_ratio"] = ASPECT_RATIO

    return payload


def post_json(url: str, payload: dict, api_key: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def read_png_size(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    png_signature = b"\x89PNG\r\n\x1a\n"
    if not image_bytes.startswith(png_signature):
        return None
    if len(image_bytes) < 24:
        return None
    width, height = struct.unpack(">II", image_bytes[16:24])
    return width, height


def save_images(result: dict, output_dir: Path) -> list[dict]:
    data = result.get("data") or []
    if not data:
        raise RuntimeError(
            f"接口未返回图片数据:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    saved_files: list[dict] = []

    for index, item in enumerate(data, start=1):
        b64_json = item.get("b64_json")
        if not b64_json:
            continue

        mime_type = item.get("mime_type") or "image/png"
        extension = "png"
        if "/" in mime_type:
            extension = mime_type.split("/", 1)[1]

        image_bytes = base64.b64decode(b64_json)
        file_path = output_dir / f"latest_api_{timestamp}_{index}.{extension}"
        file_path.write_bytes(image_bytes)
        saved_files.append({
            "path": file_path,
            "mime_type": mime_type,
            "size": read_png_size(image_bytes),
        })

    if not saved_files:
        raise RuntimeError(
            f"返回成功但没有可保存的 b64_json:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    return saved_files


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    payload = build_payload()
    output_dir = OUTPUT_DIR.expanduser()

    print("request_url:", url)
    print("payload:", json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        result = post_json(url, payload, API_KEY)
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        raise SystemExit(f"HTTP {exc.response.status_code if exc.response else 'ERROR'} 请求失败:\n{body}") from exc
    except requests.RequestException as exc:
        raise SystemExit(f"请求失败: {exc}") from exc

    saved_files = save_images(result, output_dir)

    print("\n请求成功")
    print("request_id:", result.get("request_id"))
    print("usage:", json.dumps(result.get("usage") or {}, ensure_ascii=False, indent=2))
    print("saved_files:")
    for item in saved_files:
        if item["size"]:
            width, height = item["size"]
            print(f"{item['path']} -> {width}x{height}")
        else:
            print(item["path"])


def test_latest_image_api_generation() -> None:
    """Pytest entrypoint for the same manual API verification flow."""
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    payload = build_payload()
    output_dir = OUTPUT_DIR.expanduser()

    result = post_json(url, payload, API_KEY)
    saved_files = save_images(result, output_dir)
    usage = result.get("usage") or {}

    assert saved_files, "接口返回成功，但没有保存出图片文件"
    assert usage.get("billing_type") == "image_credit"
    assert usage.get("request_type") == "image_generation"
    assert usage.get("image_count") == IMAGE_COUNT
    assert usage.get("image_size") == IMAGE_SIZE


if __name__ == "__main__":
    main()
