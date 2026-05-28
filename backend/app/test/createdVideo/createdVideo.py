import requests
import time
import json
import os
from pathlib import Path
from datetime import datetime

"""
Grok Imagine Video 生成测试脚本

支持：
- 文生视频 (text-to-video)
- 图生视频 (image-to-video，最多 7 张参考图)

注意：
- 文生视频可使用 /v1/chat/completions 流式返回视频 URL
- 图生视频推荐使用 /v1/videos 或系统同步接口 /v1/created/video
- 不要在脚本中硬编码真实 API Key，请通过环境变量传入
"""

# ==================== 配置区 ====================
API_BASE_URL = os.getenv("GROK_VIDEO_API_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("GROK_VIDEO_API_KEY", "")

# 输出目录
OUTPUT_DIR = Path(__file__).parent / "generated_videos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_base_url() -> str:
    """返回不带尾部斜杠的 base URL，避免拼接时出现双斜杠"""
    return API_BASE_URL.rstrip("/")


def get_headers():
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


# ==================== 方法1: Chat Completions 方式（文生视频） ====================
def generate_video_chat_completions(
    prompt: str = "霓虹雨夜街头,电影感慢镜头追拍",
    seconds: int = 10,
    size: str = "1792x1024",
    resolution_name: str = "720p",
    preset: str = "normal",
):
    """文生视频：流式返回视频 URL"""
    url = f"{get_base_url()}/v1/chat/completions"
    payload = {
        "model": "grok-imagine-video",
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "video_config": {
            "seconds": seconds,
            "size": size,
            "resolution_name": resolution_name,
            "preset": preset,
        },
    }

    print("\n=== Chat Completions 文生视频 ===")
    print(f"Prompt: {prompt}")
    print("正在等待流式响应...")

    try:
        with requests.post(url, headers={**get_headers(), "Content-Type": "application/json"}, json=payload, stream=True, timeout=1200) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if line:
                    print(line)
    except requests.exceptions.RequestException as e:
        print(f"❌ 文生视频失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   响应: {e.response.text[:500]}")


# ==================== 方法2: /v1/videos 异步接口（文生视频，推荐） ====================
def generate_video_async(
    prompt: str = "霓虹雨夜街头,电影感慢镜头追拍",
    seconds: str = "10",
    size: str = "1792x1024",
    resolution_name: str = "720p",
    preset: str = "normal",
):
    """文生视频"""
    url = f"{get_base_url()}/v1/videos"

    data = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "seconds": seconds,
        "size": size,
        "resolution_name": resolution_name,
        "preset": preset,
    }

    print(f"\n=== 文生视频 ===")
    print(f"Prompt: {prompt}")
    print(f"参数: seconds={seconds}, size={size}, resolution={resolution_name}, preset={preset}")
    print("正在创建视频任务...")

    try:
        resp = requests.post(url, headers=get_headers(), data=data, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ 创建任务失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   响应: {e.response.text[:500]}")
        return None

    result = resp.json()
    video_id = result.get("id")
    if not video_id:
        print(f"❌ 响应中未返回 video_id: {result}")
        return None

    print(f"✅ 视频任务已创建，ID: {video_id}")
    print(f"   request_id: {result.get('request_id')}")
    usage = result.get("usage", {})
    if usage:
        print(f"   预计扣费: {usage.get('image_credits_charged')} 积分")

    # 轮询查询状态
    return poll_video_status(video_id)


def poll_video_status(video_id: str, poll_interval: int = 5, max_wait_minutes: int = 20):
    """轮询视频任务状态直到完成或失败"""
    status_url = f"{get_base_url()}/v1/videos/{video_id}"
    content_url = f"{get_base_url()}/v1/videos/{video_id}/content"
    headers = get_headers()

    start_time = time.time()
    max_wait = max_wait_minutes * 60
    last_status = None

    print(f"\n开始轮询状态（每 {poll_interval} 秒一次，最多等待 {max_wait_minutes} 分钟）...")

    while True:
        try:
            status_resp = requests.get(status_url, headers=headers, timeout=30)
            status_resp.raise_for_status()
            status_data = status_resp.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  查询状态失败: {e}，5秒后重试...")
            time.sleep(poll_interval)
            continue

        status = status_data.get("status") or status_data.get("state") or "unknown"
        progress = status_data.get("progress")

        if status != last_status:
            ts = datetime.now().strftime("%H:%M:%S")
            progress_str = f" ({progress}%)" if progress is not None else ""
            print(f"[{ts}] 当前状态: {status}{progress_str}")
            last_status = status

        if status in ("completed", "succeeded", "success"):
            print("✅ 视频生成完成，正在下载...")

            try:
                video_resp = requests.get(content_url, headers=headers, allow_redirects=True, timeout=120)
                video_resp.raise_for_status()

                filename = f"grok_video_{video_id}_{int(time.time())}.mp4"
                output_path = OUTPUT_DIR / filename
                output_path.write_bytes(video_resp.content)

                print(f"✅ 视频已保存: {output_path}")
                print(f"   文件大小: {len(video_resp.content) / 1024 / 1024:.2f} MB")
                return str(output_path)
            except requests.exceptions.RequestException as e:
                print(f"❌ 下载视频失败: {e}")
                return None

        elif status in ("failed", "error", "cancelled"):
            print(f"❌ 视频生成失败")
            print(f"   错误信息: {status_data.get('error') or status_data.get('message') or status_data}")
            return None

        if time.time() - start_time > max_wait:
            print(f"⏱️  等待超时（{max_wait_minutes} 分钟），请稍后手动查询状态")
            print(f"   查询命令: curl -H 'Authorization: Bearer {API_KEY}' {status_url}")
            return None

        time.sleep(poll_interval)


# ==================== 方法3: 图生视频（支持最多 7 张参考图） ====================
def image_to_video(
    prompt: str = "让这张图片动起来，添加电影感的运镜效果",
    image_paths: list = None,
    seconds: str = "20",
    size: str = "720x1280",
    resolution_name: str = "720p",
    preset: str = "normal",
):
    """图生视频（支持 1~7 张参考图）"""
    url = f"{get_base_url()}/v1/videos"
    headers = get_headers()

    data = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "seconds": seconds,
        "size": size,
        "resolution_name": resolution_name,
        "preset": preset,
    }

    files = []
    if image_paths:
        for i, img_path in enumerate(image_paths[:7]):
            p = Path(img_path)
            if not p.exists():
                print(f"⚠️  参考图不存在，跳过: {img_path}")
                continue
            # 注意：字段名必须是 input_reference[]（列表形式）
            files.append(
                ("input_reference[]", (p.name, p.read_bytes(), "image/png"))
            )
        if not files:
            print("❌ 没有有效的参考图片，图生视频取消")
            return None

    print(f"\n=== 图生视频 ===")
    print(f"Prompt: {prompt}")
    print(f"参考图数量: {len(files)}")
    print(f"参数: seconds={seconds}, size={size}, resolution={resolution_name}, preset={preset}")
    print("正在创建视频任务...")

    try:
        resp = requests.post(url, headers=headers, data=data, files=files or None, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ 创建任务失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   响应: {e.response.text[:800]}")
        return None

    result = resp.json()
    video_id = result.get("id")
    if not video_id:
        print(f"❌ 响应中未返回 video_id: {result}")
        return None

    print(f"✅ 视频任务已创建，ID: {video_id}")

    return poll_video_status(video_id)


# ==================== 便捷查询工具 ====================
def get_video_status(video_id: str):
    """手动查询单个视频任务状态"""
    url = f"{get_base_url()}/v1/videos/{video_id}"
    resp = requests.get(url, headers=get_headers(), timeout=30)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))


