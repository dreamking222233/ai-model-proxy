"""User media workbench health summary service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, case, func, not_, or_
from sqlalchemy.orm import Session

from app.models.log import RequestLog
from app.services.log_service import LogService


class MediaWorkbenchService:
    """Build user-facing media invocation health summaries."""

    IMAGE_MODELS = ("gpt-image-2", "codex-gpt-image-2", "plus-codex-gpt-image-2")
    IMAGE_REQUEST_TYPES = ("image_generation", "image_edit")
    VIDEO_MODELS = ("grok-imagine-video",)
    VIDEO_REQUEST_TYPES = ("video_generation",)
    LOCAL_ERROR_MARKERS = (
        "INSUFFICIENT_IMAGE_CREDITS",
        "IMAGE_CREDIT_BALANCE_NOT_FOUND",
        "INVALID_IMAGE_CREDIT_AMOUNT",
        "IMAGE_MODEL_NOT_FOUND",
        "IMAGE_MODEL_NOT_SUPPORTED",
        "INVALID_IMAGE_PROMPT",
        "INVALID_IMAGE_SIZE",
        "IMAGE_SIZE_NOT_SUPPORTED",
        "IMAGE_SIZE_NOT_ENABLED",
        "VIDEO_MODEL_NOT_FOUND",
        "VIDEO_MODEL_NOT_SUPPORTED",
        "INVALID_VIDEO",
        "缺少必填字段",
        "积分不足",
        "余额不足",
        "当前模型不是",
        "当前模型未配置",
        "参数无效",
    )

    @staticmethod
    def _health_level(request_count: int, success_rate: float) -> str:
        if request_count <= 0:
            return "unknown"
        if success_rate >= 95:
            return "good"
        if success_rate >= 80:
            return "warning"
        return "bad"

    @staticmethod
    def _local_error_condition():
        error_message = func.coalesce(RequestLog.error_message, "")
        conditions = [
            error_message.like(f"%{marker}%")
            for marker in MediaWorkbenchService.LOCAL_ERROR_MARKERS
        ]
        return and_(
            RequestLog.status.in_(("error", "failed")),
            RequestLog.channel_id.is_(None),
            or_(*conditions),
        )

    @staticmethod
    def _empty_summary(
        key: str,
        label: str,
        model: str,
        request_types: tuple[str, ...],
        since: datetime,
        until: datetime,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "model": model,
            "request_types": list(request_types),
            "window_hours": round((until - since).total_seconds() / 3600, 1),
            "request_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "success_rate": 0.0,
            "avg_response_time_ms": 0,
            "last_request_at": None,
            "health_level": "unknown",
        }

    @staticmethod
    def _build_summary(
        db: Session,
        *,
        key: str,
        label: str,
        models: tuple[str, ...],
        request_types: tuple[str, ...],
        since: datetime,
        until: datetime,
    ) -> dict[str, Any]:
        summary = MediaWorkbenchService._empty_summary(
            key,
            label,
            models[0] if len(models) == 1 else ",".join(models),
            request_types,
            since,
            until,
        )
        success_expr = LogService._visible_success_condition()
        local_error_expr = MediaWorkbenchService._local_error_condition()

        row = (
            db.query(
                func.count(RequestLog.id).label("request_count"),
                func.sum(case((success_expr, 1), else_=0)).label("success_count"),
                func.avg(RequestLog.response_time_ms).label("avg_response_time_ms"),
                func.max(RequestLog.created_at).label("last_request_at"),
            )
            .filter(
                RequestLog.created_at >= since,
                RequestLog.created_at < until,
                RequestLog.requested_model.in_(models),
                RequestLog.request_type.in_(request_types),
                not_(local_error_expr),
            )
            .first()
        )

        request_count = int(row.request_count or 0) if row else 0
        success_count = int(row.success_count or 0) if row else 0
        failed_count = max(0, request_count - success_count)
        success_rate = round((success_count / request_count) * 100, 1) if request_count else 0.0

        summary.update({
            "request_count": request_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_rate,
            "avg_response_time_ms": int(row.avg_response_time_ms or 0) if row else 0,
            "last_request_at": row.last_request_at.isoformat() if row and row.last_request_at else None,
            "health_level": MediaWorkbenchService._health_level(request_count, success_rate),
        })
        return summary

    @staticmethod
    def get_media_health(db: Session, window_hours: int = 24) -> dict[str, Any]:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        hours = min(max(int(window_hours or 24), 1), 168)
        since = now - timedelta(hours=hours)
        items = {
            "image_gpt_image_2": MediaWorkbenchService._build_summary(
                db,
                key="image_gpt_image_2",
                label="生图 gpt-image-2",
                models=MediaWorkbenchService.IMAGE_MODELS,
                request_types=MediaWorkbenchService.IMAGE_REQUEST_TYPES,
                since=since,
                until=now,
            ),
            "video_grok": MediaWorkbenchService._build_summary(
                db,
                key="video_grok",
                label="Grok 视频生成",
                models=MediaWorkbenchService.VIDEO_MODELS,
                request_types=MediaWorkbenchService.VIDEO_REQUEST_TYPES,
                since=since,
                until=now,
            ),
        }
        return {
            "window_hours": hours,
            "items": items,
        }
