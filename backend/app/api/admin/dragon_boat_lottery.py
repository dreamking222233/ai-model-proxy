"""Admin API for Dragon Boat Festival lottery."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.dragon_boat_lottery_service import DragonBoatLotteryService


router = APIRouter(prefix="/api/admin/dragon-boat-lottery", tags=["管理-端午节抽奖"])


def _build_page_payload(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/summary", response_model=ResponseModel)
def get_lottery_summary(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = DragonBoatLotteryService.get_summary(db)
    return ResponseModel(data=result)


@router.get("/entries", response_model=ResponseModel)
def list_lottery_entries(
    keyword: Optional[str] = Query(None, description="搜索用户ID、用户名或邮箱"),
    status: Optional[str] = Query(None, description="registered/winner"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = DragonBoatLotteryService.list_entries(
        db,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=_build_page_payload(items, total, page, page_size))


@router.post("/draw", response_model=ResponseModel)
def draw_lottery(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = DragonBoatLotteryService.draw(db, current_user)
    return ResponseModel(data=result, message="抽奖完成")
