"""Pure mapping helpers for the grok-imagine image/video upstream.

ProxyService owns HTTP, billing, and routing. This module is the shipped
request-build / normalize / URL-join / status / poll-deadline surface.
"""
from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from urllib.parse import urlparse

from app.core.exceptions import ServiceException

PROVIDER_VARIANT = "grok-imagine"
POLL_TIMEOUT_SECONDS = 600
CONTENT_HTTP_METHOD = "GET"
VIDEO_STATUS_HTTP_OK = frozenset({200, 202})

IMAGE_MODEL_V1 = "grok-imagine-image"
IMAGE_MODEL_V2 = "grok-imagine-image-2.0"
VIDEO_MODEL_V1 = "grok-imagine-video"
VIDEO_MODEL_V15 = "grok-imagine-video-1.5"
FORBIDDEN_MODEL_SLUG = "grok-image-video"
ALLOWED_MODEL_SLUGS = {
    IMAGE_MODEL_V1,
    IMAGE_MODEL_V2,
    VIDEO_MODEL_V1,
    VIDEO_MODEL_V15,
}

IMAGE_ASPECT_RATIOS = (
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "2:1",
    "1:2",
    "19.5:9",
    "9:19.5",
    "20:9",
    "9:20",
    "21:9",
    "5:2",
    "auto",
)
VIDEO_ASPECT_RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3")
VIDEO_ASPECT_RATIO_SIZE_MAP = {
    "1:1": "1024x1024",
    "16:9": "1280x720",
    "9:16": "720x1280",
    "4:3": "960x720",
    "3:4": "720x960",
    "3:2": "1080x720",
    "2:3": "720x1080",
}
IMAGE_QUALITY_V2 = ("low", "medium", "auto")
VIDEO_RESOLUTIONS_T2V_I2V_V15 = ("480p", "720p", "1080p")
VIDEO_RESOLUTIONS_V1 = ("480p", "720p")
VIDEO_RESOLUTIONS_R2V = ("480p", "720p")
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_EDIT_IMAGES = 5
MAX_R2V_IMAGES = 7
DEFAULT_IMAGE_RESOLUTION = "1k"
DEFAULT_VIDEO_RESOLUTION = "480p"
DEFAULT_VIDEO_ASPECT_RATIO = "16:9"
DEFAULT_VIDEO_DURATION = 8
DEFAULT_IMAGE_ASPECT_RATIO = "auto"
DEFAULT_IMAGE_QUALITY_V2 = "auto"

_CONTINUE_STATUSES = {"pending", "queued", "in_progress", "processing", "running", "submitted", "not_start"}
_COMPLETED_STATUSES = {"completed", "succeeded", "success", "done"}
_FAILED_STATUSES = {"failed", "error", "cancelled", "canceled", "expired"}


def _raise(detail: str, error_code: str, status_code: int = 400) -> None:
    raise ServiceException(status_code, detail, error_code)


def is_grok_imagine_variant(provider_variant: Optional[str]) -> bool:
    return str(provider_variant or "").strip().lower() == PROVIDER_VARIANT


def is_video_status_http_ok(status_code: Any) -> bool:
    try:
        return int(status_code) in VIDEO_STATUS_HTTP_OK
    except (TypeError, ValueError):
        return False


def pending_video_status_body(video_id: Optional[str] = None) -> dict[str, Any]:
    request_id = str(video_id or "").strip()
    body: dict[str, Any] = {"status": "pending"}
    if request_id:
        body["id"] = request_id
        body["request_id"] = request_id
    return body


def normalize_upstream_model_slug(model_name: Optional[str]) -> str:
    slug = str(model_name or "").strip()
    if not slug:
        _raise("缺少必填字段：model", "INVALID_MODEL")
    if slug == FORBIDDEN_MODEL_SLUG or slug.replace("_", "-") == FORBIDDEN_MODEL_SLUG:
        _raise("模型名无效，请使用 grok-imagine-video 或 grok-imagine-video-1.5", "INVALID_MODEL")
    if slug not in ALLOWED_MODEL_SLUGS:
        _raise(
            "模型名无效，仅支持 grok-imagine-image、grok-imagine-image-2.0、grok-imagine-video、grok-imagine-video-1.5",
            "INVALID_MODEL",
        )
    return slug


def is_image_v2(model_name: Optional[str]) -> bool:
    return normalize_upstream_model_slug(model_name) == IMAGE_MODEL_V2


def is_video_v15(model_name: Optional[str]) -> bool:
    slug = str(model_name or "").strip()
    return slug == VIDEO_MODEL_V15


