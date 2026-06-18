from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.core.exceptions import ServiceException
from app.database import get_db
from app.models.log import SecurityRiskEvent
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.security_detection_service import SecurityDetectionService

router = APIRouter(prefix="/api/admin/security", tags=["管理-安全风控"])


class RiskEventReviewPayload(BaseModel):
    status: str = Field(..., max_length=20)
    review_note: Optional[str] = Field("", max_length=2000)


@router.get("/events", response_model=ResponseModel)
def list_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = SecurityDetectionService.list_risk_events(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        category=category,
        risk_level=risk_level,
        source=source,
        status=status,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/events/{event_id}", response_model=ResponseModel)
def get_security_event_detail(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    client_ip = request.client.host if request.client else None
    detail = SecurityDetectionService.get_risk_event_detail(
        db,
        event_id,
        current_user=current_user,
        client_ip=client_ip,
    )
    return ResponseModel(data=detail)


@router.get("/stats", response_model=ResponseModel)
def get_security_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=SecurityDetectionService.get_risk_stats(db))


@router.put("/events/{event_id}/review", response_model=ResponseModel)
def review_security_event(
    event_id: str,
    payload: RiskEventReviewPayload,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    status = str(payload.status or "").strip().lower()
    if status not in {"open", "reviewed", "ignored"}:
        raise ServiceException(400, "处理状态无效", "INVALID_SECURITY_REVIEW_STATUS")
    event = db.query(SecurityRiskEvent).filter(SecurityRiskEvent.event_id == event_id).first()
    if not event:
        raise ServiceException(404, "风险事件不存在", "SECURITY_EVENT_NOT_FOUND")
    event.status = status
    event.reviewer_id = current_user.id
    event.review_note = payload.review_note or ""
    from datetime import datetime
    event.reviewed_at = datetime.utcnow()
    db.commit()
    return ResponseModel(message="处理状态已更新")


@router.post("/snapshots/purge", response_model=ResponseModel)
def purge_security_snapshots(
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    purged = SecurityDetectionService.purge_expired_snapshots(db, limit=limit)
    return ResponseModel(data={"purged": purged}, message="过期快照清理完成")
