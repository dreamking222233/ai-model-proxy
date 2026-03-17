from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import verify_api_key
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-Anthropic"])


@router.post("/v1/messages")
async def anthropic_messages_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """Anthropic Messages API with /v1 prefix (standard format)"""
    # Verify API Key from headers
    user, api_key_record = await verify_api_key(request, db)

    # Parse request body
    body = await request.json()
    client_ip = request.client.host if request.client else None

    # Delegate to proxy service
    return await ProxyService.handle_anthropic_request(
        db, user, api_key_record, body, client_ip
    )


@router.post("/messages")
async def anthropic_messages_root(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Anthropic Messages API without /v1 prefix.

    This endpoint is for compatibility with clients like OpenClaw that configure
    baseUrl without /v1 and use api: "anthropic-messages".

    Example OpenClaw config:
    {
      "baseUrl": "https://your-domain.com",
      "api": "anthropic-messages"
    }
    """
    # Verify API Key from headers
    user, api_key_record = await verify_api_key(request, db)

    # Parse request body
    body = await request.json()
    client_ip = request.client.host if request.client else None

    # Delegate to proxy service
    return await ProxyService.handle_anthropic_request(
        db, user, api_key_record, body, client_ip
    )
