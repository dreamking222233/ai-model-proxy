"""Price adjustment rule service."""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.model import ModelPriceAdjustmentRule, UnifiedModel
from app.services.model_service import ModelService


class PriceAdjustmentService:
    """Resolve and manage model-series price multipliers."""

    BEIJING_TZ = ZoneInfo("Asia/Shanghai")
    MODEL_TYPE_VALUES = {"all", "chat", "completion", "embedding", "image", "video"}
    BILLING_TYPE_VALUES = {"all", "token", "request", "image_credit", "free"}
    SCHEDULE_TYPES = {"always", "daily_time"}

    @staticmethod
    def now_beijing() -> datetime:
        return datetime.now(PriceAdjustmentService.BEIJING_TZ)

    @staticmethod
    def _normalize_series(value: object, allow_all: bool = True) -> str:
        normalized = str(value or "all").strip().lower()
        if allow_all and normalized == "all":
            return normalized
        return ModelService.normalize_model_series(normalized)

    @staticmethod
    def _normalize_model_type(value: object, allow_all: bool = True) -> str:
        normalized = str(value or "all").strip().lower()
        if normalized not in PriceAdjustmentService.MODEL_TYPE_VALUES:
            raise ServiceException(400, "模型类型无效", "INVALID_MODEL_TYPE")
        if not allow_all and normalized == "all":
            raise ServiceException(400, "模型类型不能为 all", "INVALID_MODEL_TYPE")
        return normalized

    @staticmethod
    def _normalize_billing_type(value: object, allow_all: bool = True) -> str:
        normalized = str(value or "all").strip().lower()
        if normalized not in PriceAdjustmentService.BILLING_TYPE_VALUES:
            raise ServiceException(400, "计费类型无效", "INVALID_BILLING_TYPE")
        if not allow_all and normalized == "all":
            raise ServiceException(400, "计费类型不能为 all", "INVALID_BILLING_TYPE")
        return normalized

    @staticmethod
    def _normalize_multiplier(value: object) -> Decimal:
        try:
            multiplier = Decimal(str(value if value is not None and value != "" else 1)).quantize(Decimal("0.000001"))
        except (InvalidOperation, TypeError, ValueError):
            raise ServiceException(400, "倍率参数无效", "INVALID_PRICE_MULTIPLIER")
        if multiplier <= Decimal("0"):
            raise ServiceException(400, "倍率必须大于 0", "INVALID_PRICE_MULTIPLIER")
        if multiplier > Decimal("100"):
            raise ServiceException(400, "倍率不能超过 100", "INVALID_PRICE_MULTIPLIER")
        return multiplier

    @staticmethod
    def _normalize_time(value: object) -> Optional[time]:
        if value in (None, ""):
            return None
        if isinstance(value, time):
            return value.replace(microsecond=0)
        text = str(value).strip()
        try:
            parsed = datetime.strptime(text[:8] if len(text) >= 8 else text, "%H:%M:%S").time()
        except ValueError:
            try:
                parsed = datetime.strptime(text[:5], "%H:%M").time()
            except ValueError:
                raise ServiceException(400, "时间格式无效，请使用 HH:mm 或 HH:mm:ss", "INVALID_RULE_TIME")
        return parsed.replace(microsecond=0)

    @staticmethod
    def _normalize_payload(data, existing: Optional[ModelPriceAdjustmentRule] = None) -> dict:
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        payload = {}
        name = d.get("name", getattr(existing, "name", None))
        if name is not None:
            name = str(name or "").strip()
            if not name:
                raise ServiceException(400, "规则名称不能为空", "INVALID_RULE_NAME")
            payload["name"] = name[:128]

        if "model_series" in d or existing is None:
            payload["model_series"] = PriceAdjustmentService._normalize_series(
                d.get("model_series", getattr(existing, "model_series", "all") if existing else "all")
            )
        if "model_type" in d or existing is None:
            payload["model_type"] = PriceAdjustmentService._normalize_model_type(
                d.get("model_type", getattr(existing, "model_type", "all") if existing else "all")
            )
        if "billing_type" in d or existing is None:
            payload["billing_type"] = PriceAdjustmentService._normalize_billing_type(
                d.get("billing_type", getattr(existing, "billing_type", "all") if existing else "all")
            )
        if "multiplier" in d or existing is None:
            payload["multiplier"] = PriceAdjustmentService._normalize_multiplier(
                d.get("multiplier", getattr(existing, "multiplier", 1) if existing else 1)
            )

        schedule_type = d.get("schedule_type", getattr(existing, "schedule_type", "always") if existing else "always")
        if "schedule_type" in d or existing is None:
            schedule_type = str(schedule_type or "always").strip().lower()
            if schedule_type not in PriceAdjustmentService.SCHEDULE_TYPES:
                raise ServiceException(400, "生效方式无效", "INVALID_SCHEDULE_TYPE")
            payload["schedule_type"] = schedule_type

        effective_schedule_type = payload.get("schedule_type", getattr(existing, "schedule_type", "always") if existing else "always")
        start_value = d.get("start_time", getattr(existing, "start_time", None) if existing else None)
        end_value = d.get("end_time", getattr(existing, "end_time", None) if existing else None)
        if effective_schedule_type == "daily_time":
            start_time = PriceAdjustmentService._normalize_time(start_value)
            end_time = PriceAdjustmentService._normalize_time(end_value)
            if not start_time or not end_time:
                raise ServiceException(400, "每日时间段必须填写开始和结束时间", "INVALID_RULE_TIME")
            if start_time == end_time:
                raise ServiceException(400, "开始时间和结束时间不能相同", "INVALID_RULE_TIME")
            payload["start_time"] = start_time
            payload["end_time"] = end_time
        elif "schedule_type" in payload or "start_time" in d or "end_time" in d or existing is None:
            payload["start_time"] = None
            payload["end_time"] = None

        if "priority" in d or existing is None:
            try:
                priority = int(d.get("priority", getattr(existing, "priority", 100) if existing else 100))
            except (TypeError, ValueError):
                raise ServiceException(400, "优先级无效", "INVALID_PRIORITY")
            if priority < 0:
                raise ServiceException(400, "优先级不能小于 0", "INVALID_PRIORITY")
            payload["priority"] = priority
        if "enabled" in d or existing is None:
            payload["enabled"] = 1 if bool(d.get("enabled", getattr(existing, "enabled", 1) if existing else 1)) else 0
        if "description" in d:
            text = str(d.get("description") or "").strip()
            payload["description"] = text or None
        elif existing is None:
            payload["description"] = None
        return payload

    @staticmethod
    def _rule_to_dict(rule: ModelPriceAdjustmentRule, include_active: bool = False) -> dict:
        payload = {
            "id": rule.id,
            "name": rule.name,
            "model_series": rule.model_series,
            "model_type": rule.model_type,
            "billing_type": rule.billing_type,
            "multiplier": float(rule.multiplier or 1),
            "schedule_type": rule.schedule_type,
            "start_time": rule.start_time.strftime("%H:%M:%S") if rule.start_time else None,
            "end_time": rule.end_time.strftime("%H:%M:%S") if rule.end_time else None,
            "priority": int(rule.priority or 0),
            "enabled": int(rule.enabled or 0),
            "description": rule.description,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }
        if include_active:
            payload["is_active_now"] = PriceAdjustmentService.is_rule_active_now(rule)
        return payload

    @staticmethod
    def is_daily_time_active(start_time: time, end_time: time, now_time: time) -> bool:
        if start_time < end_time:
            return start_time <= now_time < end_time
        return now_time >= start_time or now_time < end_time

    @staticmethod
    def is_rule_active_now(rule: ModelPriceAdjustmentRule, now: Optional[datetime] = None) -> bool:
        if not int(rule.enabled or 0):
            return False
        schedule_type = str(rule.schedule_type or "always").lower()
        if schedule_type == "always":
            return True
        if schedule_type != "daily_time" or not rule.start_time or not rule.end_time:
            return False
        current = now or PriceAdjustmentService.now_beijing()
        return PriceAdjustmentService.is_daily_time_active(rule.start_time, rule.end_time, current.time())

    @staticmethod
    def list_rules(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        model_series: Optional[str] = None,
        model_type: Optional[str] = None,
        enabled: Optional[int] = None,
    ) -> tuple[list[dict], int]:
        query = db.query(ModelPriceAdjustmentRule)
        if model_series:
            query = query.filter(ModelPriceAdjustmentRule.model_series == PriceAdjustmentService._normalize_series(model_series))
        if model_type:
            query = query.filter(ModelPriceAdjustmentRule.model_type == PriceAdjustmentService._normalize_model_type(model_type))
        if enabled is not None:
            query = query.filter(ModelPriceAdjustmentRule.enabled == (1 if int(enabled) else 0))
        total = query.count()
        rows = (
            query.order_by(ModelPriceAdjustmentRule.priority.asc(), ModelPriceAdjustmentRule.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [PriceAdjustmentService._rule_to_dict(row, include_active=True) for row in rows], total

    @staticmethod
    def create_rule(db: Session, data) -> dict:
        payload = PriceAdjustmentService._normalize_payload(data)
        rule = ModelPriceAdjustmentRule(**payload)
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return PriceAdjustmentService._rule_to_dict(rule, include_active=True)

    @staticmethod
    def update_rule(db: Session, rule_id: int, data) -> dict:
        rule = db.query(ModelPriceAdjustmentRule).filter(ModelPriceAdjustmentRule.id == rule_id).first()
        if not rule:
            raise ServiceException(404, "价格调控规则不存在", "PRICE_ADJUSTMENT_RULE_NOT_FOUND")
        payload = PriceAdjustmentService._normalize_payload(data, existing=rule)
        for key, value in payload.items():
            setattr(rule, key, value)
        db.commit()
        db.refresh(rule)
        return PriceAdjustmentService._rule_to_dict(rule, include_active=True)

    @staticmethod
    def delete_rule(db: Session, rule_id: int) -> None:
        rule = db.query(ModelPriceAdjustmentRule).filter(ModelPriceAdjustmentRule.id == rule_id).first()
        if not rule:
            raise ServiceException(404, "价格调控规则不存在", "PRICE_ADJUSTMENT_RULE_NOT_FOUND")
        db.delete(rule)
        db.commit()

    @staticmethod
    def resolve_rule(
        db: Session,
        unified_model: Optional[UnifiedModel],
        now: Optional[datetime] = None,
    ) -> Optional[ModelPriceAdjustmentRule]:
        if unified_model is None:
            return None
        series = getattr(unified_model, "model_series", None) or ModelService.infer_model_series(unified_model.model_name)
        model_type = str(getattr(unified_model, "model_type", None) or "chat").strip().lower()
        billing_type = str(getattr(unified_model, "billing_type", None) or "token").strip().lower()
        rows = (
            db.query(ModelPriceAdjustmentRule)
            .filter(
                ModelPriceAdjustmentRule.enabled == 1,
                or_(ModelPriceAdjustmentRule.model_series == series, ModelPriceAdjustmentRule.model_series == "all"),
                or_(ModelPriceAdjustmentRule.model_type == model_type, ModelPriceAdjustmentRule.model_type == "all"),
                or_(ModelPriceAdjustmentRule.billing_type == billing_type, ModelPriceAdjustmentRule.billing_type == "all"),
            )
            .order_by(ModelPriceAdjustmentRule.priority.asc(), ModelPriceAdjustmentRule.id.desc())
            .all()
        )
        current = now or PriceAdjustmentService.now_beijing()
        for rule in rows:
            if PriceAdjustmentService.is_rule_active_now(rule, current):
                return rule
        return None

    @staticmethod
    def resolve_multiplier(
        db: Session,
        unified_model: Optional[UnifiedModel],
        now: Optional[datetime] = None,
    ) -> Decimal:
        rule = PriceAdjustmentService.resolve_rule(db, unified_model, now)
        if not rule:
            return Decimal("1")
        return Decimal(str(rule.multiplier or 1)).quantize(Decimal("0.000001"))

    @staticmethod
    def get_options() -> dict:
        return {
            "model_series": [
                {"value": "all", "label": "全部系列"},
                {"value": "gpt", "label": "GPT"},
                {"value": "claude", "label": "Claude"},
                {"value": "grok", "label": "Grok"},
                {"value": "gemini", "label": "Gemini"},
                {"value": "other", "label": "其他"},
            ],
            "model_types": [
                {"value": "all", "label": "全部类型"},
                {"value": "chat", "label": "文本对话"},
                {"value": "image", "label": "图片生成"},
                {"value": "video", "label": "视频生成"},
                {"value": "embedding", "label": "向量"},
                {"value": "completion", "label": "补全"},
            ],
            "billing_types": [
                {"value": "all", "label": "全部计费"},
                {"value": "token", "label": "按 Token"},
                {"value": "request", "label": "按请求"},
                {"value": "image_credit", "label": "按媒体积分"},
                {"value": "free", "label": "免费"},
            ],
            "schedule_types": [
                {"value": "always", "label": "长期生效"},
                {"value": "daily_time", "label": "每日时间段"},
            ],
        }

    @staticmethod
    def list_effective_matrix(db: Session) -> list[dict]:
        now = PriceAdjustmentService.now_beijing()
        rows = []
        for series in ("gpt", "claude", "grok", "gemini", "other"):
            for model_type in ("chat", "image", "video"):
                fake_model = UnifiedModel(
                    model_name=f"{series}-{model_type}",
                    model_series=series,
                    model_type=model_type,
                    billing_type="image_credit" if model_type in {"image", "video"} else "token",
                )
                rule = PriceAdjustmentService.resolve_rule(db, fake_model, now)
                rows.append({
                    "model_series": series,
                    "model_type": model_type,
                    "billing_type": fake_model.billing_type,
                    "multiplier": float(rule.multiplier) if rule else 1.0,
                    "rule_id": rule.id if rule else None,
                    "rule_name": rule.name if rule else "默认 1x",
                    "beijing_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                })
        return rows
