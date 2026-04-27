"""Public site configuration endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/public", tags=["公开-站点配置"])


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    request: Request,
    db: Session = Depends(get_db),
):
    data = AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(data=data)
