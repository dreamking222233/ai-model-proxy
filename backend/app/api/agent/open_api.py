"""Agent administrator endpoints for managing open API credentials."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_agent_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.agent_open_api import AgentOpenApiKeyCreate, AgentOpenApiKeyScopesUpdate
from app.schemas.common import ResponseModel
from app.services.agent_open_api_key_service import AgentOpenApiKeyService

router = APIRouter(prefix="/api/agent/open-api/keys", tags=["代理-开放 API Key"])


@router.get("", response_model=ResponseModel)
def list_open_api_keys(
    response: Response,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=AgentOpenApiKeyService.list_keys(db, int(current_user.agent_id)))


@router.post("", response_model=ResponseModel)
def create_open_api_key(
    data: AgentOpenApiKeyCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    response.headers["Cache-Control"] = "no-store"
    result = AgentOpenApiKeyService.create_key(
        db,
        current_user,
        int(current_user.agent_id),
        data.name,
        data.scopes,
        data.expires_in_days,
    )
    return ResponseModel(data=result, message="开放 API Key 已创建，请立即保存明文密钥")


@router.put("/{key_id}/scopes", response_model=ResponseModel)
def update_open_api_key_scopes(
    key_id: int,
    data: AgentOpenApiKeyScopesUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentOpenApiKeyService.update_scopes(
        db, current_user, int(current_user.agent_id), key_id, data.scopes,
    )
    return ResponseModel(data=result)


@router.delete("/{key_id}", response_model=ResponseModel)
def revoke_open_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    AgentOpenApiKeyService.revoke_key(db, current_user, int(current_user.agent_id), key_id)
    return ResponseModel(message="开放 API Key 已撤销")
