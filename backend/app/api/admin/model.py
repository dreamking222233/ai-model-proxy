from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import SysUser
from app.services.model_service import ModelService
from app.schemas.model import (
    UnifiedModelCreate, UnifiedModelUpdate,
    ModelChannelMappingCreate,
    ModelOverrideRuleCreate, ModelOverrideRuleUpdate,
)
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/models", tags=["管理-模型管理"])

# ---- Unified Model ----

@router.get("", response_model=ResponseModel)
def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = ModelService.list_models(db, page, page_size, keyword)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{model_id}", response_model=ResponseModel)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = ModelService.get_model_with_mappings(db, model_id)
    return ResponseModel(data=result)


@router.post("", response_model=ResponseModel)
def create_model(
    data: UnifiedModelCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    model = ModelService.create_model(db, data)
    return ResponseModel(data=model)


@router.put("/{model_id}", response_model=ResponseModel)
def update_model(
    model_id: int,
    data: UnifiedModelUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    model = ModelService.update_model(db, model_id, data)
    return ResponseModel(data=model)


@router.delete("/{model_id}", response_model=ResponseModel)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    ModelService.delete_model(db, model_id)
    return ResponseModel(message="Model deleted")


# ---- Model Channel Mapping ----

@router.get("/{model_id}/mappings", response_model=ResponseModel)
def list_model_mappings(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    mappings = ModelService.list_mappings(db, model_id)
    return ResponseModel(data=mappings)


@router.post("/mappings", response_model=ResponseModel)
def create_mapping(
    data: ModelChannelMappingCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    mapping = ModelService.create_mapping(db, data)
    return ResponseModel(data=mapping)


@router.delete("/mappings/{mapping_id}", response_model=ResponseModel)
def delete_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    ModelService.delete_mapping(db, mapping_id)
    return ResponseModel(message="Mapping deleted")


# ---- Override Rules ----

@router.get("/override-rules/list", response_model=ResponseModel)
def list_override_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = ModelService.list_override_rules(db, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.post("/override-rules", response_model=ResponseModel)
def create_override_rule(
    data: ModelOverrideRuleCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    rule = ModelService.create_override_rule(db, data)
    return ResponseModel(data=rule)


@router.put("/override-rules/{rule_id}", response_model=ResponseModel)
def update_override_rule(
    rule_id: int,
    data: ModelOverrideRuleUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    rule = ModelService.update_override_rule(db, rule_id, data)
    return ResponseModel(data=rule)


@router.delete("/override-rules/{rule_id}", response_model=ResponseModel)
def delete_override_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    ModelService.delete_override_rule(db, rule_id)
    return ResponseModel(message="Override rule deleted")
