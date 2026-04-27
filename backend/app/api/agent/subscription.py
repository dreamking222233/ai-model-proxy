from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.agent import AgentGrantSubscriptionRequest
from app.schemas.common import ResponseModel
from app.services.agent_asset_service import AgentAssetService
from app.services.agent_service import AgentService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/agent/subscription", tags=["代理-套餐管理"])


@router.get("/plans", response_model=ResponseModel)
def list_plans(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    plans, total = SubscriptionService.list_plans(db, status="active", page=1, page_size=200)
    inventory = AgentService.list_agent_subscription_inventory(db, int(current_user.agent_id))
    inventory_map = {item["plan_id"]: item for item in inventory}
    for plan in plans:
        stock = inventory_map.get(plan["id"])
        plan["inventory"] = stock
        plan["remaining_count"] = stock["remaining_count"] if stock else 0
    return ResponseModel(data={"list": plans, "total": total})


@router.get("/inventory", response_model=ResponseModel)
def list_inventory(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items = AgentService.list_agent_subscription_inventory(db, int(current_user.agent_id))
    return ResponseModel(data=items)


@router.get("/records", response_model=ResponseModel)
def list_subscription_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = SubscriptionService.list_agent_subscriptions(
        db,
        agent_id=int(current_user.agent_id),
        status=status,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.post("/grant", response_model=ResponseModel)
def grant_subscription(
    data: AgentGrantSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentAssetService.grant_user_subscription(
        db,
        agent_id=int(current_user.agent_id),
        user_id=data.user_id,
        plan_id=data.plan_id,
        operator_user_id=current_user.id,
        activation_mode=data.activation_mode or "append",
        remark=data.remark or "agent_grant_subscription",
    )
    return ResponseModel(data=result, message="套餐发放成功")
