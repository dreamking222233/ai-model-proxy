"""Video generation proxy endpoints for video models."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.core.dependencies import verify_api_key
from app.database import get_db
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-Video"])


async def _parse_video_form(request: Request) -> dict:
    form = await request.form()
    reference_files = [
        item
        for item in (form.getlist("input_reference[]") + form.getlist("input_reference"))
        if hasattr(item, "read")
    ]
    if len(reference_files) > 7:
        raise ServiceException(400, "参考图最多支持 7 张", "TOO_MANY_VIDEO_REFERENCES")

    parsed_references = []
    for reference_file in reference_files:
        content = await reference_file.read()
        if not content:
            raise ServiceException(400, "上传的参考图不能为空", "INVALID_VIDEO_REFERENCE")
        parsed_references.append({
            "filename": getattr(reference_file, "filename", None) or "reference.png",
            "content_type": getattr(reference_file, "content_type", None) or "application/octet-stream",
            "content": content,
        })

    return {
        "model": form.get("model"),
        "prompt": form.get("prompt"),
        "seconds": form.get("seconds"),
        "size": form.get("size"),
        "resolution_name": form.get("resolution_name"),
        "preset": form.get("preset"),
        "input_references": parsed_references,
    }


@router.post("/v1/videos")
async def videos_create_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible async video creation endpoint."""
    user, api_key_record = await verify_api_key(request, db)
    body = await _parse_video_form(request)
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_video_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.post("/v1/created/video")
async def video_created_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """Compatibility video creation endpoint."""
    user, api_key_record = await verify_api_key(request, db)
    body = await _parse_video_form(request)
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_video_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.get("/v1/videos/{video_id}")
async def videos_retrieve_v1(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Retrieve an async video task."""
    user, api_key_record = await verify_api_key(request, db)
    client_ip = request.client.host if request.client else None
    return await ProxyService.handle_video_retrieve(
        db, user, api_key_record, video_id, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.get("/v1/videos/{video_id}/content")
async def videos_content_v1(
    video_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Proxy the generated video content."""
    user, api_key_record = await verify_api_key(request, db)
    client_ip = request.client.host if request.client else None
    return await ProxyService.handle_video_content(
        db, user, api_key_record, video_id, client_ip,
        request_headers=dict(request.headers.items()),
    )
