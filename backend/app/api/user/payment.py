"""User payment APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_current_agent_context
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.payment import UserRechargeOrderCreateRequest
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/user/payment", tags=["用户-在线充值"])


def _require_end_user(current_user: SysUser) -> SysUser:
    if current_user.role != "user":
        from app.core.exceptions import ServiceException
        raise ServiceException(403, "只有终端用户可以发起在线充值", "FORBIDDEN")
    return current_user


@router.post("/recharge-orders", response_model=ResponseModel)
def create_recharge_order(
    data: UserRechargeOrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    agent_context=Depends(get_current_agent_context),
):
    user = _require_end_user(current_user)
    result = PaymentService.create_recharge_order(
        db,
        user=user,
        amount_cny=data.amount_cny,
        payment_channel=data.payment_channel,
        recharge_type=data.recharge_type,
        site_context=agent_context,
    )
    return ResponseModel(data=result, message="充值订单创建成功")


@router.get("/recharge-orders", response_model=ResponseModel)
def list_recharge_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    user = _require_end_user(current_user)
    items, total = PaymentService.list_user_orders(db, user.id, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/recharge-orders/{order_no}", response_model=ResponseModel)
def get_recharge_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    user = _require_end_user(current_user)
    return ResponseModel(data=PaymentService.get_user_order(db, user.id, order_no))


@router.post("/recharge-orders/{order_no}/sync", response_model=ResponseModel)
def sync_recharge_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    user = _require_end_user(current_user)
    return ResponseModel(data=PaymentService.sync_order_status(db, user.id, order_no))
