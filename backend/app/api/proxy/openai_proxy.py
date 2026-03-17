from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import verify_api_key
from app.models.user import SysUser, UserApiKey
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-OpenAI"])


@router.post("/v1/chat/completions")
async def openai_chat_completions_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI Chat Completions API with /v1 prefix (standard format)"""
    # Verify API Key from headers
    user, api_key_record = await verify_api_key(request, db)

    # Parse request body
    body = await request.json()
    client_ip = request.client.host if request.client else None

    # Delegate to proxy service
    return await ProxyService.handle_openai_request(
        db, user, api_key_record, body, client_ip
    )


@router.post("/chat/completions")
async def openai_chat_completions_root(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    OpenAI Chat Completions API without /v1 prefix.

    This endpoint is for compatibility with clients that configure
    baseUrl without /v1 and expect the SDK to handle path construction.

    Example config:
    {
      "baseUrl": "https://your-domain.com",
      "api": "openai-completions"
    }
    """
    # Verify API Key from headers
    user, api_key_record = await verify_api_key(request, db)

    # Parse request body
    body = await request.json()
    client_ip = request.client.host if request.client else None

    # Delegate to proxy service
    return await ProxyService.handle_openai_request(
        db, user, api_key_record, body, client_ip
    )


@router.get("/v1/models")
async def list_models_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible model listing endpoint with /v1 prefix"""
    user, api_key_record = await verify_api_key(request, db)

    from app.models.model import UnifiedModel
    models = db.query(UnifiedModel).filter(UnifiedModel.enabled == 1).all()

    model_list = []
    for m in models:
        model_list.append({
            "id": m.model_name,
            "object": "model",
            "created": int(m.created_at.timestamp()) if m.created_at else 0,
            "owned_by": "system",
        })

    return {
        "object": "list",
        "data": model_list,
    }


@router.get("/models")
async def list_models_root(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible model listing endpoint without /v1 prefix"""
    user, api_key_record = await verify_api_key(request, db)

    from app.models.model import UnifiedModel
    models = db.query(UnifiedModel).filter(UnifiedModel.enabled == 1).all()

    model_list = []
    for m in models:
        model_list.append({
            "id": m.model_name,
            "object": "model",
            "created": int(m.created_at.timestamp()) if m.created_at else 0,
            "owned_by": "system",
        })

    return {
        "object": "list",
        "data": model_list,
    }
