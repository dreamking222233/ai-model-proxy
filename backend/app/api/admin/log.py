from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.log_service import LogService
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/admin/logs", tags=["管理-日志"])


@router.get("/requests", response_model=ResponseModel)
def list_request_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    agent_id: int = Query(None),
    model: str = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = LogService.list_request_logs(
        db, page, page_size, user_id, agent_id, model, status, start_date, end_date
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/requests/user-summary", response_model=ResponseModel)
def get_request_user_summary(
    user_id: int = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    summary = LogService.get_admin_user_usage_summary(db, user_id, start_date, end_date)
    return ResponseModel(data=summary)


@router.get("/requests/stats", response_model=ResponseModel)
def get_request_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    stats = LogService.get_request_stats(db, days)
    return ResponseModel(data=stats)


@router.get("/operations", response_model=ResponseModel)
def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = LogService.list_operation_logs(db, page, page_size)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/consumption", response_model=ResponseModel)
def list_consumption_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    agent_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = LogService.list_consumption_records(db, page, page_size, user_id, agent_id)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
