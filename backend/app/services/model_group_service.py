"""CRUD and validation for model-series routing groups."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.core.model_series import MODEL_SERIES_LABELS, MODEL_SERIES_ORDER, MODEL_SERIES_VALUES
from app.models.model import ModelChannelMapping, ModelGroup, UnifiedModel
from app.models.user import UserApiKey


class ModelGroupService:
    """Manage enabled/default groups without coupling them to proxy routing."""

    CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

    @staticmethod
    def normalize_series(value: object) -> str:
        series = str(value or "").strip().lower()
        if series not in MODEL_SERIES_VALUES:
            raise ServiceException(
                400,
                f"模型系列只能是 {'、'.join(MODEL_SERIES_ORDER)}",
                "INVALID_MODEL_SERIES",
            )
        return series

    @classmethod
    def normalize_code(cls, value: object) -> str:
        code = str(value or "").strip().lower()
        if not cls.CODE_PATTERN.fullmatch(code):
            raise ServiceException(
                400,
                "分组编码只能使用小写字母、数字、下划线和短横线",
                "INVALID_MODEL_GROUP_CODE",
            )
        return code

    @staticmethod
    def _to_dict(db: Session, group: ModelGroup) -> dict:
        mapping_count = (
            db.query(func.count(ModelChannelMapping.id))
            .filter(ModelChannelMapping.group_id == group.id)
            .scalar()
            or 0
        )
        key_count = (
            db.query(func.count(UserApiKey.id))
            .filter(
                UserApiKey.group_mode == "special",
                UserApiKey.group_id == group.id,
            )
            .scalar()
            or 0
        )
        return {
            "id": int(group.id),
            "model_series": group.model_series,
            "model_series_label": MODEL_SERIES_LABELS.get(group.model_series, group.model_series),
            "code": group.code,
            "name": group.name,
            "multiplier": float(Decimal(str(group.multiplier or 1))),
            "enabled": int(group.enabled or 0),
            "is_default": int(group.is_default or 0),
            "sort_order": int(group.sort_order or 0),
            "description": group.description,
            "mapping_count": int(mapping_count),
            "key_count": int(key_count),
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        }

    @staticmethod
    def get_group(db: Session, group_id: int) -> ModelGroup:
        group = db.query(ModelGroup).filter(ModelGroup.id == int(group_id)).first()
        if not group:
            raise ServiceException(404, "模型分组不存在", "MODEL_GROUP_NOT_FOUND")
        return group

    @classmethod
    def list_groups(
        cls,
        db: Session,
        *,
        model_series: Optional[str] = None,
        include_disabled: bool = True,
    ) -> list[dict]:
        query = db.query(ModelGroup)
        if model_series:
            query = query.filter(ModelGroup.model_series == cls.normalize_series(model_series))
        if not include_disabled:
            query = query.filter(ModelGroup.enabled == 1)
        rows = query.order_by(
            ModelGroup.model_series.asc(),
            ModelGroup.sort_order.asc(),
            ModelGroup.id.asc(),
        ).all()
        return [cls._to_dict(db, row) for row in rows]

    @classmethod
    def _validate_name(cls, value: object) -> str:
        name = str(value or "").strip()
        if not name:
            raise ServiceException(400, "模型分组名称不能为空", "INVALID_MODEL_GROUP_NAME")
        return name[:128]

    @classmethod
    def _ensure_unique_code(
        cls,
        db: Session,
        model_series: str,
        code: str,
        exclude_id: Optional[int] = None,
    ) -> None:
        query = db.query(ModelGroup).filter(
            ModelGroup.model_series == model_series,
            ModelGroup.code == code,
        )
        if exclude_id is not None:
            query = query.filter(ModelGroup.id != int(exclude_id))
        if query.first():
            raise ServiceException(400, "该模型系列下的分组编码已存在", "DUPLICATE_MODEL_GROUP")

    @staticmethod
    def _unset_defaults(db: Session, model_series: str, except_id: Optional[int] = None) -> None:
        query = db.query(ModelGroup).filter(ModelGroup.model_series == model_series)
        if except_id is not None:
            query = query.filter(ModelGroup.id != int(except_id))
        query.update({ModelGroup.is_default: 0}, synchronize_session=False)

    @classmethod
    def create_group(cls, db: Session, data) -> dict:
        payload = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        series = cls.normalize_series(payload.get("model_series", "other"))
        code = cls.normalize_code(payload.get("code"))
        cls._ensure_unique_code(db, series, code)
        enabled = 1 if bool(payload.get("enabled", 1)) else 0
        is_default = 1 if bool(payload.get("is_default", 0)) else 0
        if enabled and not cls.resolve_default_group(db, series):
            is_default = 1
        if is_default and not enabled:
            raise ServiceException(400, "停用分组不能设为默认分组", "MODEL_GROUP_DEFAULT_DISABLED")

        group = ModelGroup(
            model_series=series,
            code=code,
            name=cls._validate_name(payload.get("name")),
            multiplier=Decimal(str(payload.get("multiplier", 1))),
            enabled=enabled,
            is_default=is_default,
            sort_order=int(payload.get("sort_order", 100) or 0),
            description=str(payload.get("description") or "").strip() or None,
        )
        if is_default:
            cls._unset_defaults(db, series)
        db.add(group)
        db.commit()
        db.refresh(group)
        return cls._to_dict(db, group)

    @classmethod
    def update_group(cls, db: Session, group_id: int, data) -> dict:
        group = cls.get_group(db, group_id)
        payload = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        current_series = group.model_series
        next_series = cls.normalize_series(payload.get("model_series", current_series))
        next_code = cls.normalize_code(payload.get("code", group.code))
        if next_series != current_series:
            if db.query(ModelChannelMapping).filter(ModelChannelMapping.group_id == group.id).first():
                raise ServiceException(400, "已有模型映射引用该分组，不能修改所属系列", "MODEL_GROUP_IN_USE")
            if db.query(UserApiKey).filter(UserApiKey.group_id == group.id).first():
                raise ServiceException(400, "已有 API Key 引用该分组，不能修改所属系列", "MODEL_GROUP_IN_USE")
        cls._ensure_unique_code(db, next_series, next_code, exclude_id=group.id)

        next_enabled = int(payload.get("enabled", group.enabled) if payload.get("enabled", group.enabled) is not None else group.enabled)
        next_default = int(payload.get("is_default", group.is_default) if payload.get("is_default", group.is_default) is not None else group.is_default)
        if int(group.is_default or 0) and (not next_default or next_series != current_series):
            raise ServiceException(
                400,
                "默认分组不能取消或修改所属系列，请先切换默认分组",
                "MODEL_GROUP_DEFAULT_REQUIRED",
            )
        if next_default and not next_enabled:
            raise ServiceException(400, "停用分组不能设为默认分组", "MODEL_GROUP_DEFAULT_DISABLED")
        if int(group.is_default or 0) and not next_enabled:
            raise ServiceException(400, "默认分组不能直接停用，请先切换默认分组", "MODEL_GROUP_DEFAULT_REQUIRED")

        group.model_series = next_series
        group.code = next_code
        if "name" in payload:
            group.name = cls._validate_name(payload.get("name"))
        if "multiplier" in payload and payload.get("multiplier") is not None:
            group.multiplier = Decimal(str(payload["multiplier"]))
        group.enabled = next_enabled
        group.is_default = next_default
        if "sort_order" in payload and payload.get("sort_order") is not None:
            group.sort_order = int(payload["sort_order"])
        if "description" in payload:
            group.description = str(payload.get("description") or "").strip() or None
        if next_default:
            cls._unset_defaults(db, next_series, except_id=group.id)
        db.commit()
        db.refresh(group)
        return cls._to_dict(db, group)

    @classmethod
    def set_default_group(cls, db: Session, group_id: int) -> dict:
        group = cls.get_group(db, group_id)
        if not int(group.enabled or 0):
            raise ServiceException(400, "停用分组不能设为默认分组", "MODEL_GROUP_DISABLED")
        cls._unset_defaults(db, group.model_series, except_id=group.id)
        group.is_default = 1
        db.commit()
        db.refresh(group)
        return cls._to_dict(db, group)

    @classmethod
    def disable_group(cls, db: Session, group_id: int) -> dict:
        group = cls.get_group(db, group_id)
        if int(group.is_default or 0):
            raise ServiceException(400, "默认分组不能直接停用，请先切换默认分组", "MODEL_GROUP_DEFAULT_REQUIRED")
        group.enabled = 0
        db.commit()
        db.refresh(group)
        return cls._to_dict(db, group)

    @classmethod
    def delete_group(cls, db: Session, group_id: int) -> None:
        group = cls.get_group(db, group_id)
        if int(group.is_default or 0):
            raise ServiceException(400, "默认分组不能删除，请先切换默认分组", "MODEL_GROUP_DEFAULT_REQUIRED")
        # Delete the group's mappings while retaining special API-Key references.
        # Those keys then resolve to MODEL_GROUP_UNAVAILABLE and can be switched
        # by the user, matching the disabled-group behavior.
        db.query(ModelChannelMapping).filter(ModelChannelMapping.group_id == group.id).delete(
            synchronize_session=False
        )
        db.delete(group)
        db.commit()

    @classmethod
    def resolve_default_group(cls, db: Session, model_series: str) -> Optional[ModelGroup]:
        series = cls.normalize_series(model_series)
        return (
            db.query(ModelGroup)
            .filter(
                ModelGroup.model_series == series,
                ModelGroup.enabled == 1,
                ModelGroup.is_default == 1,
            )
            .order_by(ModelGroup.sort_order.asc(), ModelGroup.id.asc())
            .first()
        )

    @classmethod
    def list_options(cls, db: Session, include_disabled: bool = False) -> dict:
        groups = cls.list_groups(db, include_disabled=include_disabled)
        series = []
        for value in MODEL_SERIES_ORDER:
            items = [item for item in groups if item["model_series"] == value]
            if items:
                series.append({
                    "value": value,
                    "label": MODEL_SERIES_LABELS.get(value, value),
                    "default_group_id": next(
                        (item["id"] for item in items if item["is_default"] and item["enabled"]),
                        None,
                    ),
                    "groups": items,
                })
        groups_by_series = {
            value: [item for item in groups if item["model_series"] == value]
            for value in MODEL_SERIES_ORDER
            if any(item["model_series"] == value for item in groups)
        }
        return {
            "series": series,
            "model_series": series,
            "groups": groups,
            "groups_by_series": groups_by_series,
        }
