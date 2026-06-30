#!/usr/bin/env python3
"""Test XiaoLeAI platform video generation with a reference image.

Run:
    XIAOLEAI_API_KEY="sk-..." python backend/app/test/test_xiaoleai_video.py

Optional:
    XIAOLEAI_BASE_URL="https://api.xiaoleai.team"
    XIAOLEAI_VIDEO_MODEL="video-ds-2.0-fast"
    XIAOLEAI_REFERENCE_IMAGE="/path/to/reference.png"
    XIAOLEAI_VIDEO_PROMPT="..."
    XIAOLEAI_VIDEO_SIZE="1280x720"
    XIAOLEAI_VIDEO_SECONDS="15"
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output_xiaoleai_video"

XIAOLEAI_BASE_URL = os.getenv("XIAOLEAI_BASE_URL", "https://api.xiaoleai.team").rstrip("/")
XIAOLEAI_API_KEY = os.getenv("XIAOLEAI_API_KEY", "")
VIDEO_MODEL = os.getenv("XIAOLEAI_VIDEO_MODEL", "video-ds-2.0-fast")
REFERENCE_IMAGE_PATH = Path(os.getenv("XIAOLEAI_REFERENCE_IMAGE", str(BASE_DIR / "image.png")))
VIDEO_SIZE = os.getenv("XIAOLEAI_VIDEO_SIZE", "1280x720")
VIDEO_SECONDS = int(os.getenv("XIAOLEAI_VIDEO_SECONDS", "15"))
POLL_INTERVAL_SECONDS = float(os.getenv("XIAOLEAI_POLL_INTERVAL_SECONDS", "5"))
TIMEOUT_SECONDS = int(os.getenv("XIAOLEAI_TIMEOUT_SECONDS", "1200"))

DEFAULT_PROMPT = """
参考图是同一个20岁出头中国男性的正面、侧面、背面人物设定，只用于锁定主角外貌和服装；视频里只出现一个主角，不要把参考图中的三视图生成成三个人。
生成一段15秒中文现实主义短剧视频，作为短剧第1段，单一连续镜头，不要硬切。
主角保持参考图外貌：短黑发、清瘦、白色T恤、浅灰色连帽衫，普通上班族气质。
场景是夜晚狭小但干净的出租屋，旧书桌、笔记本电脑、外卖盒、几张彩票、台灯暖光和电脑冷光。
镜头从中近景开始，主角趴在桌边睡着，手边压着彩票。镜头缓慢推近，他在梦中听到彩票开奖般的模糊声音，突然坐直，紧张核对彩票号码。
他的表情从困倦、怀疑、震惊变成狂喜，手颤抖着举起彩票，像确认自己中了1个亿人民币。
为了让下一段平滑转场，最后3秒让台灯和电脑光慢慢变成梦境般金色光晕，背景轻微虚化，主角抬头望向画面右侧，脸上保持狂喜和不敢相信。
整体风格：电影感写实短剧，动作自然，镜头稳定，情绪递进清晰，保留可用于下一段衔接的清晰末帧。
避免：不要字幕，不要旁白文字，不要水印，不要真实彩票品牌，不要把三视图当三个人，不要多主角，不要血腥暴力，不要色情裸露，不要毒品。
""".strip()
VIDEO_PROMPT = os.getenv("XIAOLEAI_VIDEO_PROMPT", DEFAULT_PROMPT)

COMPLETED_STATUSES = {"completed", "succeeded", "success", "done"}
FAILED_STATUSES = {"failed", "error", "cancelled", "canceled", "expired"}


def require_api_key() -> str:
    api_key = XIAOLEAI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("Missing XIAOLEAI_API_KEY environment variable")
    return api_key


def api_url(path: str) -> str:
    normalized_path = "/" + str(path or "").lstrip("/")
    if XIAOLEAI_BASE_URL.endswith("/v1") and normalized_path.startswith("/v1/"):
        normalized_path = normalized_path[3:]
    return f"{XIAOLEAI_BASE_URL}{normalized_path}"


def request_json(method: str, path_or_url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    url = path_or_url if path_or_url.startswith(("http://", "https://")) else api_url(path_or_url)
    request_headers = {
        "Authorization": f"Bearer {require_api_key()}",
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc


def encode_multipart_form(
    fields: dict[str, str],
    files: list[tuple[str, Path]],
) -> tuple[bytes, str]:
    boundary = f"----xiaoleai-video-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
            str(value).encode("utf-8"),
            b"\r\n",
        ])

    for field_name, file_path in files:
        path = file_path.expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Reference image not found: {path}")
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if not content_type.startswith("image/"):
            raise ValueError(f"Reference file must be an image: {path} ({content_type})")
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            path.read_bytes(),
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def create_video() -> dict:
    body, content_type = encode_multipart_form(
        fields={
            "model": VIDEO_MODEL,
            "prompt": VIDEO_PROMPT,
            "seconds": str(VIDEO_SECONDS),
            "size": VIDEO_SIZE,
        },
        files=[
            ("input_reference[]", REFERENCE_IMAGE_PATH),
        ],
    )
    response = request_json(
        "POST",
        "/v1/videos",
        body=body,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        },
    )
    video_id = str(response.get("id") or response.get("task_id") or response.get("request_id") or "").strip()
    if not video_id:
        raise RuntimeError(f"Missing video id in create response: {response}")
    response["id"] = video_id
    return response


def wait_video(video_id: str) -> dict:
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        response = request_json("GET", f"/v1/videos/{urllib.parse.quote(video_id, safe='')}")
        status = str(response.get("status") or response.get("state") or "").strip().lower()
        print(f"{video_id} status={status} progress={response.get('progress')}")
        if status in COMPLETED_STATUSES or status in FAILED_STATUSES:
            return response
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Video task timed out: {video_id}")


def resolve_content_url(video_id: str, status_body: dict) -> str:
    content_url = str(status_body.get("content_url") or "").strip()
    if content_url:
        if content_url.startswith(("http://", "https://")):
            return content_url
        return api_url(content_url)
    return api_url(f"/v1/videos/{urllib.parse.quote(video_id, safe='')}/content")


def download_video_content(video_id: str, status_body: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{video_id}.mp4"
    content_url = resolve_content_url(video_id, status_body)
    request = urllib.request.Request(
        content_url,
        headers={
            "Authorization": f"Bearer {require_api_key()}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            content_type = response.headers.get("content-type", "")
            data = response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Download HTTP {exc.code}: {error_body}") from exc

    if not data:
        raise RuntimeError("Downloaded video content is empty")
    if "application/json" in content_type.lower() or content_type.lower().startswith("text/"):
        preview = data[:1000].decode("utf-8", errors="replace")
        raise RuntimeError(f"Content endpoint returned non-video content_type={content_type}: {preview}")

    output_path.write_bytes(data)
    print(f"downloaded={output_path}")
    print(f"content_type={content_type}")
    print(f"content_length={len(data)}")
    return output_path


def generate_video() -> dict:
    print(f"base_url={XIAOLEAI_BASE_URL}")
    print(f"model={VIDEO_MODEL} seconds={VIDEO_SECONDS} size={VIDEO_SIZE}")
    print(f"reference_image={REFERENCE_IMAGE_PATH}")

    created = create_video()
    video_id = str(created["id"])
    print("create_response=")
    print(json.dumps(created, ensure_ascii=False, indent=2))

    final_status = wait_video(video_id)
    print("final_status=")
    print(json.dumps(final_status, ensure_ascii=False, indent=2))

    status = str(final_status.get("status") or final_status.get("state") or "").strip().lower()
    if status not in COMPLETED_STATUSES:
        raise RuntimeError(f"Video generation failed or incomplete: {final_status}")

    output_path = download_video_content(video_id, final_status)
    result = {
        "id": video_id,
        "model": VIDEO_MODEL,
        "seconds": VIDEO_SECONDS,
        "size": VIDEO_SIZE,
        "reference_image": str(REFERENCE_IMAGE_PATH),
        "output_path": str(output_path),
        "output_size_bytes": output_path.stat().st_size,
        "created": created,
        "final_status": final_status,
    }
    print("result=")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    generate_video()
    return 0


def test_xiaoleai_video_generation() -> None:
    """Pytest entrypoint for PyCharm's pytest runner."""
    assert main() == 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
