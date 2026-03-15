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


@router.post("/redeem", response_model=ResponseModel)
def redeem_code(
    data: RedeemCodeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """兑换码充值"""
    result = RedemptionService.redeem_code(db, current_user.id, data.code)
    return ResponseModel(data=result, message=f"兑换成功，充值 ${result['amount']:.4f}")