def _origin_and_v1(base_url: str) -> tuple[str, str]:
    normalized = str(base_url or "").rstrip("/")
    if not normalized:
        _raise("渠道 Base URL 无效", "INVALID_CHANNEL_BASE_URL")
    if normalized.endswith("/v1"):
        origin = normalized[: -len("/v1")].rstrip("/")
        return origin, normalized
    return normalized, f"{normalized}/v1"


def resolve_image_generations_url(base_url: str) -> str:
    return f"{_origin_and_v1(base_url)[1]}/images/generations"


def resolve_image_edits_url(base_url: str) -> str:
    return f"{_origin_and_v1(base_url)[1]}/images/edits"


def resolve_video_create_url(base_url: str) -> str:
    return f"{_origin_and_v1(base_url)[1]}/videos/generations"


def resolve_video_retrieve_url(base_url: str, request_id: str) -> str:
    video_id = str(request_id or "").strip()
    if not video_id:
        _raise("缺少视频任务 ID", "INVALID_VIDEO_ID")
    return f"{_origin_and_v1(base_url)[1]}/videos/{video_id}"


def join_content_url(
    base_url: str,
    maybe_url: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    raw = str(maybe_url or "").strip()
    origin, v1_base = _origin_and_v1(base_url)
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        return f"{origin}{raw}"
    if raw:
        return f"{v1_base}/{raw.lstrip('/')}"
    video_id = str(request_id or "").strip()
    if not video_id:
        _raise("缺少视频内容地址", "INVALID_VIDEO_CONTENT_URL")
    return f"{v1_base}/videos/{video_id}/content"


def content_probe_request(
    base_url: str,
    maybe_url: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict[str, str]:
    """Shipped content probe: GET the joined URL. Never HEAD on this channel."""
    return {
        "method": CONTENT_HTTP_METHOD,
        "url": join_content_url(base_url, maybe_url, request_id),
    }


def normalize_image_resolution(value: Any) -> str:
    raw = str(value or DEFAULT_IMAGE_RESOLUTION).strip()
    compact = raw.replace(" ", "")
    aliases = {
        "1k": "1k",
        "1K": "1k",
        "2k": "2k",
        "2K": "2k",
    }
    if compact not in aliases:
        _raise("resolution 仅支持 1k 或 2k", "INVALID_IMAGE_SIZE")
    return aliases[compact]


def normalize_image_aspect_ratio(value: Any) -> str:
    raw = str(value or DEFAULT_IMAGE_ASPECT_RATIO).strip()
    if raw not in IMAGE_ASPECT_RATIOS:
        _raise(
            f"aspect_ratio 仅支持：{'、'.join(IMAGE_ASPECT_RATIOS)}",
            "INVALID_IMAGE_ASPECT_RATIO",
        )
    return raw


def normalize_image_n(value: Any) -> int:
    if value in (None, ""):
        return 1
    try:
        count = int(value)
    except (TypeError, ValueError):
        _raise("n 参数无效", "IMAGE_COUNT_NOT_SUPPORTED")
    if count < 1 or count > 10:
        _raise("n 仅支持 1 到 10", "IMAGE_COUNT_NOT_SUPPORTED")
    return count


def normalize_image_quality(model_name: Optional[str], value: Any) -> Optional[str]:
    slug = normalize_upstream_model_slug(model_name)
    raw = str(value or "").strip().lower()
    if slug != IMAGE_MODEL_V2:
        return None
    if not raw:
        return DEFAULT_IMAGE_QUALITY_V2
    if raw not in IMAGE_QUALITY_V2:
        _raise("quality 仅支持 low、medium、auto", "INVALID_IMAGE_QUALITY")
    return raw


def image_bytes_to_data_url(content: bytes, content_type: Optional[str] = None) -> str:
    if not isinstance(content, (bytes, bytearray)) or not content:
        _raise("上传的图片文件不能为空", "INVALID_IMAGE_FILE")
    mime = str(content_type or "image/png").strip().lower() or "image/png"
    if mime == "image/jpg":
        mime = "image/jpeg"
    if mime not in ALLOWED_IMAGE_MIME_TYPES:
        _raise("参考图仅支持 JPEG、PNG、WebP", "INVALID_IMAGE_FILE")
    encoded = base64.b64encode(bytes(content)).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _image_input_object(source: dict[str, Any]) -> dict[str, str]:
    if source.get("url"):
        return {"url": str(source["url"]), "type": str(source.get("type") or "image_url")}
    return {
        "url": image_bytes_to_data_url(source.get("content") or b"", source.get("content_type")),
        "type": "image_url",
    }


def build_image_generation_payload(
    *,
    model: str,
    prompt: str,
    n: Any = 1,
    aspect_ratio: Any = None,
    resolution: Any = None,
    quality: Any = None,
    response_format: str = "b64_json",
) -> dict[str, Any]:
    slug = normalize_upstream_model_slug(model)
    text = str(prompt or "").strip()
    if not text:
        _raise("缺少必填字段：prompt", "INVALID_IMAGE_PROMPT")
    payload: dict[str, Any] = {
        "model": slug,
        "prompt": text,
        "n": normalize_image_n(n),
        "aspect_ratio": normalize_image_aspect_ratio(aspect_ratio),
        "resolution": normalize_image_resolution(resolution),
        "response_format": response_format or "b64_json",
    }
    quality_value = normalize_image_quality(slug, quality)
    if quality_value:
        payload["quality"] = quality_value
    return payload


def build_image_edit_payload(
    *,
    model: str,
    prompt: str,
    images: list[dict[str, Any]],
    n: Any = 1,
    aspect_ratio: Any = None,
    resolution: Any = None,
    quality: Any = None,
    response_format: str = "b64_json",
) -> dict[str, Any]:
    slug = normalize_upstream_model_slug(model)
    text = str(prompt or "").strip()
    if not text:
        _raise("缺少必填字段：prompt", "INVALID_IMAGE_PROMPT")
    files = [item for item in (images or []) if isinstance(item, dict)]
    if not files:
        _raise("缺少必填字段：image", "INVALID_IMAGE_FILE")
    if len(files) > MAX_EDIT_IMAGES:
        _raise(f"参考图最多支持 {MAX_EDIT_IMAGES} 张", "TOO_MANY_IMAGE_REFERENCES")
    payload: dict[str, Any] = {
        "model": slug,
        "prompt": text,
        "n": normalize_image_n(n),
        "response_format": response_format or "b64_json",
    }
    if aspect_ratio not in (None, ""):
        payload["aspect_ratio"] = normalize_image_aspect_ratio(aspect_ratio)
    if resolution not in (None, ""):
        payload["resolution"] = normalize_image_resolution(resolution)
    quality_value = normalize_image_quality(slug, quality)
    if quality_value:
        payload["quality"] = quality_value
    objects = [_image_input_object(item) for item in files]
    if len(objects) == 1:
        payload["image"] = objects[0]
    else:
        payload["images"] = objects
    if "image" in payload and "images" in payload:
        _raise("image 与 images 不能同时使用", "INVALID_IMAGE_FILE")
    return payload


def normalize_video_mode(raw_mode: Any, reference_count: int) -> str:
    mode = str(raw_mode or "").strip().lower()
    count = int(reference_count or 0)
    if not mode:
        if count <= 0:
            return "t2v"
        _raise("请指定 video_mode：t2v、i2v 或 r2v", "VIDEO_MODE_REQUIRED")
    if mode in {"text", "t2v"}:
        mode = "t2v"
    elif mode in {"i2v", "image", "first_frame"}:
        mode = "i2v"
    elif mode in {"r2v", "reference"}:
        mode = "r2v"
    else:
        _raise("video_mode 仅支持 t2v、i2v、r2v", "INVALID_VIDEO_MODE")
    if mode == "t2v" and count > 0:
        _raise("文生视频不能上传参考图", "INVALID_VIDEO_REFERENCE")
    if mode == "i2v" and count != 1:
        _raise("图生视频必须恰好上传 1 张参考图作为第一帧", "INVALID_VIDEO_REFERENCE")
    if mode == "r2v" and count < 1:
        _raise("参考生视频至少上传 1 张参考图", "INVALID_VIDEO_REFERENCE")
    if mode == "r2v" and count > MAX_R2V_IMAGES:
        _raise(f"参考生视频最多支持 {MAX_R2V_IMAGES} 张参考图", "TOO_MANY_VIDEO_REFERENCES")
    return mode


def normalize_video_duration(model_name: Optional[str], mode: str, value: Any) -> int:
    if value in (None, ""):
        seconds = DEFAULT_VIDEO_DURATION
    else:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            _raise("seconds 参数无效", "INVALID_VIDEO_SECONDS")
    if seconds < 1 or seconds > 15:
        _raise("seconds 仅支持 1 到 15", "INVALID_VIDEO_SECONDS")
    slug = str(model_name or "").strip()
    if mode == "r2v" and slug == VIDEO_MODEL_V1 and seconds > 10:
        _raise("grok-imagine-video 参考生视频最长 10 秒", "INVALID_VIDEO_SECONDS")
    return seconds


def normalize_video_aspect_ratio(value: Any) -> str:
    raw = str(value or DEFAULT_VIDEO_ASPECT_RATIO).strip()
    if raw not in VIDEO_ASPECT_RATIOS:
        _raise(
            f"aspect_ratio 仅支持：{'、'.join(VIDEO_ASPECT_RATIOS)}",
            "INVALID_VIDEO_SIZE",
        )
    return raw


def normalize_video_resolution(model_name: Optional[str], mode: str, value: Any) -> str:
    raw = str(value or DEFAULT_VIDEO_RESOLUTION).strip().lower()
    slug = str(model_name or "").strip()
    if mode == "r2v":
        allowed = VIDEO_RESOLUTIONS_R2V
    elif slug == VIDEO_MODEL_V15:
        allowed = VIDEO_RESOLUTIONS_T2V_I2V_V15
    else:
        allowed = VIDEO_RESOLUTIONS_V1
    if raw not in allowed:
        _raise(
            f"resolution 仅支持：{'、'.join(allowed)}",
            "INVALID_VIDEO_RESOLUTION",
        )
    return raw


def log_size_from_aspect_ratio(aspect_ratio: str) -> str:
    return VIDEO_ASPECT_RATIO_SIZE_MAP.get(aspect_ratio, "1280x720")


def build_video_generation_payload(
    *,
    model: str,
    prompt: str,
    mode: Any,
    reference_data_urls: Optional[list[str]] = None,
    seconds: Any = None,
    aspect_ratio: Any = None,
    resolution: Any = None,
) -> dict[str, Any]:
    slug = normalize_upstream_model_slug(model)
    urls = [str(item).strip() for item in (reference_data_urls or []) if str(item).strip()]
    video_mode = normalize_video_mode(mode, len(urls))
    text = str(prompt or "").strip()
    if video_mode != "i2v" and not text:
        _raise("缺少必填字段：prompt", "INVALID_VIDEO_PROMPT")
    payload: dict[str, Any] = {
        "model": slug,
        "duration": normalize_video_duration(slug, video_mode, seconds),
        "aspect_ratio": normalize_video_aspect_ratio(aspect_ratio),
        "resolution": normalize_video_resolution(slug, video_mode, resolution),
    }
    if text:
        payload["prompt"] = text
    if video_mode == "i2v":
        payload["image"] = {"url": urls[0]}
    elif video_mode == "r2v":
        payload["reference_images"] = [{"url": item} for item in urls]
    if "image" in payload and "reference_images" in payload:
        _raise("image 与 reference_images 不能同时使用", "INVALID_VIDEO_REFERENCE")
    return payload


def normalize_video_status(status: Any) -> str:
    raw = str(status or "").strip().lower()
    if raw in _COMPLETED_STATUSES:
        return "completed"
    if raw in _FAILED_STATUSES:
        return "expired" if raw == "expired" else "failed"
    if raw in _CONTINUE_STATUSES or not raw:
        return "pending"
    return raw or "pending"


def extract_request_id(body: dict[str, Any]) -> str:
    if not isinstance(body, dict):
        return ""
    for key in ("request_id", "id", "task_id"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_progress(body: dict[str, Any]) -> Any:
    if not isinstance(body, dict):
        return None
    if body.get("progress") in (None, ""):
        return None
    return body.get("progress")


def extract_video_url(body: dict[str, Any]) -> str:
    if not isinstance(body, dict):
        return ""
    video = body.get("video") if isinstance(body.get("video"), dict) else {}
    for value in (
        video.get("url") if isinstance(video, dict) else None,
        body.get("video_url"),
        body.get("url"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_video_create_response(
    body: dict[str, Any],
    *,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    seconds: Optional[int] = None,
    size: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
) -> dict[str, Any]:
    request_id = extract_request_id(body if isinstance(body, dict) else {})
    if not request_id:
        _raise("视频任务创建成功，但未返回 request_id", "OPENAI_VIDEO_GENERATION_FAILED", 503)
    status = normalize_video_status((body or {}).get("status") or "pending")
    normalized: dict[str, Any] = {
        "object": "video",
        "id": request_id,
        "request_id": request_id,
        "model": model or (body or {}).get("model") or "",
        "status": status,
    }
    progress = extract_progress(body or {})
    if progress not in (None, ""):
        normalized["progress"] = progress
    if prompt is not None:
        normalized["prompt"] = prompt
    if seconds is not None:
        normalized["seconds"] = str(seconds)
    if size is not None:
        normalized["size"] = size
    if aspect_ratio is not None:
        normalized["aspect_ratio"] = aspect_ratio
    if resolution is not None:
        normalized["resolution"] = resolution
    return normalized


def normalize_video_status_response(
    body: dict[str, Any],
    *,
    video_id: Optional[str] = None,
    channel_base_url: Optional[str] = None,
) -> dict[str, Any]:
    data = body if isinstance(body, dict) else {}
    request_id = extract_request_id(data) or str(video_id or "").strip()
    status = normalize_video_status(data.get("status"))
    normalized: dict[str, Any] = {
        "object": "video",
        "id": request_id,
        "request_id": request_id,
        "status": status,
        "model": data.get("model") or "",
    }
    progress = extract_progress(data)
    if progress not in (None, ""):
        normalized["progress"] = progress
    if isinstance(data.get("error"), (dict, str)):
        normalized["error"] = data.get("error")
        if status not in _FAILED_STATUSES and status != "failed":
            normalized["status"] = "failed"
    video_url = extract_video_url(data)
    if video_url and channel_base_url:
        normalized["video_url"] = join_content_url(channel_base_url, video_url, request_id)
    elif video_url:
        parsed = urlparse(video_url)
        if parsed.scheme in {"http", "https"}:
            normalized["video_url"] = video_url
        elif request_id:
            # Keep relative until caller joins with channel base.
            normalized["video_url"] = video_url
    return normalized


def should_continue_polling(
    status: Any,
    elapsed_seconds: float,
    timeout_seconds: float = POLL_TIMEOUT_SECONDS,
) -> bool:
    if float(elapsed_seconds) >= float(timeout_seconds):
        return False
    normalized = normalize_video_status(status)
    if normalized in {"completed", "failed", "expired"}:
        return False
    return True


def poll_timeout_seconds() -> int:
    return POLL_TIMEOUT_SECONDS


def resolve_video_credit_total(adjusted_rate: Any) -> Decimal:
    """Charge a flat per-video credit amount; duration does not multiply cost."""
    try:
        amount = Decimal(str(adjusted_rate or 0)).quantize(Decimal("0.001"))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0.000")
    return amount


def image_workbench_capabilities(model_name: Optional[str]) -> dict[str, Any]:
    slug = str(model_name or "").strip()
    quality_options = list(IMAGE_QUALITY_V2) if slug == IMAGE_MODEL_V2 else []
    return {
        "supports_text_to_image": True,
        "supports_edit": True,
        "resolution_options": ["1K", "2K"],
        "quality_options": quality_options,
        "aspect_ratio_options": list(IMAGE_ASPECT_RATIOS),
        "n_max": 10,
        "n_options": list(range(1, 11)),
        "edit_min_images": 1,
        "edit_max_images": MAX_EDIT_IMAGES,
        "default_resolution": "1K",
        "default_quality": DEFAULT_IMAGE_QUALITY_V2 if quality_options else "",
        "default_aspect_ratio": DEFAULT_IMAGE_ASPECT_RATIO,
        "default_n": 1,
        "upstream_family": PROVIDER_VARIANT,
    }


def video_workbench_capabilities(model_name: Optional[str]) -> dict[str, Any]:
    slug = str(model_name or "").strip()
    is_v15 = slug == VIDEO_MODEL_V15
    r2v_seconds = list(range(1, 16)) if is_v15 else list(range(1, 11))
    resolution_options = list(VIDEO_RESOLUTIONS_T2V_I2V_V15 if is_v15 else VIDEO_RESOLUTIONS_V1)
    return {
        "supports_text_to_video": True,
        "supports_image_to_video": True,
        "supports_reference_to_video": True,
        "supports_video_to_video": False,
        "reference_required": False,
        "reference_min_count": 0,
        "reference_max_count": MAX_R2V_IMAGES,
        "i2v_max_count": 1,
        "reference_media_types": ["image"],
        "seconds_options_without_reference": list(range(1, 16)),
        "seconds_options_with_reference": list(range(1, 16)),
        "seconds_options_i2v": list(range(1, 16)),
        "seconds_options_r2v": r2v_seconds,
        "aspect_ratio_options": list(VIDEO_ASPECT_RATIOS),
        "resolution_options": resolution_options,
        "r2v_resolution_options": list(VIDEO_RESOLUTIONS_R2V),
        "default_seconds": DEFAULT_VIDEO_DURATION,
        "default_aspect_ratio": DEFAULT_VIDEO_ASPECT_RATIO,
        "default_resolution": DEFAULT_VIDEO_RESOLUTION,
        "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
        "supports_preset": False,
        "upstream_family": PROVIDER_VARIANT,
    }
