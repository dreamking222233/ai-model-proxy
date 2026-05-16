"""Admin payment and agent cash APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_platform_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.payment import AgentCashAdjustRequest, AgentCashWithdrawRequest
from app.services.agent_cash_service import AgentCashService

router = APIRouter(prefix="/api/admin/payments", tags=["管理-支付管理"])


@router.get("/agent-cash/summary", response_model=ResponseModel)
def list_agent_cash_summary(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    items, total = AgentCashService.list_admin_summary(db, page, page_size, keyword)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/agent-cash/orders", response_model=ResponseModel)
def list_agent_cash_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_id: int = Query(None),
    user_id: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    items, total = AgentCashService.list_recharge_orders(db, page, page_size, agent_id, user_id, status)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/agent-cash/withdrawals", response_model=ResponseModel)
def list_agent_cash_withdrawals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    items, total = AgentCashService.list_withdrawals(db, page, page_size, agent_id)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.post("/agent-cash/{agent_id}/adjust", response_model=ResponseModel)
def adjust_agent_cash(
    agent_id: int,
    data: AgentCashAdjustRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentCashService.adjust_agent_cash_balance(
        db,
        agent_id=agent_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.remark,
    )
    return ResponseModel(data=result, message="代理现金余额调整成功")


@router.post("/agent-cash/{agent_id}/withdraw", response_model=ResponseModel)
def withdraw_agent_cash(
    agent_id: int,
    data: AgentCashWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentCashService.withdraw_agent_cash(
        db,
        agent_id=agent_id,
        amount=data.amount,
        transfer_method=data.transfer_method,
        operator_user_id=current_user.id,
        remark=data.remark,
    )
    return ResponseModel(data=result, message="代理提现登记成功")
