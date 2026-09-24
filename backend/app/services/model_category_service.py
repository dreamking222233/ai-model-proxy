"""CRUD and validation for administrator-managed model categories."""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.core.model_series import MODEL_SERIES_LABELS, MODEL_SERIES_ORDER, MODEL_SERIES_VALUES
from app.models.model import ModelCategory, ModelPriceAdjustmentRule, UnifiedModel, UserPriceAdjustmentRule


class ModelCategoryService:
    CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

    @staticmethod
    def _normalize_code(value: object) -> str:
        code = str(value or "").strip().lower()
        if code == "all" or not ModelCategoryService.CODE_PATTERN.fullmatch(code):
            raise ServiceException(400, "类别编码只能使用小写字母、数字、下划线和短横线，且不能为 all", "INVALID_MODEL_CATEGORY")
        return code

    @staticmethod
    def _normalize_series(value: object) -> str:
        series = str(value or "").strip().lower()
        if series not in MODEL_SERIES_VALUES:
            raise ServiceException(400, f"模型系列只能是 {'、'.join(MODEL_SERIES_ORDER)}", "INVALID_MODEL_SERIES")
        return series

    @staticmethod
    def _to_dict(category: ModelCategory) -> dict:
        return {
            "id": int(category.id),
            "code": category.code,
            "name": category.name,
            "model_series": category.model_series,
            "model_series_label": MODEL_SERIES_LABELS.get(category.model_series, category.model_series),
            "sort_order": int(category.sort_order or 0),
            "enabled": int(category.enabled or 0),
            "description": category.description,
            "created_at": category.created_at.isoformat() if category.created_at else None,
            "updated_at": category.updated_at.isoformat() if category.updated_at else None,
        }

    @staticmethod
    def list_categories(db: Session, include_disabled: bool = True) -> list[dict]:
        query = db.query(ModelCategory)
        if not include_disabled:
            query = query.filter(ModelCategory.enabled == 1)
        rows = query.order_by(ModelCategory.sort_order.asc(), ModelCategory.id.asc()).all()
        return [ModelCategoryService._to_dict(row) for row in rows]

    @staticmethod
    def get_category(db: Session, category_id: int) -> ModelCategory:
        category = db.query(ModelCategory).filter(ModelCategory.id == int(category_id)).first()
        if not category:
            raise ServiceException(404, "模型类别不存在", "MODEL_CATEGORY_NOT_FOUND")
        return category

    @staticmethod
    def validate_for_model(db: Session, value: object, model_series: str, *, allow_empty: bool = True, existing_code: Optional[str] = None) -> Optional[str]:
        code = str(value or "").strip().lower()
        if not code:
            return None if allow_empty else model_series
        code = ModelCategoryService._normalize_code(code)
        category = db.query(ModelCategory).filter(ModelCategory.code == code).first()
        if not category:
            raise ServiceException(400, f"模型类别 '{code}' 不存在", "MODEL_CATEGORY_NOT_FOUND")
        if not int(category.enabled or 0) and code != existing_code:
            raise ServiceException(400, f"模型类别 '{code}' 已禁用", "MODEL_CATEGORY_DISABLED")
        if category.model_series != model_series:
            raise ServiceException(400, "模型类别所属系列与模型系列不一致", "MODEL_CATEGORY_SERIES_MISMATCH")
        return code

    @staticmethod
    def normalize_rule_category(db: Session, value: object, *, existing_code: Optional[str] = None) -> str:
        code = str(value or "all").strip().lower()
        if code == "all":
            return code
        normalized = ModelCategoryService._normalize_code(code)
        category = db.query(ModelCategory).filter(ModelCategory.code == normalized).first()
        if not category:
            raise ServiceException(400, f"模型类别 '{normalized}' 不存在", "MODEL_CATEGORY_NOT_FOUND")
        if not int(category.enabled or 0) and normalized != existing_code:
            raise ServiceException(400, f"模型类别 '{normalized}' 已禁用", "MODEL_CATEGORY_DISABLED")
        return normalized

    @staticmethod
    def create_category(db: Session, data) -> dict:
        payload = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        code = ModelCategoryService._normalize_code(payload.get("code"))
        if db.query(ModelCategory).filter(ModelCategory.code == code).first():
            raise ServiceException(400, f"模型类别编码 '{code}' 已存在", "DUPLICATE_MODEL_CATEGORY")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ServiceException(400, "模型类别名称不能为空", "INVALID_MODEL_CATEGORY_NAME")
        category = ModelCategory(
            code=code,
            name=name[:128],
            model_series=ModelCategoryService._normalize_series(payload.get("model_series", "other")),
            sort_order=int(payload.get("sort_order", 100) or 0),
            enabled=1 if bool(payload.get("enabled", 1)) else 0,
            description=str(payload.get("description") or "").strip() or None,
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        return ModelCategoryService._to_dict(category)

    @staticmethod
    def update_category(db: Session, category_id: int, data) -> dict:
        category = ModelCategoryService.get_category(db, category_id)
        payload = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        if "code" in payload:
            code = ModelCategoryService._normalize_code(payload.get("code"))
            duplicate = db.query(ModelCategory).filter(ModelCategory.code == code, ModelCategory.id != category.id).first()
            if duplicate:
                raise ServiceException(400, f"模型类别编码 '{code}' 已存在", "DUPLICATE_MODEL_CATEGORY")
            if code != category.code and ModelCategoryService._is_referenced(db, category.code):
                raise ServiceException(400, "已有模型或价格规则使用该类别，不能修改类别编码", "MODEL_CATEGORY_IN_USE")
            category.code = code
        if "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                raise ServiceException(400, "模型类别名称不能为空", "INVALID_MODEL_CATEGORY_NAME")
            category.name = name[:128]
        if "model_series" in payload:
            next_series = ModelCategoryService._normalize_series(payload.get("model_series"))
            if next_series != category.model_series and ModelCategoryService._is_referenced(db, category.code):
                raise ServiceException(400, "已有模型或价格规则使用该类别，不能修改所属系列", "MODEL_CATEGORY_IN_USE")
            category.model_series = next_series
        for field in ("sort_order", "enabled"):
            if field in payload and payload[field] is not None:
                setattr(category, field, int(payload[field]))
        if "description" in payload:
            category.description = str(payload.get("description") or "").strip() or None
        db.commit()
        db.refresh(category)
        return ModelCategoryService._to_dict(category)

    @staticmethod
    def delete_category(db: Session, category_id: int) -> None:
        category = ModelCategoryService.get_category(db, category_id)
        if ModelCategoryService._is_referenced(db, category.code):
            raise ServiceException(400, "已有模型或价格规则使用该类别，请先调整引用", "MODEL_CATEGORY_IN_USE")
        db.delete(category)
        db.commit()

    @staticmethod
    def _is_referenced(db: Session, code: str) -> bool:
        return bool(
            db.query(UnifiedModel).filter(UnifiedModel.model_category == code).first()
            or db.query(ModelPriceAdjustmentRule).filter(ModelPriceAdjustmentRule.model_category == code).first()
            or db.query(UserPriceAdjustmentRule).filter(UserPriceAdjustmentRule.model_category == code).first()
        )
