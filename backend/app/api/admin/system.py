from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import ServiceException
from app.models.user import SysUser
from app.models.log import PlatformAnnouncement, SystemConfig
from app.schemas.common import ResponseModel
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/admin/system", tags=["管理-系统配置"])


class ConfigUpdate(BaseModel):
    config_value: str
    description: Optional[str] = None


class AnnouncementConfigUpdate(BaseModel):
    announcement_title: str = Field(..., max_length=128)
    announcement_content: str
    support_wechat: Optional[str] = Field("", max_length=128)
    support_qq: Optional[str] = Field("", max_length=64)


class AnnouncementPayload(BaseModel):
    title: str = Field(..., max_length=128)
    content: str
    show_popup: bool = True
    sort_order: int = 0
    status: Optional[str] = "draft"


class AnnouncementStatusUpdate(BaseModel):
    status: str


ANNOUNCEMENT_CONFIG_KEYS = {
    "platform_announcement_title": "平台公告",
    "platform_announcement_content": "",
    "platform_support_wechat": "",
    "platform_support_qq": "",
}


def _get_config_map(db: Session, keys: dict[str, str]) -> dict[str, str]:
    rows = db.query(SystemConfig).filter(SystemConfig.config_key.in_(keys.keys())).all()
    result = dict(keys)
    for row in rows:
        result[row.config_key] = row.config_value
    return result


def _upsert_config(db: Session, key: str, value: str, description: str) -> None:
    config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
    if config:
        config.config_value = value
        config.description = description
        return
    db.add(SystemConfig(
        config_key=key,
        config_value=value,
        config_type="string",
        description=description,
    ))


def _announcement_to_dict(item: PlatformAnnouncement) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "status": item.status,
        "show_popup": bool(item.show_popup),
        "sort_order": item.sort_order,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "created_by_user_id": item.created_by_user_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _normalize_announcement_payload(data: AnnouncementPayload) -> dict:
    title = data.title.strip()
    content = data.content.strip()
    status = str(data.status or "draft").strip().lower()
    if not title:
        raise ServiceException(400, "公告标题不能为空", "INVALID_ANNOUNCEMENT_TITLE")
    if not content:
        raise ServiceException(400, "公告内容不能为空", "INVALID_ANNOUNCEMENT_CONTENT")
    if status not in {"draft", "published", "offline"}:
        raise ServiceException(400, "公告状态无效", "INVALID_ANNOUNCEMENT_STATUS")
    return {
        "title": title,
        "content": content,
        "show_popup": 1 if data.show_popup else 0,
        "sort_order": data.sort_order,
        "status": status,
    }


