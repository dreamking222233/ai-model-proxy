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
            "model_series": getattr(m, "model_series", None) or ModelService.infer_model_series(m.model_name),
            "protocol_type": m.protocol_type,
            "max_tokens": m.max_tokens,
            "input_price": float(m.input_price_per_million) if m.input_price_per_million else 0,
            "output_price": float(m.output_price_per_million) if m.output_price_per_million else 0,
            "billing_type": m.billing_type,
            "request_price": float(getattr(m, "request_price", 0) or 0),
            "image_credit_multiplier": float(m.image_credit_multiplier or 1),
            "image_resolution_rules": (
                ModelService.list_image_resolution_rules(db, m.id)
                if ModelService.supports_image_resolution_rules(
                    m.model_name,
                    m.model_type,
                    m.billing_type,
                )
                else []
            ),
            "video_size_capabilities": (
                list(ModelService.get_video_size_capabilities(m.model_name))
                if m.model_type == "video"
                else []
            ),
            "video_seconds_capabilities": (
                list(ModelService.get_video_seconds_capabilities(m.model_name))
                if m.model_type == "video"
                else []
            ),
            "channel_count": channel_count,
            "description": m.description,
        })

    return ResponseModel(data=result)


@router.get("/chat/models", response_model=ResponseModel)
def list_chat_models(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return enabled chat/image/video models for the AI chat page."""
    models = (
        db.query(UnifiedModel)
        .filter(
            UnifiedModel.enabled == 1,
            UnifiedModel.model_type.in_(("chat", "image", "video")),
        )
        .order_by(UnifiedModel.model_type, UnifiedModel.model_name)
        .all()
    )

    result = []
    for m in models:
        mapping_rows = (
            db.query(ModelChannelMapping, Channel)
            .join(Channel, ModelChannelMapping.channel_id == Channel.id)
            .filter(
                ModelChannelMapping.unified_model_id == m.id,
                ModelChannelMapping.enabled == 1,
                Channel.enabled == 1,
            )
            .order_by(Channel.priority.asc(), Channel.id.asc())
            .all()
        )
        if not mapping_rows:
            continue

        mappings = [row[0] for row in mapping_rows]
        video_workbench_capabilities = {}
        if m.model_type == "video":
            video_workbench_capabilities = ModelService.merge_video_workbench_capabilities([
                ModelService.resolve_video_workbench_capabilities(
                    m.model_name,
                    provider_variant=getattr(channel, "provider_variant", None),
                    actual_model_name=mapping.actual_model_name,
                )
                for mapping, channel in mapping_rows
            ])

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
            "model_series": getattr(m, "model_series", None) or ModelService.infer_model_series(m.model_name),
            "protocol_type": m.protocol_type,
            "max_tokens": m.max_tokens,
            "api_type": api_type,
            "billing_type": m.billing_type,
            "request_price": float(getattr(m, "request_price", 0) or 0),
            "image_credit_multiplier": float(m.image_credit_multiplier or 1),
            "image_resolution_rules": (
                ModelService.list_image_resolution_rules(db, m.id)
                if ModelService.supports_image_resolution_rules(
                    m.model_name,
                    m.model_type,
                    m.billing_type,
                )
                else []
            ),
            "image_size_capabilities": (
                list(ModelService.get_image_resolution_capabilities(m.model_name))
                if m.model_type == "image"
                else []
            ),
            "video_size_capabilities": (
                list(ModelService.get_video_size_capabilities(m.model_name))
                if m.model_type == "video"
                else []
            ),
            "video_seconds_capabilities": (
                list(ModelService.get_video_seconds_capabilities(m.model_name))
                if m.model_type == "video"
                else []
            ),
            "video_workbench_capabilities": video_workbench_capabilities,
            "supports_image_edit": (
                ModelService.supports_image_edit(m.model_name)
                if m.model_type == "image"
                else False
            ),
        })

    return ResponseModel(data=result)
