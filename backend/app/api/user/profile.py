from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.log_service import LogService
from app.services.health_service import get_system_config
from app.services.agent_service import AgentService
from app.models.log import PlatformAnnouncement, SystemConfig
from app.models.payment import PaymentRechargeOrder
from app.schemas.user import PasswordChange
from app.schemas.common import ResponseModel
from fastapi import Query

router = APIRouter(prefix="/api/user/profile", tags=["用户-个人信息"])

SUPPORT_CONTACT_THRESHOLD_CNY = Decimal("100.00")
SUPPORT_CONTACT_THRESHOLD_CONFIG_KEY = "platform_support_contact_threshold_cny"


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_support_contact_threshold_cny(db: Session) -> Decimal:
    row = db.query(SystemConfig).filter(SystemConfig.config_key == SUPPORT_CONTACT_THRESHOLD_CONFIG_KEY).first()
    raw_value = row.config_value if row else SUPPORT_CONTACT_THRESHOLD_CNY
    try:
        threshold = Decimal(str(raw_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        threshold = SUPPORT_CONTACT_THRESHOLD_CNY
    return max(threshold, Decimal("0.00"))


def _get_platform_support_contact_status(db: Session, user_id: int) -> dict:
    threshold = _get_support_contact_threshold_cny(db)
    paid_total = (
        db.query(func.coalesce(func.sum(PaymentRechargeOrder.amount_cny), 0))
        .filter(
            PaymentRechargeOrder.user_id == user_id,
            PaymentRechargeOrder.agent_id.is_(None),
            PaymentRechargeOrder.site_scope == "platform",
            PaymentRechargeOrder.status == "paid",
            PaymentRechargeOrder.recharge_type.in_(("balance", "subscription")),
        )
        .scalar()
    )
    paid_cny = _money(paid_total)
    visible = paid_cny > threshold
    next_visible_amount = threshold + Decimal("0.01")
    remaining = max(next_visible_amount - paid_cny, Decimal("0.00"))
    threshold_display = f"{threshold.normalize():f}"
    notice = (
        f"成功充值余额或购买套餐累计超过 {threshold_display} 元后，可查看官方 QQ 和微信联系方式。"
        f"当前累计 ¥{paid_cny:.2f}，还差 ¥{remaining:.2f}。"
    )
    return {
        "support_contact_visible": visible,
        "support_contact_threshold_cny": float(threshold),
        "support_contact_paid_cny": float(paid_cny),
        "support_contact_notice": "" if visible else notice,
    }


def _apply_platform_support_contact_gate(db: Session, current_user: SysUser, payload: dict) -> dict:
    result = dict(payload)
    if getattr(current_user, "agent_id", None) is not None or result.get("site_scope") != "platform":
        result.update({
            "support_contact_visible": True,
            "support_contact_threshold_cny": float(SUPPORT_CONTACT_THRESHOLD_CNY),
            "support_contact_paid_cny": None,
            "support_contact_notice": "",
        })
        return result

    contact_status = _get_platform_support_contact_status(db, current_user.id)
    result.update(contact_status)
    if not contact_status["support_contact_visible"]:
        result["support_wechat"] = ""
        result["support_qq"] = ""
    return result


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
    result = _apply_platform_support_contact_gate(db, current_user, result)
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
    site_config = _apply_platform_support_contact_gate(db, current_user, site_config)
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
            "support_contact_visible": site_config.get("support_contact_visible", True),
            "support_contact_notice": site_config.get("support_contact_notice") or "",
            "support_contact_threshold_cny": site_config.get("support_contact_threshold_cny"),
            "support_contact_paid_cny": site_config.get("support_contact_paid_cny"),
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
            "support_contact_visible": True,
            "support_contact_notice": "",
            "support_contact_threshold_cny": None,
            "support_contact_paid_cny": None,
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
