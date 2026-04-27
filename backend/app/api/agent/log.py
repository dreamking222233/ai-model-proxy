from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agent/logs", tags=["代理-日志"])


@router.get("/requests", response_model=ResponseModel)
def list_request_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    model: str = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = LogService.list_request_logs(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        agent_id=int(current_user.agent_id),
        model=model,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )
    for item in items:
        item["actual_model"] = None
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/requests/user-summary", response_model=ResponseModel)
def get_request_user_summary(
    user_id: int = Query(...),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    summary = LogService.get_agent_user_usage_summary(
        db=db,
        user_id=user_id,
        agent_id=int(current_user.agent_id),
        start_date=start_date,
        end_date=end_date,
    )
    return ResponseModel(data=summary)


@router.get("/consumption", response_model=ResponseModel)
def list_consumption_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = LogService.list_consumption_records(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
