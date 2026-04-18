from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.health_service import HealthService
from app.tasks.health_check import trigger_manual_check
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/health", tags=["管理-健康监控"])


class SingleChannelHealthCheckRequest(BaseModel):
    """Optional payload for overriding the model used in a single health check."""

    model_name: Optional[str] = Field(default=None, max_length=128)


@router.get("/status", response_model=ResponseModel)
def get_health_status(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    status = HealthService.get_health_status(db)
    return ResponseModel(data=status)


@router.post("/check", response_model=ResponseModel)
async def trigger_health_check(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    await trigger_manual_check()
    status = HealthService.get_health_status(db)
    return ResponseModel(message="Health check completed", data=status)


@router.post("/check/{channel_id}", response_model=ResponseModel)
async def check_single_channel(
    channel_id: int,
    data: Optional[SingleChannelHealthCheckRequest] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = await HealthService.check_single_channel(
        db,
        channel_id,
        data.model_name if data else None,
    )
    return ResponseModel(data=result)


@router.get("/logs", response_model=ResponseModel)
def get_health_logs(
    channel_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = HealthService.get_health_logs(db, channel_id, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
