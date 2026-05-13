import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


# ================== 配置 ====================
API_BASE_URL = "http://43.128.147.93:8317/v1"
API_KEY = "sk-xiaoleai"
REQUEST_TIMEOUT = 600
SAVE_DIR = Path(__file__).resolve().parent / "generated_images"
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def edit_image(image_path: str, prompt: str, size: str = "2160x3840") -> Optional[str]:
    """
    调用 gpt-image-2 编辑图片并保存到本地。

    Args:
        image_path: 原始图片路径
        prompt: 编辑提示词
        size: 输出分辨率，默认竖屏 9:16 4K
    """
    url = f"{API_BASE_URL.rstrip('/')}/images/edits"
    image_file = Path(image_path).expanduser()
    if not image_file.exists():
        raise FileNotFoundError(f"原始图片不存在: {image_file}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
    }

    data = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }

    print("request_url:", url)
    print("image_path:", str(image_file))
    print("payload:", json.dumps(data, ensure_ascii=False, indent=2))

    with image_file.open("rb") as f:
        files = {
            "image": (image_file.name, f, "image/png"),
        }
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"图片编辑请求失败 (HTTP {response.status_code}):\n{response.text}"
        )

    result = response.json()
    items = result.get("data") or []
    if not items:
        raise RuntimeError(
            f"接口返回成功，但没有图片数据:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    first_item = items[0]
    b64_json = first_item.get("b64_json")
    if not b64_json:
        raise RuntimeError(
            f"接口返回成功，但 data[0] 没有 b64_json:\n{json.dumps(result, ensure_ascii=False, indent=2)}"
        )

    image_bytes = base64.b64decode(b64_json)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = SAVE_DIR / f"edited_{size.replace('x', '_')}_{timestamp}.png"
    output_file.write_bytes(image_bytes)

    print("\n请求成功")
    print("request_id:", result.get("request_id"))
    print("usage:", json.dumps(result.get("usage") or {}, ensure_ascii=False, indent=2))
    print("saved_file:", str(output_file))
    return str(output_file)


if __name__ == "__main__":
    # 竖屏 9:16 4K 分辨率示例
    edit_image(
        image_path=str(SAVE_DIR / "/Volumes/project/modelInvocationSystem/backend/app/test/createImg/generated_images/img.png"),
        prompt="根据这张图片制作一个logo",
        size="3840x2160",
    )
