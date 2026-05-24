import requests
import base64
from datetime import datetime
from pathlib import Path

API_BASE_URL = "http://43.156.153.12:8317/v1"
API_KEY = "sk-uWQMveW4dEb4TCxMJ"  # 你的 API key
OUTPUT_DIR = Path("./generated_images")


def generate_images(prompt, n=1, size="1024x1024"):
    OUTPUT_DIR.mkdir(exist_ok=True)
    url = f"{API_BASE_URL}/images/generations"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    saved_files = []
    for i in range(1, n + 1):
        print(f"正在生成第 {i}/{n} 张...")
        data = {
            "model": "gpt-image-2",
            "prompt": prompt,
            "size": size,
            "response_format": "b64_json"
        }

        response = requests.post(url, headers=headers, json=data, timeout=60)
        if response.status_code == 200:
            result = response.json()
            b64_data = result["data"][0]["b64_json"]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            image_file = OUTPUT_DIR / f"img_{timestamp}.png"
            with open(image_file, "wb") as f:
                f.write(base64.b64decode(b64_data))
            saved_files.append(str(image_file))
            print(f"✓ 已保存: {image_file.name}")
        else:
            print(f"✗ 错误 ({response.status_code}): {response.text}")

    return saved_files


# 测试
generate_images("一只可爱的橘猫在阳光下睡觉", n=1)