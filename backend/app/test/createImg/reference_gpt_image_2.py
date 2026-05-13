"""Reference example for calling gpt-image-2 through the origin server."""

import base64
import json
import time
from pathlib import Path

import requests


# 保留源站地址，绕过 Cloudflare，适合长耗时图片请求。
BASE_URL = "http://43.155.142.220:8085"
API_KEY = "sk-请替换为你自己的密钥"
ENDPOINT = "/v1/images/generations"

# 当前示例使用 gpt-image-2 文生图接口。
MODEL = "gpt-image-2"
PROMPT = "生成一个抖音直播间截图"

# 推荐优先使用 image_size + aspect_ratio。
# 支持的 image_size: 1K / 2K / 4K
# 横屏 16:9，竖屏 9:16。
IMAGE_SIZE = "4K"
ASPECT_RATIO = "9:16"

# gpt-image-2 支持 1 <= n <= 4
IMAGE_COUNT = 1
REQUEST_TIMEOUT = 600
OUTPUT_DIR = Path(__file__).resolve().parent / "generated_images"


def build_payload() -> dict:
    return {
        "model": MODEL,
        "prompt": PROMPT,
        "response_format": "b64_json",
        "image_size": IMAGE_SIZE,
        "aspect_ratio": ASPECT_RATIO,
        "n": IMAGE_COUNT,
    }


def request_images(payload: dict) -> dict:
    response = requests.post(
        f"{BASE_URL.rstrip('/')}{ENDPOINT}",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def save_images(result: dict) -> list[Path]:
    images = result.get("data") or []
    if not images:
        raise RuntimeError(
            f"接口返回成功，但没有图片数据:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    saved_files: list[Path] = []

    for index, item in enumerate(images, start=1):
        b64_json = item.get("b64_json")
        if not b64_json:
            continue

        file_path = OUTPUT_DIR / f"gpt_image_2_{timestamp}_{index}.png"
        file_path.write_bytes(base64.b64decode(b64_json))
        saved_files.append(file_path)

    if not saved_files:
        raise RuntimeError(
            f"接口返回成功，但 data 中没有可保存的 b64_json:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    return saved_files


def main() -> None:
    payload = build_payload()
    print("request_url:", f"{BASE_URL.rstrip('/')}{ENDPOINT}")
    print("payload:", json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        result = request_images(payload)
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        raise SystemExit(f"HTTP {exc.response.status_code if exc.response else 'ERROR'} 请求失败:\n{body}") from exc
    except requests.RequestException as exc:
        raise SystemExit(f"请求失败: {exc}") from exc

    saved_files = save_images(result)

    print("\n请求成功")
    print("request_id:", result.get("request_id"))
    print("usage:", json.dumps(result.get("usage") or {}, ensure_ascii=False, indent=2))
    print("saved_files:")
    for file_path in saved_files:
        print(file_path)


if __name__ == "__main__":
    main()
