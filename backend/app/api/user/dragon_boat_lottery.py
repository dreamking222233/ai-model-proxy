"""User API for Dragon Boat Festival lottery."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.dragon_boat_lottery_service import DragonBoatLotteryService


router = APIRouter(prefix="/api/user/dragon-boat-lottery", tags=["用户-端午节抽奖"])


@router.get("/status", response_model=ResponseModel)
def get_lottery_status(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    result = DragonBoatLotteryService.get_user_status(db, current_user)
    return ResponseModel(data=result)


@router.post("/register", response_model=ResponseModel)
def register_lottery(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    result = DragonBoatLotteryService.register(db, current_user)
    return ResponseModel(data=result, message="报名成功")