def download_video(video_id: str, output_name: str = None):
    """直接下载已完成的视频"""
    url = f"{get_base_url()}/v1/videos/{video_id}/content"
    resp = requests.get(url, headers=get_headers(), allow_redirects=True, timeout=120)
    resp.raise_for_status()

    if output_name is None:
        output_name = f"grok_video_{video_id}_{int(time.time())}.mp4"

    output_path = OUTPUT_DIR / output_name
    output_path.write_bytes(resp.content)
    print(f"✅ 已下载: {output_path}")
    return str(output_path)


# ==================== 主入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("Grok Imagine Video 测试脚本")
    print(f"API Base: {get_base_url()}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    # 选择你要测试的方法（取消注释即可）

    # 方法1（当前不支持）
    generate_video_chat_completions()

    # 方法2: 文生视频（最常用）
    # generate_video_async(
    #     prompt="霓虹雨夜街头,电影感慢镜头追拍",
    #     seconds="10",
    #     size="1792x1024",
    #     resolution_name="720p",
    #     preset="normal",
    # )

    # 方法3: 图生视频（使用你提供的图片）
    ref_image = Path(__file__).parent / "reference_images" / "beauty.png"
    if not ref_image.exists():
        print(f"\n❌ 参考图片不存在！")
        print(f"   请将你上传的图片保存到：{ref_image}")
        print("   然后重新运行脚本。\n")
    else:
        image_to_video(
            prompt="让参考图中的人物自然跳舞，电影感镜头推进",
            image_paths=[str(ref_image)],
            seconds="20",
            size="720x1280",
            resolution_name="720p",
            preset="normal",
        )

    # 工具函数示例（手动查询或下载）
    # get_video_status("video_xxx")
    # download_video("video_xxx")

    print("\n✅ 脚本已配置为「图生视频」模式")
    print("   提示词：「让参考图中的人物自然跳舞，电影感镜头推进」")
    print("   视频参数：竖屏 9:16 (720x1280) / 20秒 / 720p")
    print("   参考图路径已指向：reference_images/beauty.png")
