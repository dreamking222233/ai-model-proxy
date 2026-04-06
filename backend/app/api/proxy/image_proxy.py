"""Image generation proxy endpoints for Gemini and other image models."""

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import verify_api_key
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-Image"])


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
