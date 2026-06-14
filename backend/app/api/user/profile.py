from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.log_service import LogService
from app.services.health_service import get_system_config
from app.services.agent_service import AgentService
from app.models.log import PlatformAnnouncement, SystemConfig
from app.schemas.user import PasswordChange
from app.schemas.common import ResponseModel
from fastapi import Query

router = APIRouter(prefix="/api/user/profile", tags=["用户-个人信息"])


@router.get("", response_model=ResponseModel)
def get_profile(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    info = AuthService.get_current_user_info(db, current_user.id)
    return ResponseModel(data=info)


@router.put("/password", response_model=ResponseModel)
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    AuthService.change_password(db, current_user.id, data.old_password, data.new_password)
    return ResponseModel(message="Password changed")


@router.get("/usage-logs", response_model=ResponseModel)
def get_usage_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    items, total = LogService.list_request_logs(
        db, page, page_size, user_id=current_user.id,
        status=status, start_date=start_date, end_date=end_date,
        include_internal_fields=True,
    )
    items = LogService.build_user_visible_request_log_items(items)

    # Calculate summary statistics for the filtered date range
    summary = LogService.get_usage_summary(
        db, current_user.id, start_date=start_date, end_date=end_date
    )
    cache_visible = (
        (bool(get_system_config(db, "anthropic_prompt_cache_enabled", False)) and bool(
            get_system_config(db, "anthropic_prompt_cache_user_visible", False)
        ))
        or bool(get_system_config(db, "conversation_state_user_visible", False))
    )

    return ResponseModel(data={
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
        "cache_visible": cache_visible,
    })


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return public site config values for frontend display."""
    keys = {
        "anthropic_prompt_cache_enabled",
        "anthropic_prompt_cache_user_visible",
        "conversation_state_compaction_enabled",
        "conversation_state_user_visible",
    }
    configs = db.query(SystemConfig).filter(SystemConfig.config_key.in_(keys)).all()
    result = AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    result["api_base_url"] = result.get("quickstart_api_base_url") or result.get("api_base_url")
    result["quickstart_api_base_url"] = result.get("quickstart_api_base_url") or result.get("api_base_url")
    for config in configs:
        result[config.config_key] = config.config_value
    return ResponseModel(data=result)


@router.get("/announcements", response_model=ResponseModel)
def get_announcements(
    request: Request,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return fixed and published announcements for the current site."""
    site_config = AgentService.build_public_site_config(
        db,
        host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    fixed_title = site_config.get("announcement_title") or "平台公告"
    fixed_content = site_config.get("announcement_content") or ""
    result = []
    if fixed_content:
        fixed_id = f"fixed-{site_config.get('site_scope') or 'platform'}-{site_config.get('agent_id') or 'platform'}"
        result.append({
            "id": fixed_id,
            "title": fixed_title,
            "content": fixed_content,
            "source": "fixed",
            "popup": True,
            "show_popup": True,
            "support_wechat": site_config.get("support_wechat") or "",
            "support_qq": site_config.get("support_qq") or "",
            "published_at": None,
        })

    published_items = (
        db.query(PlatformAnnouncement)
        .filter(PlatformAnnouncement.status == "published")
        .order_by(PlatformAnnouncement.sort_order.desc(), PlatformAnnouncement.id.desc())
        .all()
    )
    for item in published_items:
        result.append({
            "id": f"platform-{item.id}",
            "title": item.title,
            "content": item.content,
            "source": "platform",
            "popup": bool(item.show_popup),
            "show_popup": bool(item.show_popup),
            "support_wechat": "",
            "support_qq": "",
            "published_at": item.published_at.isoformat() if item.published_at else None,
        })
    return ResponseModel(data=result)


@router.get("/per-minute-stats", response_model=ResponseModel)
def get_per_minute_stats(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Get per-minute request and token statistics."""
    stats = LogService.get_per_minute_stats(
        db, current_user.id, start_date=start_date, end_date=end_date
    )
    return ResponseModel(data=stats)
