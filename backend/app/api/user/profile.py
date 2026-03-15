from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.log_service import LogService
from app.models.log import SystemConfig
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
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    items, total = LogService.list_request_logs(
        db, page, page_size, user_id=current_user.id,
        start_date=start_date, end_date=end_date
    )

    # Calculate summary statistics for the filtered date range
    summary = LogService.get_usage_summary(
        db, current_user.id, start_date=start_date, end_date=end_date
    )

    return ResponseModel(data={
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary
    })


@router.get("/site-config", response_model=ResponseModel)
def get_site_config(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Return public site config values for frontend display."""
    keys = ["api_base_url"]
    configs = db.query(SystemConfig).filter(SystemConfig.config_key.in_(keys)).all()
    result = {c.config_key: c.config_value for c in configs}
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
