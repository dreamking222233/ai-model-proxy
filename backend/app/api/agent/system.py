from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.agent import AgentUpdate
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent/system", tags=["代理-系统管理"])


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    return ResponseModel(data=AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    ))


@router.put("/site-config", response_model=ResponseModel)
def update_site_config(
    data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    payload = data.model_dump(
        exclude_unset=True,
        include={
            "site_title",
            "site_subtitle",
            "announcement_title",
            "announcement_content",
            "support_wechat",
            "support_qq",
            "allow_self_register",
            "theme_config_json",
        },
    )
    updated = AgentService.update_agent(db, int(current_user.agent_id), payload)
    return ResponseModel(data=updated, message="代理站点配置更新成功")
