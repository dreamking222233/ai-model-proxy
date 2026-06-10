"""User promotion APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_agent_context, get_current_user
from app.core.exceptions import ServiceException
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.promotion_service import PromotionService

router = APIRouter(prefix="/api/user/promotion", tags=["用户-推广"])


def _require_end_user(current_user: SysUser) -> SysUser:
    if current_user.role != "user":
        raise ServiceException(403, "只有普通用户可以使用推广功能", "FORBIDDEN")
    return current_user


@router.get("/overview", response_model=ResponseModel)
def get_promotion_overview(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
    agent_context=Depends(get_current_agent_context),
):
    user = _require_end_user(current_user)
    return ResponseModel(data=PromotionService.get_user_overview(db, user, agent_context))


@router.get("/invited-users", response_model=ResponseModel)
def list_invited_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    user = _require_end_user(current_user)
    items, total = PromotionService.list_user_invited_users(db, user.id, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
