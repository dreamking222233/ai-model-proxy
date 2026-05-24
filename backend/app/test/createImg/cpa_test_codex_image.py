import requests
import base64
from datetime import datetime
import os

# ==================== 配置 ====================
# API_BASE_URL = "http://43.128.147.93:8317/v1"
API_BASE_URL = "http://43.135.136.15:8317/v1"
# API_BASE_URL = "http://43.156.153.12:8317/v1"

# API_KEY = "sk-xiaoleai"
API_KEY = "sk-bH4MiRFTJnvYaiXrR"
# API_KEY = "sk-uWQMveW4dEb4TCxMJ"
REQUEST_TIMEOUT = 600

# 创建保存目录
SAVE_DIR = "generated_images"
os.makedirs(SAVE_DIR, exist_ok=True)


def generate_images(
    prompt: str,
    n: int = 1,
    size: str = "1024x1792",
    quality: str = "high",
    timeout: int = REQUEST_TIMEOUT,
):
    """
    调用 gpt-image-2 生成图片并保存到本地
    """
    url = f"{API_BASE_URL}/images/generations"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "response_format": "b64_json"
    }

    print(f"🚀 开始生成 {n} 张图片，比例 {size}，超时 {timeout} 秒...")
    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout)
    except requests.exceptions.ReadTimeout:
        print(f"❌ 请求超时，已等待 {timeout} 秒仍未返回结果")
        return None

    if response.status_code == 200:
        result = response.json()
        if "data" in result and len(result["data"]) > 0:
            print(f"✅ API 返回成功，共 {len(result['data'])} 张图片")
            for i, item in enumerate(result["data"], 1):
                b64_data = item.get("b64_json", "")
                b64_preview = b64_data[:50] + "..." if b64_data else "无数据"
                print(f"   图片 {i}: base64 长度 {len(b64_data)} 字符，预览: {b64_preview}")


        if "data" in result and len(result["data"]) > 0:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            saved_files = []

            for i, item in enumerate(result["data"], 1):
                try:
                    b64_data = item["b64_json"]
                    image_data = base64.b64decode(b64_data)

                    filename = f"{SAVE_DIR}/gptimage_{size.replace('x', '_')}_{timestamp}_{i:02d}.png"

                    with open(filename, "wb") as f:
                        f.write(image_data)

                    saved_files.append(filename)
                    print(f"✅ 第 {i}/{n} 张保存完成: {filename}")

                except Exception as e:
                    print(f"❌ 保存第 {i} 张图片失败: {e}")

            print(f"\n🎉 全部完成！共保存 {len(saved_files)} 张图片")
            return saved_files
        else:
            print("⚠️ 返回数据中没有图片")
            return None
    else:
        print(f"❌ 请求失败 ({response.status_code})")
        print(response.text)
        return None


if __name__ == "__main__":
    # ==================== 测试调用 ====================
    prompt = """
    生成一张抖音直播间截图
    """
    # 生成 1 张竖屏图片（9:16）
    generate_images(prompt, n=1, size="3840x2160")
