"""Request log, operation log, and statistics service."""
from __future__ import annotations

import json
from typing import Optional

from datetime import datetime, timedelta

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.log import RequestLog, OperationLog, ConsumptionRecord, RequestCacheSummary
from app.models.user import SysUser
from app.core.exceptions import ServiceException


class LogService:
    """Query and create log records, compute aggregated statistics."""

    @staticmethod
    def _parse_date_filters(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        start_dt: Optional[datetime] = None
        end_dt: Optional[datetime] = None

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                start_dt = None

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            except ValueError:
                end_dt = None

        return start_dt, end_dt

    @staticmethod
    def _load_cache_details(details_json: Optional[str]) -> Optional[dict]:
        """Parse cached request-summary JSON safely."""
        if not details_json:
            return None
        try:
            return json.loads(details_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def list_request_logs(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        List request logs with pagination and optional filters.

        Args:
            start_date / end_date: ISO date strings (YYYY-MM-DD).

        Returns:
            Tuple of (list of log dicts, total count).
        """
        query = db.query(
            RequestLog,
            SysUser.username,
            ConsumptionRecord.total_cost,
            RequestCacheSummary.details_json,
        ).outerjoin(
            SysUser, RequestLog.user_id == SysUser.id
        ).outerjoin(
            ConsumptionRecord, RequestLog.request_id == ConsumptionRecord.request_id
        ).outerjoin(
            RequestCacheSummary, RequestLog.request_id == RequestCacheSummary.request_id
        )

        if user_id is not None:
            query = query.filter(RequestLog.user_id == user_id)
        if model:
            query = query.filter(RequestLog.requested_model == model)
        if status:
            query = query.filter(RequestLog.status == status)
        start_dt, end_dt = LogService._parse_date_filters(start_date, end_date)
        if start_dt:
            query = query.filter(RequestLog.created_at >= start_dt)
        if end_dt:
            query = query.filter(RequestLog.created_at < end_dt)

        total = query.count()
        rows = (
            query.order_by(RequestLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = [
            {
                "id": log.id,
                "request_id": log.request_id,
                "user_id": log.user_id,
                "username": username,
                "user_api_key_id": log.user_api_key_id,
                "channel_id": log.channel_id,
                "channel_name": log.channel_name,
                "requested_model": log.requested_model,
                "actual_model": log.actual_model,
                "protocol_type": log.protocol_type,
                "request_type": log.request_type,
                "billing_type": log.billing_type,
                "is_stream": bool(log.is_stream),
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "image_credits_charged": int(log.image_credits_charged or 0),
                "image_count": int(log.image_count or 0),
                "response_time_ms": log.response_time_ms,
                "cache_status": log.cache_status,
                "cache_hit_segments": log.cache_hit_segments or 0,
                "cache_miss_segments": log.cache_miss_segments or 0,
                "cache_bypass_segments": log.cache_bypass_segments or 0,
                "cache_reused_tokens": log.cache_reused_tokens or 0,
                "cache_new_tokens": log.cache_new_tokens or 0,
                "cache_reused_chars": log.cache_reused_chars or 0,
                "cache_new_chars": log.cache_new_chars or 0,
                "logical_input_tokens": log.logical_input_tokens or 0,
                "upstream_input_tokens": log.upstream_input_tokens or 0,
                "upstream_cache_read_input_tokens": log.upstream_cache_read_input_tokens or 0,
                "upstream_cache_creation_input_tokens": log.upstream_cache_creation_input_tokens or 0,
                "upstream_cache_creation_5m_input_tokens": log.upstream_cache_creation_5m_input_tokens or 0,
                "upstream_cache_creation_1h_input_tokens": log.upstream_cache_creation_1h_input_tokens or 0,
                "upstream_prompt_cache_status": log.upstream_prompt_cache_status or "BYPASS",
                "conversation_session_id": log.conversation_session_id,
                "conversation_match_status": log.conversation_match_status,
                "compression_mode": log.compression_mode,
                "compression_status": log.compression_status,
                "original_estimated_input_tokens": log.original_estimated_input_tokens or 0,
                "compressed_estimated_input_tokens": log.compressed_estimated_input_tokens or 0,
                "compression_saved_estimated_tokens": log.compression_saved_estimated_tokens or 0,
                "compression_ratio": float(log.compression_ratio or 0),
                "compression_fallback_reason": log.compression_fallback_reason,
                "upstream_session_mode": log.upstream_session_mode,
                "upstream_session_id": log.upstream_session_id,
                "status": log.status,
                "error_message": log.error_message,
                "client_ip": log.client_ip,
                "total_cost": float(total_cost) if total_cost else 0.0,
                "cache_details": LogService._load_cache_details(cache_details),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log, username, total_cost, cache_details in rows
        ]
        return result, total

    @staticmethod
    def get_admin_user_usage_summary(
        db: Session,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        start_dt, end_dt = LogService._parse_date_filters(start_date, end_date)

        request_query = db.query(RequestLog).filter(RequestLog.user_id == user_id)
        if start_dt:
            request_query = request_query.filter(RequestLog.created_at >= start_dt)
        if end_dt:
            request_query = request_query.filter(RequestLog.created_at < end_dt)

        stats = request_query.with_entities(
            func.count(RequestLog.id).label("request_count"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(RequestLog.image_credits_charged), 0).label("image_credits"),
            func.sum(func.IF(RequestLog.status == "success", 1, 0)).label("success_count"),
            func.sum(func.IF(RequestLog.status != "success", 1, 0)).label("failed_count"),
            func.avg(RequestLog.response_time_ms).label("avg_response_time_ms"),
            func.max(RequestLog.created_at).label("last_request_at"),
        ).first()

        cost_query = db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0)).filter(
            ConsumptionRecord.user_id == user_id,
            ConsumptionRecord.total_cost > 0,
            ConsumptionRecord.model_name.isnot(None),
        )
        if start_dt:
            cost_query = cost_query.filter(ConsumptionRecord.created_at >= start_dt)
        if end_dt:
            cost_query = cost_query.filter(ConsumptionRecord.created_at < end_dt)
        total_cost = cost_query.scalar() or 0

        request_count = int(stats.request_count or 0)
        success_count = int(stats.success_count or 0)
        failed_count = int(stats.failed_count or 0)

        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "summary": {
                "request_count": request_count,
                "success_count": success_count,
                "failed_count": failed_count,
                "success_rate": round((success_count / request_count) * 100, 1) if request_count > 0 else 100.0,
                "input_tokens": int(stats.input_tokens or 0),
                "output_tokens": int(stats.output_tokens or 0),
                "total_tokens": int(stats.total_tokens or 0),
                "image_credits": int(stats.image_credits or 0),
                "total_cost": float(total_cost),
                "avg_response_time_ms": float(stats.avg_response_time_ms or 0),
                "last_request_at": stats.last_request_at.isoformat() if stats.last_request_at else None,
            },
            "range": {
                "start_date": start_date,
                "end_date": end_date,
            },
        }

    @staticmethod
    def get_request_stats(db: Session, days: int = 7) -> list[dict]:
        """
        Get daily aggregated request statistics for the past N days.

        Returns:
            List of dicts with keys: ``date``, ``total_requests``,
            ``success_requests``, ``failed_requests``, ``total_input_tokens``,
            ``total_output_tokens``, ``total_tokens``, ``total_cost``.
        """
        since = datetime.utcnow() - timedelta(days=days)

        rows = (
            db.query(
                func.date(RequestLog.created_at).label("date"),
                func.count(RequestLog.id).label("total_requests"),
                func.sum(
                    func.IF(RequestLog.status == "success", 1, 0)
                ).label("success_requests"),
                func.sum(
                    func.IF(RequestLog.status != "success", 1, 0)
                ).label("failed_requests"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            )
            .filter(RequestLog.created_at >= since)
            .group_by(func.date(RequestLog.created_at))
            .order_by(func.date(RequestLog.created_at).asc())
            .all()
        )

        return [
            {
                "date": str(row.date),
                "total_requests": int(row.total_requests),
                "success_requests": int(row.success_requests or 0),
                "failed_requests": int(row.failed_requests or 0),
                "total_input_tokens": int(row.total_input_tokens),
                "total_output_tokens": int(row.total_output_tokens),
                "total_tokens": int(row.total_tokens),
            }
            for row in rows
        ]

    @staticmethod
    def list_operation_logs(
        db: Session,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        List operation (audit) logs with pagination.

        Returns:
            Tuple of (list of log dicts, total count).
        """
        query = db.query(OperationLog)
        total = query.count()
        logs = (
            query.order_by(OperationLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        result = [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "description": log.description,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
        return result, total

    @staticmethod
    def create_operation_log(
        db: Session,
        user_id: Optional[int],
        username: Optional[str],
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        description: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> OperationLog:
        """
        Create an operation audit log entry.

        Returns:
            The created OperationLog instance.
        """
        log = OperationLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            description=description,
            ip_address=ip,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

        return result, total

    @staticmethod
    def get_user_model_stats(db: Session, user_id: int, days: int = 1) -> dict:
        """
        Get model usage statistics for a specific user.

        Args:
            user_id: The user to query for.
            days: Number of days to look back (1 = today, 7 = last 7 days).

        Returns:
            Dict with ``by_model``, ``daily_trend``, and ``summary``.
        """
        now = datetime.utcnow()
        since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        base_filter = and_(
            RequestLog.user_id == user_id,
            RequestLog.created_at >= since,
        )

        # --- by_model ---
        model_rows = (
            db.query(
                RequestLog.requested_model.label("model_name"),
                func.count(RequestLog.id).label("request_count"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                func.sum(func.IF(RequestLog.status == "success", 1, 0)).label("success_count"),
            )
            .filter(base_filter)
            .group_by(RequestLog.requested_model)
            .order_by(func.count(RequestLog.id).desc())
            .all()
        )

        by_model = [
            {
                "model_name": row.model_name or "unknown",
                "request_count": int(row.request_count),
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.total_tokens),
                "success_count": int(row.success_count or 0),
            }
            for row in model_rows
        ]

        # --- daily_trend ---
        trend_rows = (
            db.query(
                func.date(RequestLog.created_at).label("date"),
                func.count(RequestLog.id).label("request_count"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                func.sum(func.IF(RequestLog.status == "success", 1, 0)).label("success_count"),
                func.sum(func.IF(RequestLog.status != "success", 1, 0)).label("failed_count"),
            )
            .filter(base_filter)
            .group_by(func.date(RequestLog.created_at))
            .order_by(func.date(RequestLog.created_at).asc())
            .all()
        )

        daily_trend = [
            {
                "date": str(row.date),
                "request_count": int(row.request_count),
                "total_tokens": int(row.total_tokens),
                "success_count": int(row.success_count or 0),
                "failed_count": int(row.failed_count or 0),
            }
            for row in trend_rows
        ]

        # --- summary ---
        total_requests = sum(m["request_count"] for m in by_model)
        total_tokens = sum(m["total_tokens"] for m in by_model)
        total_success = sum(m["success_count"] for m in by_model)

        # Get total cost from consumption records (only positive costs, exclude recharge records)
        cost_row = (
            db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0))
            .filter(
                ConsumptionRecord.user_id == user_id,
                ConsumptionRecord.created_at >= since,
                ConsumptionRecord.total_cost > 0,  # Only count actual consumption
                ConsumptionRecord.model_name.isnot(None),  # Exclude recharge records
            )
            .scalar()
        )

        return {
            "by_model": by_model,
            "daily_trend": daily_trend,
            "summary": {
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "total_success": total_success,
                "total_failed": total_requests - total_success,
                "total_cost": float(cost_row or 0),
            },
        }

    @staticmethod
    def get_token_ranking(db: Session, days: int = 1, limit: int = 5) -> list[dict]:
        """
        Get top users by token usage within the given time window.
        """
        now = datetime.utcnow()
        since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        rows = (
            db.query(
                SysUser.id.label("user_id"),
                SysUser.username,
                SysUser.role,
                SysUser.avatar,
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.count(RequestLog.id).label("request_count"),
                func.max(RequestLog.created_at).label("last_used_at"),
            )
            .join(SysUser, SysUser.id == RequestLog.user_id)
            .filter(
                RequestLog.user_id.isnot(None),
                RequestLog.created_at >= since,
            )
            .group_by(SysUser.id, SysUser.username, SysUser.role, SysUser.avatar)
            .order_by(
                func.coalesce(func.sum(RequestLog.total_tokens), 0).desc(),
                func.count(RequestLog.id).desc(),
                func.max(RequestLog.created_at).desc(),
                SysUser.id.asc(),
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "rank": index + 1,
                "user_id": row.user_id,
                "username": row.username,
                "role": row.role,
                "avatar": row.avatar,
                "total_tokens": int(row.total_tokens or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "request_count": int(row.request_count or 0),
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            }
            for index, row in enumerate(rows)
        ]

    @staticmethod
    def list_consumption_records(
        db: Session, page: int = 1, page_size: int = 20, user_id: int = None,
    ) -> tuple[list[dict], int]:
        query = db.query(ConsumptionRecord)
        if user_id is not None:
            query = query.filter(ConsumptionRecord.user_id == user_id)
        total = query.count()
        records = query.order_by(ConsumptionRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        result = [
            {
                "id": r.id, "user_id": r.user_id, "request_id": r.request_id,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "input_cost": float(r.input_cost), "output_cost": float(r.output_cost),
                "total_cost": float(r.total_cost),
                "balance_before": float(r.balance_before), "balance_after": float(r.balance_after),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
        return result, total

    @staticmethod
    def get_usage_summary(
        db: Session,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        Get usage summary statistics for a user within a date range.

        Returns:
            Dict with todayRequests, todayTokens, successRate.
        """
        query = db.query(RequestLog).filter(RequestLog.user_id == user_id)

        if start_date:
            try:
                dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(RequestLog.created_at >= dt)
            except ValueError:
                pass

        if end_date:
            try:
                dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(RequestLog.created_at < dt)
            except ValueError:
                pass

        # Get aggregated statistics
        stats = query.with_entities(
            func.count(RequestLog.id).label("total_requests"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            func.sum(func.IF(RequestLog.status == "success", 1, 0)).label("success_count"),
        ).first()

        total_requests = int(stats.total_requests or 0)
        total_tokens = int(stats.total_tokens or 0)
        success_count = int(stats.success_count or 0)
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 100

        return {
            "todayRequests": total_requests,
            "todayTokens": total_tokens,
            "successRate": round(success_rate, 1),
        }

    @staticmethod
    def get_per_minute_stats(
        db: Session,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Get per-minute request and token statistics for a user.

        Args:
            user_id: The user to query for.
            start_date: Start date (YYYY-MM-DD), defaults to today.
            end_date: End date (YYYY-MM-DD), defaults to today.

        Returns:
            List of dicts with keys: minute, request_count, total_tokens, success_count.
        """
        query = db.query(RequestLog).filter(RequestLog.user_id == user_id)

        if start_date:
            try:
                dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(RequestLog.created_at >= dt)
            except ValueError:
                pass
        else:
            # Default to today
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(RequestLog.created_at >= today)

        if end_date:
            try:
                dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                query = query.filter(RequestLog.created_at < dt)
            except ValueError:
                pass

        # Group by minute: DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:00')
        rows = (
            query.with_entities(
                func.date_format(RequestLog.created_at, '%Y-%m-%d %H:%i:00').label("minute"),
                func.count(RequestLog.id).label("request_count"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                func.sum(func.IF(RequestLog.status == "success", 1, 0)).label("success_count"),
            )
            .group_by(func.date_format(RequestLog.created_at, '%Y-%m-%d %H:%i:00'))
            .order_by(func.date_format(RequestLog.created_at, '%Y-%m-%d %H:%i:00').asc())
            .all()
        )

        return [
            {
                "minute": row.minute,
                "request_count": int(row.request_count),
                "total_tokens": int(row.total_tokens),
                "success_count": int(row.success_count or 0),
            }
            for row in rows
        ]
