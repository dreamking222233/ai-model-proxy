"""Agent promotion visibility APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_agent_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.promotion_service import PromotionService

router = APIRouter(prefix="/api/agent/promotions", tags=["代理-推广记录"])


@router.get("/summary", response_model=ResponseModel)
def get_agent_promotion_summary(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    return ResponseModel(data=PromotionService.get_admin_summary(db, agent_id=int(current_user.agent_id)))


@router.get("/relations", response_model=ResponseModel)
def list_agent_promotion_relations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    has_recharged: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = PromotionService.list_relations(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        site_scope="agent",
        agent_id=int(current_user.agent_id),
        has_recharged=has_recharged,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/rewards", response_model=ResponseModel)
def list_agent_promotion_rewards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    reward_asset_type: str = Query(None),
    recharge_type: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = PromotionService.list_rewards(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        agent_id=int(current_user.agent_id),
        reward_asset_type=reward_asset_type,
        recharge_type=recharge_type,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
