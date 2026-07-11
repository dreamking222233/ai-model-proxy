"""Public site configuration endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentService
from app.models.model import UnifiedModel

router = APIRouter(prefix="/api/public", tags=["公开-站点配置"])


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    request: Request,
    db: Session = Depends(get_db),
):
    data = AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    # Deprecated compatibility fields: support contacts are now always visible.
    data.update({
        "support_contact_visible": True,
        "support_contact_notice": "",
        "support_contact_threshold_cny": None,
        "support_contact_paid_cny": None,
    })
    return ResponseModel(data=data)


@router.get("/models", response_model=ResponseModel)
def list_public_models(
    db: Session = Depends(get_db),
):
    """返回所有已启用的模型列表及基本定价和属性，供公开首页展示"""
    models = (
        db.query(UnifiedModel)
        .filter(UnifiedModel.enabled == 1)
        .order_by(UnifiedModel.model_type, UnifiedModel.model_name)
        .all()
    )

    result = []
    for m in models:
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
            "request_price": float(getattr(m, "request_price", 0) or 0),
            "image_credit_multiplier": float(m.image_credit_multiplier or 1),
            "description": m.description,
        })

    return ResponseModel(data=result)
