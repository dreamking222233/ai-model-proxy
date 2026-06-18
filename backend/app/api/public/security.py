from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ResponseModel
from app.services.security_detection_service import SecurityDetectionService

router = APIRouter(prefix="/api/public/security", tags=["公共-安全风控"])


class PublicRiskReportPayload(BaseModel):
    snapshot_id: str = Field(..., max_length=36)
    report_token: str = Field(..., max_length=256)
    category: str = Field("unknown", max_length=64)
    severity: str = Field("medium", max_length=20)
    reason: Optional[str] = Field("", max_length=2000)


@router.post("/risk-report", response_model=ResponseModel)
def report_security_risk(
    payload: PublicRiskReportPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else None
    result = SecurityDetectionService.handle_public_report(
        db,
        payload.dict(),
        client_ip,
    )
    return ResponseModel(data=result, message="风险已上报")
