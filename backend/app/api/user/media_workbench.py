"""User media workbench endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.media_workbench_service import MediaWorkbenchService

router = APIRouter(prefix="/api/user/media-workbench", tags=["用户-媒体工作台"])


@router.get("/health", response_model=ResponseModel)
def get_media_health(
    window_hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    return ResponseModel(data=MediaWorkbenchService.get_media_health(db, window_hours, current_user.id))
