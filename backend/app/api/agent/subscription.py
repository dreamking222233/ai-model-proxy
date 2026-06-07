from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.agent import AgentGrantSubscriptionRequest
from app.schemas.common import ResponseModel
from app.services.agent_asset_service import AgentAssetService
from app.services.agent_settlement_service import AgentSettlementService
from app.services.agent_service import AgentService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/api/agent/subscription", tags=["代理-套餐管理"])


def _build_page_payload(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/plans", response_model=ResponseModel)
def list_plans(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    plans, total = SubscriptionService.list_plans(db, status="active", page=1, page_size=200)
    inventory = AgentService.list_agent_subscription_inventory(db, int(current_user.agent_id))
    inventory_map = {item["plan_id"]: item for item in inventory}
    credit_limits = AgentSettlementService.list_limits(db, int(current_user.agent_id))
    credit_limit_map = {
        item["plan_id"]: item
        for item in credit_limits
        if item.get("resource_type") == AgentSettlementService.RESOURCE_SUBSCRIPTION
    }
    for plan in plans:
        stock = inventory_map.get(plan["id"])
        credit_limit = credit_limit_map.get(plan["id"])
        plan["inventory"] = stock
        plan["credit_limit"] = credit_limit
        plan["remaining_count"] = stock["remaining_count"] if stock else 0
        plan["daily_remaining_count"] = int(float(credit_limit["remaining_amount"])) if credit_limit else 0
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


@router.get("/active-users", response_model=ResponseModel)
def list_active_subscription_users(
    keyword: str = Query(None, description="按用户ID、用户名或邮箱查询"),
    sort_order: str = Query("asc", description="剩余时长排序: asc/desc"),
    expires_within_days: Optional[int] = Query(None, ge=1, le=3650, description="仅查询 N 天内到期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    records, total = SubscriptionService.list_active_subscription_users(
        db,
        keyword=keyword,
        sort_order=sort_order,
        expires_within_days=expires_within_days,
        agent_id=int(current_user.agent_id),
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=_build_page_payload(records, total, page, page_size))


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
