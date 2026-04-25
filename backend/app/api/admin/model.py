from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import SysUser
from app.models.model import UnifiedModel, ModelChannelMapping
from app.models.channel import Channel
from app.services.model_service import ModelService
from app.schemas.model import (
    UnifiedModelCreate, UnifiedModelUpdate,
    ModelChannelMappingCreate,
    ModelOverrideRuleCreate, ModelOverrideRuleUpdate,
)
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/models", tags=["管理-模型管理"])


def _public_actual_model_name(model_name: str, actual_model_name: str | None) -> str | None:
    if str(model_name or "").strip() == "claude-opus-4-6":
        return "claude-opus-4-6"
    return actual_model_name

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


# ---- Chat Page: Channels + Models mapping ----

@router.get("/chat/channels-models", response_model=ResponseModel)
def get_channels_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """Return all enabled channels with their mapped chat/image models.
    Used by admin chat page for channel+model two-level selection.
    """
    channels = (
        db.query(Channel)
        .filter(Channel.enabled == 1)
        .order_by(Channel.priority, Channel.name)
        .all()
    )

    result = []
    for ch in channels:
        mappings = (
            db.query(ModelChannelMapping)
            .join(UnifiedModel, ModelChannelMapping.unified_model_id == UnifiedModel.id)
            .filter(
                ModelChannelMapping.channel_id == ch.id,
                ModelChannelMapping.enabled == 1,
                UnifiedModel.enabled == 1,
                UnifiedModel.model_type.in_(("chat", "image")),
            )
            .all()
        )

        models = []
        for mp in mappings:
            um = db.query(UnifiedModel).filter(UnifiedModel.id == mp.unified_model_id).first()
            if um:
                actual = mp.actual_model_name or ""
                api_type = "openai"
                if um.model_type == "chat":
                    api_type = "anthropic" if actual.startswith("responses:") else "openai"
                models.append({
                    "model_name": um.model_name,
                    "display_name": um.display_name or um.model_name,
                    "actual_model_name": _public_actual_model_name(um.model_name, mp.actual_model_name),
                    "api_type": api_type,
                    "model_type": um.model_type,
                    "protocol_type": um.protocol_type,
                    "billing_type": um.billing_type,
                    "image_credit_multiplier": float(um.image_credit_multiplier or 1),
                    "image_resolution_rules": (
                        ModelService.list_image_resolution_rules(db, um.id)
                        if um.model_type == "image" and um.protocol_type == "google"
                        else []
                    ),
                    "image_size_capabilities": (
                        list(ModelService.get_image_resolution_capabilities(um.model_name))
                        if um.model_type == "image"
                        else []
                    ),
                    "supports_image_edit": (
                        ModelService.supports_image_edit(um.model_name)
                        if um.model_type == "image"
                        else False
                    ),
                })

        if models:
            result.append({
                "channel_id": ch.id,
                "channel_name": ch.name,
                "models": models,
            })

    return ResponseModel(data=result)