@router.get("/configs", response_model=ResponseModel)
def list_configs(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    configs = db.query(SystemConfig).order_by(SystemConfig.id).all()
    result = [
        {
            "id": c.id,
            "config_key": c.config_key,
            "config_value": c.config_value,
            "config_type": c.config_type,
            "description": c.description,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in configs
    ]
    return ResponseModel(data=result)


@router.put("/configs/{config_id}", response_model=ResponseModel)
def update_config(
    config_id: int,
    data: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    config = db.query(SystemConfig).filter(SystemConfig.id == config_id).first()
    if not config:
        from app.core.exceptions import ServiceException
        raise ServiceException(404, "Config not found")
    config.config_value = data.config_value
    if data.description is not None:
        config.description = data.description
    db.commit()
    db.refresh(config)
    return ResponseModel(data={
        "id": config.id,
        "config_key": config.config_key,
        "config_value": config.config_value,
        "config_type": config.config_type,
        "description": config.description,
    })


@router.get("/announcements/config", response_model=ResponseModel)
def get_announcement_config(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    config_map = _get_config_map(db, ANNOUNCEMENT_CONFIG_KEYS)
    return ResponseModel(data={
        "announcement_title": config_map["platform_announcement_title"],
        "announcement_content": config_map["platform_announcement_content"],
        "support_wechat": config_map["platform_support_wechat"],
        "support_qq": config_map["platform_support_qq"],
    })


@router.put("/announcements/config", response_model=ResponseModel)
def update_announcement_config(
    data: AnnouncementConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    title = data.announcement_title.strip()
    content = data.announcement_content.strip()
    if not title:
        raise ServiceException(400, "固定公告标题不能为空", "INVALID_ANNOUNCEMENT_TITLE")
    if not content:
        raise ServiceException(400, "固定公告内容不能为空", "INVALID_ANNOUNCEMENT_CONTENT")
    _upsert_config(db, "platform_announcement_title", title, "平台直营站点公告标题")
    _upsert_config(db, "platform_announcement_content", content, "平台直营站点公告内容")
    _upsert_config(db, "platform_support_wechat", (data.support_wechat or "").strip(), "平台直营站点微信联系方式")
    _upsert_config(db, "platform_support_qq", (data.support_qq or "").strip(), "平台直营站点QQ联系方式")
    db.commit()
    return ResponseModel(message="公告配置已保存")


@router.get("/announcements", response_model=ResponseModel)
def list_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    query = db.query(PlatformAnnouncement)
    if status:
        query = query.filter(PlatformAnnouncement.status == status)
    total = query.count()
    items = (
        query.order_by(PlatformAnnouncement.sort_order.desc(), PlatformAnnouncement.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ResponseModel(data={
        "list": [_announcement_to_dict(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/announcements", response_model=ResponseModel)
def create_announcement(
    data: AnnouncementPayload,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    payload = _normalize_announcement_payload(data)
    item = PlatformAnnouncement(
        **payload,
        published_at=datetime.now() if payload["status"] == "published" else None,
        created_by_user_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ResponseModel(data=_announcement_to_dict(item), message="公告已创建")


@router.put("/announcements/{announcement_id}", response_model=ResponseModel)
def update_announcement(
    announcement_id: int,
    data: AnnouncementPayload,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    item = db.query(PlatformAnnouncement).filter(PlatformAnnouncement.id == announcement_id).first()
    if not item:
        raise ServiceException(404, "公告不存在", "ANNOUNCEMENT_NOT_FOUND")
    payload = _normalize_announcement_payload(data)
    was_published = item.status == "published"
    for key, value in payload.items():
        setattr(item, key, value)
    if item.status == "published" and not was_published:
        item.published_at = datetime.now()
    db.commit()
    db.refresh(item)
    return ResponseModel(data=_announcement_to_dict(item), message="公告已保存")


@router.delete("/announcements/{announcement_id}", response_model=ResponseModel)
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    item = db.query(PlatformAnnouncement).filter(PlatformAnnouncement.id == announcement_id).first()
    if not item:
        raise ServiceException(404, "公告不存在", "ANNOUNCEMENT_NOT_FOUND")
    db.delete(item)
    db.commit()
    return ResponseModel(message="公告已删除")


@router.put("/announcements/{announcement_id}/status", response_model=ResponseModel)
def update_announcement_status(
    announcement_id: int,
    data: AnnouncementStatusUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    status = str(data.status or "").strip().lower()
    if status not in {"draft", "published", "offline"}:
        raise ServiceException(400, "公告状态无效", "INVALID_ANNOUNCEMENT_STATUS")
    item = db.query(PlatformAnnouncement).filter(PlatformAnnouncement.id == announcement_id).first()
    if not item:
        raise ServiceException(404, "公告不存在", "ANNOUNCEMENT_NOT_FOUND")
    was_published = item.status == "published"
    item.status = status
    if status == "published" and not was_published:
        item.published_at = datetime.now()
    db.commit()
    db.refresh(item)
    return ResponseModel(data=_announcement_to_dict(item), message="公告状态已更新")


@router.get("/dashboard", response_model=ResponseModel)
def get_dashboard_stats(
    range_key: str = Query("7d", alias="range"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    from app.models.log import ConsumptionRecord, RequestLog
    from app.models.model import UnifiedModel
    from sqlalchemy import func
    from app.services.log_service import LogService

    today, _ = LogService._get_timezone_day_window(1)
    user_total = db.query(func.count(SysUser.id)).filter(
        SysUser.role == "user"
    ).scalar()
    model_total = db.query(func.count(UnifiedModel.id)).scalar()

    today_requests = db.query(func.count(RequestLog.id)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_tokens = db.query(func.coalesce(func.sum(RequestLog.total_tokens), 0)).filter(
        RequestLog.created_at >= today
    ).scalar()
    today_cost = db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0)).filter(
        ConsumptionRecord.created_at >= today,
        ConsumptionRecord.total_cost > 0,
        ConsumptionRecord.request_id.isnot(None),
        ConsumptionRecord.model_name.isnot(None),
    ).scalar()

    return ResponseModel(data={
        "user_total": int(user_total or 0),
        "model_total": int(model_total or 0),
        "today_requests": today_requests,
        "today_tokens": int(today_tokens),
        "today_cost": float(today_cost or 0),
    })
