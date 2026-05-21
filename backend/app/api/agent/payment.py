"""Agent payment visibility APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_agent_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.agent_cash_service import AgentCashService

router = APIRouter(prefix="/api/agent/payments", tags=["代理-充值记录"])


@router.get("/summary", response_model=ResponseModel)
def get_agent_payment_summary(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    return ResponseModel(data=AgentCashService.get_agent_summary(db, int(current_user.agent_id)))


@router.get("/orders", response_model=ResponseModel)
def list_agent_payment_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    status: str = Query(None),
    recharge_type: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = AgentCashService.list_recharge_orders(
        db,
        page=page,
        page_size=page_size,
        agent_id=int(current_user.agent_id),
        user_id=user_id,
        status=status,
        recharge_type=recharge_type,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/withdrawals", response_model=ResponseModel)
def list_agent_payment_withdrawals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = AgentCashService.list_withdrawals(
        db,
        page=page,
        page_size=page_size,
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
