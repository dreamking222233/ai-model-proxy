from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.balance_service import BalanceService
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/user/balance", tags=["用户-余额"])


@router.get("", response_model=ResponseModel)
def get_balance(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    balance = BalanceService.get_balance(db, current_user.id)
    return ResponseModel(data=balance)


@router.get("/consumption", response_model=ResponseModel)
def get_consumption_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    items, total = BalanceService.get_consumption_records(db, current_user.id, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
