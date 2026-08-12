from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.agent import AgentSiteConfigUpdate
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentAuditContext, AgentService

router = APIRouter(prefix="/api/agent/system", tags=["代理-系统管理"])


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    data = AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
        user=current_user,
    )
    editable = AgentService.get_agent(db, int(current_user.agent_id))
    data.update({
        "custom_recharge_rate_enabled": editable["custom_recharge_rate_enabled"],
        "custom_recharge_rate": editable["custom_recharge_rate"],
        "max_custom_recharge_rate": editable["max_custom_recharge_rate"],
        "subscription_online_recharge_configured": editable["subscription_online_recharge_configured"],
    })
    return ResponseModel(data=data)


@router.put("/site-config", response_model=ResponseModel)
def update_site_config(
    data: AgentSiteConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    agent_id = int(current_user.agent_id)
    updated = AgentService.update_agent_site_config(
        db,
        agent_id,
        data,
        audit_context=AgentAuditContext(
            user_id=current_user.id,
            username=current_user.username,
            source="agent",
            ip_address=request.client.host if request.client else None,
        ),
    )
    return ResponseModel(data=updated, message="代理站点配置更新成功")
