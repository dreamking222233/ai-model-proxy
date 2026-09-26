"""Administrator API for model-series routing groups."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.model import ModelGroupCreate, ModelGroupUpdate
from app.services.model_group_service import ModelGroupService

router = APIRouter(prefix="/api/admin/model-groups", tags=["管理-模型分组"])


@router.get("", response_model=ResponseModel)
def list_groups(
    model_series: Optional[str] = Query(None),
    include_disabled: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.list_groups(
        db,
        model_series=model_series,
        include_disabled=include_disabled,
    ))


@router.get("/options", response_model=ResponseModel)
def group_options(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.list_options(db, include_disabled=include_disabled))


@router.post("", response_model=ResponseModel)
def create_group(
    data: ModelGroupCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.create_group(db, data), message="模型分组已创建")


@router.put("/{group_id}", response_model=ResponseModel)
def update_group(
    group_id: int,
    data: ModelGroupUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.update_group(db, group_id, data), message="模型分组已保存")


@router.put("/{group_id}/default", response_model=ResponseModel)
def set_default_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.set_default_group(db, group_id), message="默认分组已更新")


@router.put("/{group_id}/disable", response_model=ResponseModel)
def disable_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=ModelGroupService.disable_group(db, group_id), message="模型分组已停用")


@router.delete("/{group_id}", response_model=ResponseModel)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    ModelGroupService.delete_group(db, group_id)
    return ResponseModel(message="模型分组已删除")
