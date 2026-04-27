from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_platform_admin
from app.models.user import SysUser
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentBalanceRecharge,
    AgentImageBalanceRecharge,
    AgentSubscriptionInventoryRecharge,
    AgentRedemptionAmountRuleCreate,
)
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentService
from app.services.agent_asset_service import AgentAssetService
from app.services.redemption_service import RedemptionService

router = APIRouter(prefix="/api/admin/agents", tags=["管理-代理管理"])


@router.get("/amount-rules", response_model=ResponseModel)
def list_redemption_amount_rules(
    agent_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = RedemptionService.list_allowed_amount_rules(db, agent_id=agent_id)
    return ResponseModel(data=result)


@router.post("/amount-rules", response_model=ResponseModel)
def create_redemption_amount_rule(
    data: AgentRedemptionAmountRuleCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = RedemptionService.create_amount_rule(
        db,
        amount=data.amount,
        agent_id=data.agent_id,
        status=data.status or "active",
        sort_order=data.sort_order or 0,
    )
    return ResponseModel(data=result, message="代理兑换码面额规则创建成功")


@router.get("", response_model=ResponseModel)
def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    items, total = AgentService.list_agents(db, page, page_size, keyword)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{agent_id}", response_model=ResponseModel)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    return ResponseModel(data=AgentService.get_agent(db, agent_id))


@router.post("", response_model=ResponseModel)
def create_agent(
    data: AgentCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    return ResponseModel(data=AgentService.create_agent(db, data), message="代理创建成功")


@router.put("/{agent_id}", response_model=ResponseModel)
def update_agent(
    agent_id: int,
    data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    return ResponseModel(data=AgentService.update_agent(db, agent_id, data), message="代理更新成功")


@router.post("/{agent_id}/balance/recharge", response_model=ResponseModel)
def recharge_agent_balance(
    agent_id: int,
    data: AgentBalanceRecharge,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentAssetService.recharge_agent_balance(
        db,
        agent_id=agent_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.remark,
    )
    return ResponseModel(data=result, message="代理余额充值成功")


@router.post("/{agent_id}/image-credits/recharge", response_model=ResponseModel)
def recharge_agent_image_balance(
    agent_id: int,
    data: AgentImageBalanceRecharge,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentAssetService.recharge_agent_image_balance(
        db,
        agent_id=agent_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.remark,
    )
    return ResponseModel(data=result, message="代理图片积分充值成功")


@router.get("/{agent_id}/subscription-inventory", response_model=ResponseModel)
def list_agent_subscription_inventory(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentService.list_agent_subscription_inventory(db, agent_id)
    return ResponseModel(data=result)


@router.post("/{agent_id}/subscription-inventory/recharge", response_model=ResponseModel)
def recharge_agent_subscription_inventory(
    agent_id: int,
    data: AgentSubscriptionInventoryRecharge,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentAssetService.recharge_agent_subscription_inventory(
        db,
        agent_id=agent_id,
        plan_id=data.plan_id,
        count=data.count,
        operator_user_id=current_user.id,
        remark=data.remark,
    )
    return ResponseModel(data=result, message="代理套餐库存充值成功")

