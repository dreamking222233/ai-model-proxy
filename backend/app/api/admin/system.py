from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.models.log import SystemConfig
from app.schemas.common import ResponseModel
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/admin/system", tags=["管理-系统配置"])


class ConfigUpdate(BaseModel):
    config_value: str
    description: Optional[str] = None


@router.get("/configs", response_model=ResponseModel)
def list_configs(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    configs = db.query(SystemConfig).order_by(SystemConfig.id).all()
    result = [
        {
            "id": c.id,
            "config_key": c.config_key,
            "config_value": c.config_value,
            "config_type": c.config_type,
            "description": c.description,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in configs
    ]
    return ResponseModel(data=result)


@router.put("/configs/{config_id}", response_model=ResponseModel)
def update_config(
    config_id: int,
    data: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    config = db.query(SystemConfig).filter(SystemConfig.id == config_id).first()
    if not config:
        from app.core.exceptions import ServiceException
        raise ServiceException(404, "Config not found")
    config.config_value = data.config_value
    if data.description is not None:
        config.description = data.description
    db.commit()
    db.refresh(config)
    return ResponseModel(data={
        "id": config.id,
        "config_key": config.config_key,
        "config_value": config.config_value,
        "config_type": config.config_type,
        "description": config.description,
    })


@router.get("/dashboard", response_model=ResponseModel)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    from app.models.user import SysUser as UserModel
    from app.models.channel import Channel
    from app.models.model import UnifiedModel
    from app.models.log import RequestLog
    from sqlalchemy import func
    from datetime import datetime, timedelta

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.query(func.count(UserModel.id)).scalar()
    total_channels = db.query(func.count(Channel.id)).scalar()
    enabled_channels = db.query(func.count(Channel.id)).filter(
        Channel.enabled == 1
    ).scalar()
    healthy_channels = db.query(func.count(Channel.id)).filter(
        Channel.enabled == 1, Channel.is_healthy == 1
    ).scalar()
    total_models = db.query(func.count(UnifiedModel.id)).filter(UnifiedModel.enabled == 1).scalar()

    today_requests = db.query(func.count(RequestLog.id)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_tokens = db.query(func.coalesce(func.sum(RequestLog.total_tokens), 0)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_errors = db.query(func.count(RequestLog.id)).filter(
        RequestLog.created_at >= today, RequestLog.status == 'error'
    ).scalar()

    return ResponseModel(data={
        "total_users": total_users,
        "total_channels": total_channels,
        "enabled_channels": enabled_channels,
        "healthy_channels": healthy_channels,
        "total_models": total_models,
        "today_requests": today_requests,
        "today_tokens": int(today_tokens),
        "today_errors": today_errors,
    })
