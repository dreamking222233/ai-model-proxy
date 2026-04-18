from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import SysUser
from app.services.channel_service import ChannelService
from app.schemas.channel import ChannelCreate, ChannelHealthCheckModelUpdate, ChannelUpdate
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/channels", tags=["管理-渠道管理"])


@router.get("", response_model=ResponseModel)
def list_channels(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = ChannelService.list_channels(db, page, page_size, keyword)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{channel_id}", response_model=ResponseModel)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    channel = ChannelService.get_channel(db, channel_id)
    return ResponseModel(data=channel)


@router.post("", response_model=ResponseModel)
def create_channel(
    data: ChannelCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    channel = ChannelService.create_channel(db, data)
    return ResponseModel(data=channel)


@router.put("/{channel_id}", response_model=ResponseModel)
def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    channel = ChannelService.update_channel(db, channel_id, data)
    return ResponseModel(data=channel)


@router.put("/{channel_id}/health-check-model", response_model=ResponseModel)
def update_channel_health_check_model(
    channel_id: int,
    data: ChannelHealthCheckModelUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    channel = ChannelService.update_channel_health_check_model(
        db,
        channel_id,
        data.health_check_model,
    )
    return ResponseModel(data=channel)


@router.delete("/{channel_id}", response_model=ResponseModel)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    ChannelService.delete_channel(db, channel_id)
    return ResponseModel(message="Channel deleted")
