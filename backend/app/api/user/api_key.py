from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.api_key_service import ApiKeyService
from app.schemas.common import ResponseModel
from pydantic import BaseModel

router = APIRouter(prefix="/api/user/api-keys", tags=["用户-API Key"])


class ApiKeyCreateRequest(BaseModel):
    name: str


@router.get("", response_model=ResponseModel)
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    keys = ApiKeyService.list_api_keys(db, current_user.id)
    return ResponseModel(data=keys)


@router.post("", response_model=ResponseModel)
def create_api_key(
    data: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    result = ApiKeyService.create_api_key(db, current_user.id, data.name)
    return ResponseModel(data=result)


@router.delete("/{key_id}", response_model=ResponseModel)
def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ApiKeyService.delete_api_key(db, current_user.id, key_id)
    return ResponseModel(message="API Key deleted")


@router.get("/{key_id}/reveal", response_model=ResponseModel)
def reveal_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    result = ApiKeyService.reveal_api_key(db, current_user.id, key_id)
    return ResponseModel(data=result)


@router.put("/{key_id}/disable", response_model=ResponseModel)
def disable_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ApiKeyService.disable_api_key(db, current_user.id, key_id)
    return ResponseModel(message="API Key disabled")


@router.put("/{key_id}/enable", response_model=ResponseModel)
def enable_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    ApiKeyService.enable_api_key(db, current_user.id, key_id)
    return ResponseModel(message="API Key enabled")
