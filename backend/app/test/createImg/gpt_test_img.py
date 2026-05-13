import base64
import requests
from pathlib import Path

# API_BASE = "https://api.xiaoleai.team/v1"
API_BASE = "http://localhost:8085/v1"
API_KEY = "sk-fe08732e298eaccf38582222d2e83c9d118b822e90faf9be"
OUTPUT_DIR = Path(__file__).resolve().parent
REQUEST_TIMEOUT = (10, 600)

payload = {
    "model": "gpt-image-2",
    "prompt": "生成扫地机器人淘宝主页图，2张主图，2张副图 将宽高比设为1:1",
    "response_format": "b64_json",
    "image_size": "1K",
    "aspect_ratio": "1:1",
    "n": 4,
}

print("request_url:", f"{API_BASE}/images/generations")
print("request_n:", payload["n"])
print("timeout:", REQUEST_TIMEOUT)

try:
    resp = requests.post(
        f"{API_BASE}/images/generations",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    result = resp.json()
except requests.exceptions.ReadTimeout as exc:
    raise SystemExit(
        f"请求超时：生成 {payload['n']} 张图片耗时超过 {REQUEST_TIMEOUT[1]} 秒，可继续调大 REQUEST_TIMEOUT 后重试"
    ) from exc

saved_files = []
for index, item in enumerate(result.get("data", []), start=1):
    image_b64 = item["b64_json"]
    image_bytes = base64.b64decode(image_b64)
    output_file = OUTPUT_DIR / f"gpt-image-2-result-{index}.png"
    output_file.write_bytes(image_bytes)
    saved_files.append(str(output_file))

print("saved_files:", saved_files)
print("request_id:", result.get("request_id"))
print("usage:", result.get("usage"))
