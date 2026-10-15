"""Administrator configuration and audit records for local cache accounting."""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.exceptions import ServiceException
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.cache_simulation import (
    CacheSimulationConfigUpdate, CacheSimulationRuleCreate, CacheSimulationRuleUpdate,
)
from app.services.cache_simulation_service import CacheSimulationService

router = APIRouter(prefix="/api/admin/cache-simulation", tags=["管理-模拟缓存"])


@router.get("/config", response_model=ResponseModel)
def get_config(db: Session = Depends(get_db), current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.config_dto(db))


@router.put("/config", response_model=ResponseModel)
def update_config(data: CacheSimulationConfigUpdate, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.update_config(db, data, current_user.id), message="配置已保存")


@router.get("/rules", response_model=ResponseModel)
def list_rules(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.list_rules(db, page, page_size))


@router.post("/rules", response_model=ResponseModel)
def create_rule(data: CacheSimulationRuleCreate, db: Session = Depends(get_db),
                current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.create_rule(db, data, current_user.id), message="规则已创建")


@router.put("/rules/{rule_id}", response_model=ResponseModel)
def update_rule(rule_id: int, data: CacheSimulationRuleUpdate, db: Session = Depends(get_db),
                current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.update_rule(db, rule_id, data, current_user.id), message="规则已保存")


@router.get("/records", response_model=ResponseModel)
def list_records(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None, gt=0), group_id: Optional[int] = Query(None, gt=0),
    model: Optional[str] = Query(None, max_length=128),
    outcome: Literal["simulated", "observing", "upstream_good", "skipped", "all"] = "simulated",
    accounting_status: Literal["settled", "pending", "failed", "all"] = "settled",
    start: Optional[datetime] = None, end: Optional[datetime] = None,
    db: Session = Depends(get_db), current_user: SysUser = Depends(require_admin),
):
    # Stored timestamps are UTC without a timezone, matching existing request logs.
    start = start.astimezone(timezone.utc).replace(tzinfo=None) if start and start.tzinfo else start
    end = end.astimezone(timezone.utc).replace(tzinfo=None) if end and end.tzinfo else end
    if start and end and start > end:
        raise ServiceException(400, "开始时间不能晚于结束时间", "CACHE_SIMULATION_INVALID_RANGE")
    return ResponseModel(data=CacheSimulationService.list_records(
        db, page, page_size, user_id=user_id, group_id=group_id, model=model,
        outcome=None if outcome == "all" else outcome,
        accounting_status=None if accounting_status == "all" else accounting_status, start=start, end=end,
    ))


@router.get("/records/{request_id}", response_model=ResponseModel)
def record_detail(request_id: str, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(require_admin)):
    return ResponseModel(data=CacheSimulationService.record_detail(db, request_id))
