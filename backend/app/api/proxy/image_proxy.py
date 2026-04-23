"""Image generation/edit proxy endpoints for image models."""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.database import get_db
from app.core.dependencies import verify_api_key
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-Image"])


async def _parse_image_edit_form(request: Request) -> dict:
    form = await request.form()
    image_files = [item for item in form.getlist("image") if hasattr(item, "read")]
    if not image_files:
        raise ServiceException(400, "Missing required field: image", "INVALID_IMAGE_FILE")

    parsed_images = []
    for image_file in image_files:
        image_bytes = await image_file.read()
        if not image_bytes:
            raise ServiceException(400, "Uploaded image is empty", "INVALID_IMAGE_FILE")
        parsed_images.append({
            "filename": getattr(image_file, "filename", None) or "upload.png",
            "content_type": getattr(image_file, "content_type", None) or "application/octet-stream",
            "content": image_bytes,
        })

    return {
        "model": form.get("model"),
        "prompt": form.get("prompt"),
        "n": form.get("n"),
        "response_format": form.get("response_format"),
        "image_size": form.get("image_size"),
        "imageSize": form.get("imageSize"),
        "size": form.get("size"),
        "aspect_ratio": form.get("aspect_ratio"),
        # Keep the legacy single-image field for existing downstream logic.
        "image": parsed_images[0],
        "images": parsed_images,
    }


@router.post("/v1/images/generations")
async def image_generations_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible image generation endpoint with /v1 prefix."""
    user, api_key_record = await verify_api_key(request, db)
    body = await request.json()
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_image_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.post("/v1/image/created")
async def image_created_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """Alternative image generation endpoint."""
    user, api_key_record = await verify_api_key(request, db)
    body = await request.json()
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_image_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.post("/v1/image/edit")
async def image_edit_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """Alternative image edit endpoint."""
    user, api_key_record = await verify_api_key(request, db)
    body = await _parse_image_edit_form(request)
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_image_edit_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )


@router.post("/v1/images/edits")
async def image_edits_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible image edit endpoint with /v1 prefix."""
    user, api_key_record = await verify_api_key(request, db)
    body = await _parse_image_edit_form(request)
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_image_edit_request(
        db, user, api_key_record, body, client_ip,
        request_headers=dict(request.headers.items()),
    )
