"""User-facing endpoint to list available models."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.models.model import UnifiedModel, ModelChannelMapping
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/user/models", tags=["用户-模型列表"])


@router.get("", response_model=ResponseModel)
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
        # Count how many active channels support this model
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
            "channel_count": channel_count,
            "description": m.description,
        })

    return ResponseModel(data=result)
