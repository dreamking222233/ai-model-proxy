"""User-facing endpoint to list available models."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.models.model import UnifiedModel, ModelChannelMapping
from app.models.channel import Channel
from app.schemas.common import ResponseModel
from app.services.model_service import ModelService

router = APIRouter(prefix="/api/user", tags=["用户-模型列表"])


@router.get("/models", response_model=ResponseModel)
def list_available_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return all enabled models with pricing info for the current user."""
    models = (
        db.query(UnifiedModel)
        .filter(UnifiedModel.enabled == 1)
        .order_by(UnifiedModel.model_type, UnifiedModel.model_name)
        .all()
    )

    result = []
    for m in models:
        channel_count = (
            db.query(ModelChannelMapping)
            .filter(
                ModelChannelMapping.unified_model_id == m.id,
                ModelChannelMapping.enabled == 1,
            )
            .count()
        )
        result.append({
            "id": m.id,
            "model_name": m.model_name,
            "display_name": m.display_name or m.model_name,
            "model_type": m.model_type,
            "protocol_type": m.protocol_type,
            "max_tokens": m.max_tokens,
            "input_price": float(m.input_price_per_million) if m.input_price_per_million else 0,
            "output_price": float(m.output_price_per_million) if m.output_price_per_million else 0,
            "billing_type": m.billing_type,
            "image_credit_multiplier": float(m.image_credit_multiplier or 1),
            "image_resolution_rules": ModelService.list_image_resolution_rules(db, m.id) if m.model_type == "image" and m.protocol_type == "google" else [],
            "channel_count": channel_count,
            "description": m.description,
        })

    return ResponseModel(data=result)


@router.get("/chat/models", response_model=ResponseModel)
def list_chat_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return enabled chat/image models for the AI chat page."""
    models = (
        db.query(UnifiedModel)
        .filter(
            UnifiedModel.enabled == 1,
            UnifiedModel.model_type.in_(("chat", "image")),
        )
        .order_by(UnifiedModel.model_type, UnifiedModel.model_name)
        .all()
    )

    result = []
    for m in models:
        mappings = (
            db.query(ModelChannelMapping)
            .join(Channel, ModelChannelMapping.channel_id == Channel.id)
            .filter(
                ModelChannelMapping.unified_model_id == m.id,
                ModelChannelMapping.enabled == 1,
                Channel.enabled == 1,
            )
            .all()
        )
        if not mappings:
            continue

        api_type = "openai"
        if m.model_type == "chat":
            has_chat_completions = False
            for mp in mappings:
                actual = mp.actual_model_name or ""
                if not actual.startswith("responses:"):
                    has_chat_completions = True
                    break
            api_type = "openai" if has_chat_completions else "anthropic"

        result.append({
            "id": m.id,
            "model_name": m.model_name,
            "display_name": m.display_name or m.model_name,
            "model_type": m.model_type,
            "protocol_type": m.protocol_type,
            "max_tokens": m.max_tokens,
            "api_type": api_type,
            "billing_type": m.billing_type,
            "image_credit_multiplier": float(m.image_credit_multiplier or 1),
            "image_resolution_rules": (
                ModelService.list_image_resolution_rules(db, m.id)
                if m.model_type == "image" and m.protocol_type == "google"
                else []
            ),
            "image_size_capabilities": (
                list(ModelService.get_image_resolution_capabilities(m.model_name))
                if m.model_type == "image"
                else []
            ),
            "supports_image_edit": (
                ModelService.supports_image_edit(m.model_name)
                if m.model_type == "image"
                else False
            ),
        })

    return ResponseModel(data=result)
