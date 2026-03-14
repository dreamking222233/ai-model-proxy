"""User-facing endpoint for usage statistics."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.log_service import LogService
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/user/stats", tags=["用户-使用统计"])


@router.get("/model-usage", response_model=ResponseModel)
def get_model_usage_stats(
    days: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    stats = LogService.get_user_model_stats(db, current_user.id, days)
    return ResponseModel(data=stats)
