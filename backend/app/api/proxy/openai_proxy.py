from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import verify_api_key
from app.models.user import SysUser, UserApiKey
from app.services.proxy_service import ProxyService

router = APIRouter(tags=["代理-OpenAI"])


@router.post("/v1/chat/completions")
async def openai_chat_completions(
    request: Request,
    db: Session = Depends(get_db),
):
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
async def list_models(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI-compatible model listing endpoint"""
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
