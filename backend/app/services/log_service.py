"""Request log, operation log, and statistics service."""
from __future__ import annotations

import json
from typing import Optional

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, and_, or_, not_
from sqlalchemy.orm import Session

from app.models.log import RequestLog, OperationLog, ConsumptionRecord, RequestCacheSummary
from app.models.user import SysUser
from app.core.exceptions import ServiceException


class LogService:
    """Query and create log records, compute aggregated statistics."""

    DEFAULT_TIMEZONE = "Asia/Shanghai"
    REQUEST_STATS_RANGES = {
        "today": 1,
        "7d": 7,
        "30d": 30,
    }
    ACCOUNTING_FAILURE_PREFIX = "本地计费或记账失败："

    @staticmethod
    def _public_actual_model_name(requested_model: Optional[str], actual_model: Optional[str]) -> Optional[str]:
        requested_text = str(requested_model or "").strip()
        actual_text = str(actual_model or "").strip()
        if not actual_text:
            return actual_model
        if requested_text == "claude-opus-4-6":
            return requested_text
        return actual_model

    @staticmethod
    def _get_timezone_day_window(days: int = 1, tz_name: str = DEFAULT_TIMEZONE) -> tuple[datetime, datetime]:
        zone = ZoneInfo(tz_name)
        local_now = datetime.now(timezone.utc).astimezone(zone)
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=max(days, 1) - 1)
        return local_start.replace(tzinfo=None), local_now.replace(tzinfo=None)

    @staticmethod
    def _resolve_request_stats_config(days: int = 7, range_key: Optional[str] = None) -> dict:
        normalized_range = str(range_key or "").strip().lower()
        if normalized_range == "today":
            since, until = LogService._get_timezone_day_window(1)
            return {
                "range_key": "today",
                "days": 1,
                "bucket_mode": "two_hour",
                "since": since,
                "until": until,
            }

        resolved_days = LogService.REQUEST_STATS_RANGES.get(normalized_range, max(int(days or 1), 1))
        since, until = LogService._get_timezone_day_window(resolved_days)
        return {
            "range_key": normalized_range or f"{resolved_days}d",
            "days": resolved_days,
            "bucket_mode": "day",
            "since": since,
            "until": until,
        }

    @staticmethod
    def _summarize_model_usage_rows(rows: list, limit: int = 6) -> list[dict]:
        total_requests = sum(int(row.request_count or 0) for row in rows)
        if total_requests <= 0:
            return []

        primary_rows = list(rows[:limit])
        remaining_rows = list(rows[limit:])
        result = [
            {
                "model_name": str(row.model_name or "unknown"),
                "request_count": int(row.request_count or 0),
                "total_tokens": int(row.total_tokens or 0),
                "ratio": round(int(row.request_count or 0) * 100 / total_requests, 1),
            }
            for row in primary_rows
        ]

        if remaining_rows:
            other_requests = sum(int(row.request_count or 0) for row in remaining_rows)
            other_tokens = sum(int(row.total_tokens or 0) for row in remaining_rows)
            result.append({
                "model_name": "其他",
                "request_count": other_requests,
                "total_tokens": other_tokens,
                "ratio": round(other_requests * 100 / total_requests, 1),
            })

        return result

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
    def _is_accounting_failure_after_success(status: Optional[str], error_message: Optional[str], total_tokens: int) -> bool:
        return (
            str(status or "").lower() in {"error", "failed"}
            and str(error_message or "").startswith(LogService.ACCOUNTING_FAILURE_PREFIX)
            and int(total_tokens or 0) > 0
        )

    @staticmethod
    def _visible_success_condition():
        return or_(
            RequestLog.status == "success",
            and_(
                RequestLog.status.in_(("error", "failed")),
                RequestLog.error_message.like(f"{LogService.ACCOUNTING_FAILURE_PREFIX}%"),
                func.coalesce(RequestLog.total_tokens, 0) > 0,
            ),
        )

    @staticmethod
    def _visible_failure_condition():
        return and_(
            RequestLog.status.in_(("error", "failed")),
            not_(LogService._visible_success_condition()),
        )

    @staticmethod
    def list_request_logs(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        agent_only: bool = False,
        platform_only: bool = False,
        include_internal_fields: bool = False,
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
            ConsumptionRecord.input_cost,
            ConsumptionRecord.output_cost,
            ConsumptionRecord.cache_read_cost,
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
        if agent_id is not None:
            query = query.filter(RequestLog.agent_id == agent_id)
        elif agent_only:
            query = query.filter(RequestLog.agent_id.isnot(None))
        elif platform_only:
            query = query.filter(RequestLog.agent_id.is_(None))
        if model:
            query = query.filter(RequestLog.requested_model == model)
        if status:
            normalized_status = str(status).strip().lower()
            if normalized_status == "success":
                query = query.filter(LogService._visible_success_condition())
            elif normalized_status in {"error", "failed"}:
                query = query.filter(LogService._visible_failure_condition())
            else:
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

        result = []
        for log, username, input_cost, output_cost, record_cache_read_cost, total_cost, cache_details in rows:
            item = {
                "id": log.id,
                "request_id": log.request_id,
                "user_id": log.user_id,
                "agent_id": log.agent_id,
                "username": username,
                "user_api_key_id": log.user_api_key_id,
                "channel_id": log.channel_id,
                "model": log.requested_model or "-",
                "protocol_type": log.protocol_type,
                "request_type": log.request_type,
                "billing_type": log.billing_type,
                "is_stream": bool(log.is_stream),
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "billable_input_tokens": log.billable_input_tokens or log.input_tokens or 0,
                "raw_input_tokens": log.raw_input_tokens or 0,
                "raw_output_tokens": log.raw_output_tokens or 0,
                "raw_total_tokens": log.raw_total_tokens or 0,
                "image_credits_charged": float(log.image_credits_charged or 0),
                "image_count": int(log.image_count or 0),
                "image_size": log.image_size,
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
                "billable_cache_read_input_tokens": log.billable_cache_read_input_tokens or log.upstream_cache_read_input_tokens or 0,
                "upstream_cache_creation_input_tokens": log.upstream_cache_creation_input_tokens or 0,
                "upstream_cache_creation_5m_input_tokens": log.upstream_cache_creation_5m_input_tokens or 0,
                "upstream_cache_creation_1h_input_tokens": log.upstream_cache_creation_1h_input_tokens or 0,
                "upstream_prompt_cache_status": log.upstream_prompt_cache_status or "BYPASS",
                "conversation_session_id": None,
                "conversation_match_status": None,
                "compression_mode": None,
                "compression_status": None,
                "original_estimated_input_tokens": 0,
                "compressed_estimated_input_tokens": 0,
                "compression_saved_estimated_tokens": 0,
                "compression_ratio": 0.0,
                "compression_fallback_reason": None,
                "upstream_session_mode": None,
                "upstream_session_id": None,
                "raw_status": log.status,
                "accounting_failed_after_success": LogService._is_accounting_failure_after_success(
                    log.status,
                    log.error_message,
                    log.total_tokens,
                ),
                "status": "success"
                if LogService._is_accounting_failure_after_success(log.status, log.error_message, log.total_tokens)
                else log.status,
                "error_message": log.error_message,
                "client_ip": log.client_ip,
                "subscription_cycle_id": log.subscription_cycle_id,
                "quota_metric": log.quota_metric,
                "quota_consumed_amount": float(log.quota_consumed_amount or 0),
                "quota_limit_snapshot": float(log.quota_limit_snapshot or 0),
                "quota_used_after": float(log.quota_used_after or 0),
                "quota_cycle_date": log.quota_cycle_date.isoformat() if log.quota_cycle_date else None,
                "cache_read_cost": float(log.cache_read_cost or record_cache_read_cost or 0),
                "input_price_per_million_snapshot": float(log.input_price_per_million_snapshot or 0),
                "output_price_per_million_snapshot": float(log.output_price_per_million_snapshot or 0),
                "price_multiplier_snapshot": float(log.price_multiplier_snapshot or 1),
                "fast_price_multiplier_snapshot": float(log.fast_price_multiplier_snapshot or 1),
                "service_tier": log.service_tier,
                "token_multiplier_snapshot": float(log.token_multiplier_snapshot or 1),
                "input_cost": float(input_cost or 0),
                "output_cost": float(output_cost or 0),
                "total_cost": float(total_cost) if total_cost else 0.0,
                "cache_details": LogService._load_cache_details(cache_details),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            if include_internal_fields:
                item["channel_name"] = log.channel_name
                item["requested_model"] = log.requested_model
                item["actual_model"] = LogService._public_actual_model_name(
                    log.requested_model,
                    log.actual_model,
                )
            result.append(item)
        return result, total

    @staticmethod
    def get_admin_user_usage_summary(
        db: Session,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        platform_only: bool = False,
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")
        if platform_only and user.agent_id is not None:
            raise ServiceException(404, "用户不属于平台主站", "USER_NOT_PLATFORM_SCOPE")

        start_dt, end_dt = LogService._parse_date_filters(start_date, end_date)

        request_query = db.query(RequestLog).filter(RequestLog.user_id == user_id)
        if platform_only:
            request_query = request_query.filter(RequestLog.agent_id.is_(None))
        if start_dt:
            request_query = request_query.filter(RequestLog.created_at >= start_dt)
        if end_dt:
            request_query = request_query.filter(RequestLog.created_at < end_dt)

        stats = request_query.with_entities(
            func.count(RequestLog.id).label("request_count"),
            func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(RequestLog.upstream_cache_read_input_tokens), 0).label("cache_read_input_tokens"),
            func.coalesce(func.sum(RequestLog.upstream_cache_creation_input_tokens), 0).label("cache_creation_input_tokens"),
            func.coalesce(func.sum(RequestLog.image_credits_charged), 0).label("image_credits"),
            func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_count"),
            func.sum(func.IF(not_(LogService._visible_success_condition()), 1, 0)).label("failed_count"),
            func.avg(RequestLog.response_time_ms).label("avg_response_time_ms"),
            func.max(RequestLog.created_at).label("last_request_at"),
        ).first()

        cost_query = db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0)).filter(
            ConsumptionRecord.user_id == user_id,
            ConsumptionRecord.total_cost > 0,
            ConsumptionRecord.model_name.isnot(None),
        )
        if platform_only:
            cost_query = cost_query.filter(ConsumptionRecord.agent_id.is_(None))
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
                "cache_read_input_tokens": int(stats.cache_read_input_tokens or 0),
                "cache_creation_input_tokens": int(stats.cache_creation_input_tokens or 0),
                "image_credits": float(stats.image_credits or 0),
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
    def get_agent_user_usage_summary(
        db: Session,
        user_id: int,
        agent_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if int(user.agent_id or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")

        summary = LogService.get_admin_user_usage_summary(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        summary_user = summary.get("user") or {}
        summary_user["agent_id"] = user.agent_id
        return summary

    @staticmethod
    def get_request_stats(
        db: Session,
        days: int = 7,
        agent_id: Optional[int] = None,
        range_key: Optional[str] = None,
    ) -> list[dict]:
        """
        Get aggregated request statistics for a given range.

        Returns:
            List of dicts with keys: ``date``, ``label``, ``total_requests``,
            ``success_requests``, ``failed_requests``, ``total_input_tokens``,
            ``total_output_tokens``, ``total_tokens``, ``total_cost``.
        """
        config = LogService._resolve_request_stats_config(days=days, range_key=range_key)
        since = config["since"]
        until = config["until"]
        bucket_mode = config["bucket_mode"]

        query = db.query(RequestLog).filter(
            RequestLog.created_at >= since,
            RequestLog.created_at <= until,
        )
        if agent_id is not None:
            query = query.filter(RequestLog.agent_id == agent_id)

        if bucket_mode == "two_hour":
            success_expr = LogService._visible_success_condition()
            bucket_expr = func.concat(
                func.date_format(RequestLog.created_at, "%Y-%m-%d "),
                func.lpad(func.floor(func.hour(RequestLog.created_at) / 2) * 2, 2, "0"),
                ":00",
            )
            rows = (
                query.with_entities(
                    bucket_expr.label("bucket_key"),
                    func.count(RequestLog.id).label("total_requests"),
                    func.sum(func.IF(success_expr, 1, 0)).label("success_requests"),
                    func.sum(func.IF(not_(success_expr), 1, 0)).label("failed_requests"),
                    func.coalesce(func.sum(RequestLog.input_tokens), 0).label("total_input_tokens"),
                    func.coalesce(func.sum(RequestLog.output_tokens), 0).label("total_output_tokens"),
                    func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                )
                .group_by(bucket_expr)
                .order_by(bucket_expr.asc())
                .all()
            )

            rows_by_bucket = {
                str(row.bucket_key): {
                    "bucket_key": str(row.bucket_key),
                    "date": str(row.bucket_key)[11:16],
                    "label": str(row.bucket_key)[11:16],
                    "total_requests": int(row.total_requests or 0),
                    "success_requests": int(row.success_requests or 0),
                    "failed_requests": int(row.failed_requests or 0),
                    "total_input_tokens": int(row.total_input_tokens or 0),
                    "total_output_tokens": int(row.total_output_tokens or 0),
                    "total_tokens": int(row.total_tokens or 0),
                }
                for row in rows
            }

            bucket_start = since.replace(minute=0, second=0, microsecond=0)
            return [
                rows_by_bucket.get(
                    (bucket_start + timedelta(hours=offset * 2)).strftime("%Y-%m-%d %H:00"),
                    {
                        "bucket_key": (bucket_start + timedelta(hours=offset * 2)).strftime("%Y-%m-%d %H:00"),
                        "date": (bucket_start + timedelta(hours=offset * 2)).strftime("%H:%M"),
                        "label": (bucket_start + timedelta(hours=offset * 2)).strftime("%H:%M"),
                        "total_requests": 0,
                        "success_requests": 0,
                        "failed_requests": 0,
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_tokens": 0,
                    },
                )
                for offset in range(12)
            ]

        rows = (
            query.with_entities(
                func.date(RequestLog.created_at).label("date"),
                func.count(RequestLog.id).label("total_requests"),
                func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_requests"),
                func.sum(func.IF(not_(LogService._visible_success_condition()), 1, 0)).label("failed_requests"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("total_input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("total_output_tokens"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            )
            .group_by(func.date(RequestLog.created_at))
            .order_by(func.date(RequestLog.created_at).asc())
            .all()
        )

        rows_by_date = {
            str(row.date): {
                "bucket_key": str(row.date),
                "date": str(row.date),
                "label": str(row.date),
                "total_requests": int(row.total_requests or 0),
                "success_requests": int(row.success_requests or 0),
                "failed_requests": int(row.failed_requests or 0),
                "total_input_tokens": int(row.total_input_tokens or 0),
                "total_output_tokens": int(row.total_output_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
            }
            for row in rows
        }

        start_date = since.date()
        total_days = max(int(config["days"] or 1), 1)
        return [
            rows_by_date.get(
                (start_date + timedelta(days=offset)).isoformat(),
                {
                    "bucket_key": (start_date + timedelta(days=offset)).isoformat(),
                    "date": (start_date + timedelta(days=offset)).isoformat(),
                    "label": (start_date + timedelta(days=offset)).isoformat(),
                    "total_requests": 0,
                    "success_requests": 0,
                    "failed_requests": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                },
            )
            for offset in range(total_days)
        ]

    @staticmethod
    def get_model_usage_ratio(
        db: Session,
        days: int = 7,
        agent_id: Optional[int] = None,
        range_key: Optional[str] = None,
        limit: int = 6,
    ) -> list[dict]:
        """Get model usage ratio aggregated by request count for a given range."""
        config = LogService._resolve_request_stats_config(days=days, range_key=range_key)
        since = config["since"]
        until = config["until"]
        model_name_expr = func.coalesce(RequestLog.requested_model, "unknown")

        query = db.query(RequestLog).filter(
            RequestLog.created_at >= since,
            RequestLog.created_at <= until,
        )
        if agent_id is not None:
            query = query.filter(RequestLog.agent_id == agent_id)

        rows = (
            query.with_entities(
                model_name_expr.label("model_name"),
                func.count(RequestLog.id).label("request_count"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
            )
            .group_by(model_name_expr)
            .order_by(func.count(RequestLog.id).desc(), model_name_expr.asc())
            .all()
        )
        return LogService._summarize_model_usage_rows(rows, limit=limit)

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
        agent_id: Optional[int] = None,
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
            agent_id=agent_id,
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
                func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_count"),
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
                func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_count"),
                func.sum(func.IF(not_(LogService._visible_success_condition()), 1, 0)).label("failed_count"),
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
    def get_token_ranking(db: Session, days: int = 1, limit: int = 10) -> list[dict]:
        """
        Get top users by USD consumption within the given time window.
        """
        try:
            resolved_limit = 10 if limit is None else int(limit)
        except (TypeError, ValueError):
            resolved_limit = 10
        resolved_limit = min(max(resolved_limit, 1), 50)
        since, now = LogService._get_timezone_day_window(days)
        rows = (
            db.query(
                SysUser.id.label("user_id"),
                SysUser.username,
                SysUser.role,
                SysUser.avatar,
                func.coalesce(func.sum(ConsumptionRecord.total_cost), 0).label("total_cost"),
                func.coalesce(func.sum(RequestLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.count(RequestLog.id).label("request_count"),
                func.max(RequestLog.created_at).label("last_used_at"),
            )
            .join(SysUser, SysUser.id == RequestLog.user_id)
            .outerjoin(ConsumptionRecord, ConsumptionRecord.request_id == RequestLog.request_id)
            .filter(
                RequestLog.user_id.isnot(None),
                RequestLog.created_at >= since,
                RequestLog.created_at <= now,
            )
            .group_by(SysUser.id, SysUser.username, SysUser.role, SysUser.avatar)
            .order_by(
                func.coalesce(func.sum(ConsumptionRecord.total_cost), 0).desc(),
                func.count(RequestLog.id).desc(),
                func.max(RequestLog.created_at).desc(),
                SysUser.id.asc(),
            )
            .limit(resolved_limit)
            .all()
        )

        return [
            {
                "rank": index + 1,
                "user_id": row.user_id,
                "username": row.username,
                "role": row.role,
                "avatar": row.avatar,
                "total_cost": float(row.total_cost or 0),
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
        db: Session, page: int = 1, page_size: int = 20, user_id: int = None, agent_id: int = None,
    ) -> tuple[list[dict], int]:
        query = db.query(ConsumptionRecord)
        if user_id is not None:
            query = query.filter(ConsumptionRecord.user_id == user_id)
        if agent_id is not None:
            query = query.filter(ConsumptionRecord.agent_id == agent_id)
        total = query.count()
        records = query.order_by(ConsumptionRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        result = [
            {
                "id": r.id, "user_id": r.user_id, "agent_id": r.agent_id, "request_id": r.request_id,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "billable_input_tokens": r.billable_input_tokens or r.input_tokens or 0,
                "raw_input_tokens": r.raw_input_tokens or 0,
                "raw_output_tokens": r.raw_output_tokens or 0,
                "raw_total_tokens": r.raw_total_tokens or 0,
                "logical_input_tokens": r.logical_input_tokens or 0,
                "upstream_input_tokens": r.upstream_input_tokens or 0,
                "upstream_cache_read_input_tokens": r.upstream_cache_read_input_tokens or 0,
                "billable_cache_read_input_tokens": r.billable_cache_read_input_tokens or r.upstream_cache_read_input_tokens or 0,
                "upstream_cache_creation_input_tokens": r.upstream_cache_creation_input_tokens or 0,
                "upstream_prompt_cache_status": r.upstream_prompt_cache_status or "BYPASS",
                "input_cost": float(r.input_cost), "output_cost": float(r.output_cost),
                "cache_read_cost": float(r.cache_read_cost or 0),
                "total_cost": float(r.total_cost),
                "input_price_per_million_snapshot": float(r.input_price_per_million_snapshot or 0),
                "output_price_per_million_snapshot": float(r.output_price_per_million_snapshot or 0),
                "price_multiplier_snapshot": float(r.price_multiplier_snapshot or 1),
                "fast_price_multiplier_snapshot": float(r.fast_price_multiplier_snapshot or 1),
                "service_tier": r.service_tier,
                "token_multiplier_snapshot": float(r.token_multiplier_snapshot or 1),
                "balance_before": float(r.balance_before), "balance_after": float(r.balance_after),
                "subscription_id": r.subscription_id,
                "subscription_cycle_id": r.subscription_cycle_id,
                "quota_metric": r.quota_metric,
                "quota_consumed_amount": float(r.quota_consumed_amount or 0),
                "quota_limit_snapshot": float(r.quota_limit_snapshot or 0),
                "quota_used_after": float(r.quota_used_after or 0),
                "quota_cycle_date": r.quota_cycle_date.isoformat() if r.quota_cycle_date else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
        return result, total

    @staticmethod
    def get_agent_token_ranking(
        db: Session,
        agent_id: int,
        days: int = 1,
        limit: int = 10,
    ) -> list[dict]:
        since, now = LogService._get_timezone_day_window(days)
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
                RequestLog.agent_id == agent_id,
                RequestLog.user_id.isnot(None),
                SysUser.role == "user",
                RequestLog.created_at >= since,
                RequestLog.created_at <= now,
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
            func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_count"),
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
                func.sum(func.IF(LogService._visible_success_condition(), 1, 0)).label("success_count"),
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
