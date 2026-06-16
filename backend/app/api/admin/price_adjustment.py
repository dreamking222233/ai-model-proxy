from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.model import ModelPriceAdjustmentRuleCreate, ModelPriceAdjustmentRuleUpdate
from app.services.price_adjustment_service import PriceAdjustmentService

router = APIRouter(prefix="/api/admin/price-adjustments", tags=["管理-价格调控"])


@router.get("", response_model=ResponseModel)
def list_price_adjustment_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_series: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    enabled: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = PriceAdjustmentService.list_rules(
        db,
        page=page,
        page_size=page_size,
        model_series=model_series,
        model_type=model_type,
        enabled=enabled,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/options", response_model=ResponseModel)
def get_price_adjustment_options(
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=PriceAdjustmentService.get_options())


@router.get("/effective", response_model=ResponseModel)
def get_effective_price_adjustments(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=PriceAdjustmentService.list_effective_matrix(db))


@router.post("", response_model=ResponseModel)
def create_price_adjustment_rule(
    data: ModelPriceAdjustmentRuleCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=PriceAdjustmentService.create_rule(db, data), message="价格调控规则已创建")


@router.put("/{rule_id}", response_model=ResponseModel)
def update_price_adjustment_rule(
    rule_id: int,
    data: ModelPriceAdjustmentRuleUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=PriceAdjustmentService.update_rule(db, rule_id, data), message="价格调控规则已保存")


@router.delete("/{rule_id}", response_model=ResponseModel)
def delete_price_adjustment_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    PriceAdjustmentService.delete_rule(db, rule_id)
    return ResponseModel(message="价格调控规则已删除")
