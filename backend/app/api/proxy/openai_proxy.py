from fastapi import APIRouter, Request, Depends, WebSocket
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import verify_api_key, verify_api_key_from_headers
from app.core.exceptions import ServiceException
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


@router.post("/v1/responses")
async def codex_responses_v1(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    OpenAI Responses API endpoint for Codex CLI compatibility.

    This endpoint handles Codex CLI requests using the Responses API format:
    - Request: {"model": "...", "input": "..."}
    - Response: Responses API format with events like response.output_text.delta
    """
    user, api_key_record = await verify_api_key(request, db)
    body = await request.json()
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_responses_request(
        db, user, api_key_record, body, client_ip
    )


@router.post("/responses")
async def codex_responses_root(
    request: Request,
    db: Session = Depends(get_db),
):
    """OpenAI Responses API endpoint without /v1 prefix"""
    user, api_key_record = await verify_api_key(request, db)
    body = await request.json()
    client_ip = request.client.host if request.client else None

    return await ProxyService.handle_responses_request(
        db, user, api_key_record, body, client_ip
    )


async def _handle_codex_responses_websocket(websocket: WebSocket, db: Session):
    """Shared websocket entry for Codex CLI Responses API."""
    try:
        user, api_key_record = verify_api_key_from_headers(
            db,
            authorization=websocket.headers.get("Authorization"),
            x_api_key=websocket.headers.get("X-API-Key"),
            anthropic_api_key=websocket.headers.get("anthropic-api-key"),
        )
    except ServiceException as exc:
        await websocket.close(code=1008, reason=exc.detail[:120])
        return

    await websocket.accept()
    client_ip = websocket.client.host if websocket.client else None
    await ProxyService.handle_responses_websocket(
        db, user, api_key_record, websocket, client_ip
    )


@router.websocket("/v1/responses")
async def codex_responses_v1_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """Websocket Responses API endpoint for Codex CLI compatibility."""
    await _handle_codex_responses_websocket(websocket, db)


@router.websocket("/responses")
async def codex_responses_root_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """Websocket Responses API endpoint without /v1 prefix."""
    await _handle_codex_responses_websocket(websocket, db)
