"""User API for redeeming codes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.redemption_service import RedemptionService
from app.schemas.common import ResponseModel
from pydantic import BaseModel, Field


class RedeemCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, description="兑换码")


router = APIRouter(prefix="/api/user/redemption", tags=["用户-兑换码"])


@router.get("/status", response_model=ResponseModel)
def get_redemption_status(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """查询当前用户的兑换状态（是否已使用过兑换码）"""
    info = RedemptionService.get_user_redemption_info(db, current_user.id)
    return ResponseModel(data=info)


@router.post("/redeem", response_model=ResponseModel)
def redeem_code(
    data: RedeemCodeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """兑换码充值（每位用户仅能使用一次）"""
    result = RedemptionService.redeem_code(db, current_user.id, data.code)
    return ResponseModel(data=result, message=f"兑换成功，充值 ${result['amount']:.4f}")
