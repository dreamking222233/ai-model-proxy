from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.balance_service import BalanceService
from app.services.log_service import LogService
from app.schemas.user import UserUpdate, BalanceRechargeRequest
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/users", tags=["管理-用户管理"])


@router.get("", response_model=ResponseModel)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = AuthService.list_users(db, page, page_size, keyword)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{user_id}", response_model=ResponseModel)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.get_user_detail(db, user_id)
    return ResponseModel(data=user)


@router.put("/{user_id}", response_model=ResponseModel)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.update_user(db, user_id, data)
    return ResponseModel(data=user)


@router.put("/{user_id}/status", response_model=ResponseModel)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.toggle_user_status(db, user_id)
    return ResponseModel(data={"id": user.id, "status": user.status})


@router.post("/recharge", response_model=ResponseModel)
def recharge_balance(
    data: BalanceRechargeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    balance = BalanceService.recharge(db, data.user_id, data.amount, current_user.id)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "recharge", "user_balance", data.user_id,
        f"Recharged {data.amount} for user {data.user_id}",
        None,
    )
    return ResponseModel(data=balance)
