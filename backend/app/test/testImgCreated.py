"""Manual test script for this project's image generation proxy."""

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


# BASE_URL = "https://api.xiaoleai.team"
# API_KEY = "sk-8a5a983b619a63dd0e5ce6542b14b0f5ac3dd4d4d98b6a2e"
BASE_URL = "http://localhost:8085"
API_KEY = "sk-1b5300bc0b9dfe59769e499b86f3335a2c6fbc298cc3e1b4"
ENDPOINT = "/v1/image/created"
MODEL = "gemini-3.1-flash-image-preview"
PROMPT = "生成一张抖音首页女主播直播的截图"
ASPECT_RATIO = "1:1"
OUTPUT_DIR = Path("backend/app/test/output")


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
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} request failed:\n{error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc}") from exc


def save_images(result: dict) -> list[Path]:
    data = result.get("data") or []
    if not data:
        raise RuntimeError(
            f"No image data returned: {json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    saved_files: list[Path] = []

    for index, item in enumerate(data, start=1):
        b64_json = item.get("b64_json")
        if not b64_json:
            continue

        mime_type = item.get("mime_type") or "image/png"
        extension = "png"
        if "/" in mime_type:
            extension = mime_type.split("/", 1)[1]

        file_path = OUTPUT_DIR / f"generated_{timestamp}_{index}.{extension}"
        file_path.write_bytes(base64.b64decode(b64_json))
        saved_files.append(file_path)

    if not saved_files:
        raise RuntimeError(
            f"Response contains no b64_json image payload: {json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    return saved_files


def main() -> None:
    url = f"{BASE_URL.rstrip('/')}{ENDPOINT}"
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "response_format": "b64_json",
        "aspect_ratio": ASPECT_RATIO,
        "n": 1,
    }

    print(f"Request URL: {url}")
    print(f"Model: {MODEL}")
    print(f"Prompt: {PROMPT}")

    result = post_json(url, payload, API_KEY)
    saved_files = save_images(result)

    print("\nRequest succeeded.")
    print(json.dumps(result.get("usage") or {}, ensure_ascii=False, indent=2))
    print("\nSaved files:")
    for path in saved_files:
        print(f"- {path}")


if __name__ == "__main__":
    main()
