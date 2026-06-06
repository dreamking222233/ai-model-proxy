from fastapi import APIRouter, Depends, Query
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
    range_key: str = Query("7d", alias="range"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    from app.models.log import ConsumptionRecord, RequestLog
    from app.models.model import UnifiedModel
    from sqlalchemy import func
    from app.services.log_service import LogService

    today, _ = LogService._get_timezone_day_window(1)
    user_total = db.query(func.count(SysUser.id)).filter(
        SysUser.role == "user"
    ).scalar()
    model_total = db.query(func.count(UnifiedModel.id)).scalar()

    today_requests = db.query(func.count(RequestLog.id)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_tokens = db.query(func.coalesce(func.sum(RequestLog.total_tokens), 0)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_cost = db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0)).filter(
        ConsumptionRecord.created_at >= today,
        ConsumptionRecord.total_cost > 0,
        ConsumptionRecord.request_id.isnot(None),
        ConsumptionRecord.model_name.isnot(None),
    ).scalar()

    return ResponseModel(data={
        "user_total": int(user_total or 0),
        "model_total": int(model_total or 0),
        "today_requests": today_requests,
        "today_tokens": int(today_tokens),
        "today_cost": float(today_cost or 0),
    })
