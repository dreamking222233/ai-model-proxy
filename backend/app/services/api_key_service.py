"""API key management service."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import SysUser, UserApiKey
from app.models.model import ModelGroup
from app.core.model_series import MODEL_SERIES_LABELS
from app.core.security import generate_api_key
from app.core.exceptions import ServiceException
from app.services.model_group_service import ModelGroupService


class ApiKeyService:
    """CRUD operations for user API keys."""

    @staticmethod
    def _normalize_binding(
        db: Session,
        group_mode: str = "unified",
        group_model_series: str | None = None,
        group_id: int | None = None,
    ) -> tuple[str, str | None, int | None, ModelGroup | None]:
        mode = str(group_mode or "unified").strip().lower()
        if mode not in {"unified", "special"}:
            raise ServiceException(400, "API Key 分组模式无效", "INVALID_API_KEY_GROUP_MODE")
        if mode == "unified":
            return "unified", None, None, None
        if not group_model_series or group_id is None:
            raise ServiceException(400, "专用 API Key 必须选择模型系列和分组", "API_KEY_GROUP_REQUIRED")
        series = ModelGroupService.normalize_series(group_model_series)
        group = db.query(ModelGroup).filter(ModelGroup.id == int(group_id)).first()
        if not group:
            raise ServiceException(404, "模型分组不存在", "MODEL_GROUP_NOT_FOUND")
        if group.model_series != series:
            raise ServiceException(400, "分组所属系列与 API Key 选择不一致", "MODEL_GROUP_SERIES_MISMATCH")
        if not int(group.enabled or 0):
            raise ServiceException(400, "模型分组已停用", "MODEL_GROUP_DISABLED")
        return mode, series, int(group.id), group

    @staticmethod
    def _group_payload(db: Session, api_key: UserApiKey) -> dict:
        mode = str(getattr(api_key, "group_mode", None) or "unified").strip().lower()
        if mode != "special":
            return {
                "group_mode": "unified",
                "group_model_series": None,
                "group_series_label": None,
                "group_id": None,
                "group_name": None,
                "group_enabled": None,
                "group_status": "unified",
            }
        group = None
        if getattr(api_key, "group_id", None):
            group = db.query(ModelGroup).filter(ModelGroup.id == int(api_key.group_id)).first()
        enabled = bool(group and int(group.enabled or 0))
        return {
            "group_mode": "special",
            "group_model_series": getattr(api_key, "group_model_series", None),
            "group_series_label": MODEL_SERIES_LABELS.get(
                getattr(api_key, "group_model_series", None),
                getattr(api_key, "group_model_series", None),
            ),
            "group_id": int(api_key.group_id) if getattr(api_key, "group_id", None) else None,
            "group_name": group.name if group else None,
            "group_enabled": enabled,
            "group_status": "active" if enabled else "disabled",
        }

    @classmethod
    def create_api_key(
        cls,
        db: Session,
        user_id: int,
        name: str,
        group_mode: str = "unified",
        group_model_series: str | None = None,
        group_id: int | None = None,
    ) -> dict:
        """
        Generate and persist a new API key.

        Args:
            user_id: owning user id.
            name: human-readable key name.

        Returns:
            dict with ``id``, ``name``, ``key`` (full key, shown only once),
            ``key_prefix``, ``created_at``.
        """
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ServiceException(400, "API Key 名称不能为空", "INVALID_API_KEY_NAME")
        mode, series, normalized_group_id, _ = cls._normalize_binding(
            db, group_mode, group_model_series, group_id,
        )
        full_key, key_prefix, key_hash = generate_api_key()

        api_key = UserApiKey(
            user_id=user_id,
            name=normalized_name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            key_full=full_key,
            status="active",
            group_mode=mode,
            group_model_series=series,
            group_id=normalized_group_id,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        return {
            "id": api_key.id,
            "name": api_key.name,
            "key": full_key,  # shown only once
            "key_prefix": api_key.key_prefix,
            "created_at": api_key.created_at,
            **cls._group_payload(db, api_key),
        }

    @classmethod
    def _serialize_api_key(cls, db: Session, api_key: UserApiKey) -> dict:
        """Serialize the public API key metadata and current usage snapshot."""
        return {
            "id": api_key.id,
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "status": api_key.status,
            "total_requests": int(api_key.total_requests or 0),
            "total_tokens": int(api_key.total_tokens or 0),
            "total_cost": float(api_key.total_cost or 0),
            "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
            **cls._group_payload(db, api_key),
        }

    @classmethod
    def list_api_keys(cls, db: Session, user_id: int) -> list[dict]:
        """
        List all API keys for a user.

        The full key is never returned -- only the prefix is shown.
        """
        keys = (
            db.query(UserApiKey)
            .filter(UserApiKey.user_id == user_id)
            .order_by(UserApiKey.created_at.desc())
            .all()
        )

        return [cls._serialize_api_key(db, key) for key in keys]

    @classmethod
    def list_api_keys_for_admin(cls, db: Session, user_id: int) -> list[dict]:
        """List a user's API keys for an administrator, without revealing secrets."""
        if not db.query(SysUser.id).filter(SysUser.id == user_id).first():
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        keys = (
            db.query(UserApiKey)
            .filter(UserApiKey.user_id == user_id)
            .order_by(UserApiKey.created_at.desc(), UserApiKey.id.desc())
            .all()
        )
        return [cls._serialize_api_key(db, key) for key in keys]

    @classmethod
    def reset_usage(cls, db: Session, user_id: int, key_id: int) -> dict:
        """Reset one of the current user's usage counters."""
        api_key = (
            db.query(UserApiKey)
            .filter(UserApiKey.id == key_id, UserApiKey.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")

        api_key.total_requests = 0
        api_key.total_tokens = 0
        api_key.total_cost = Decimal("0")
        db.commit()
        db.refresh(api_key)
        return cls._serialize_api_key(db, api_key)

    @classmethod
    def update_group_binding(
        cls,
        db: Session,
        user_id: int,
        key_id: int,
        group_mode: str = "unified",
        group_model_series: str | None = None,
        group_id: int | None = None,
    ) -> dict:
        api_key = db.query(UserApiKey).filter(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user_id,
        ).first()
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")
        mode, series, normalized_group_id, _ = cls._normalize_binding(
            db, group_mode, group_model_series, group_id,
        )
        api_key.group_mode = mode
        api_key.group_model_series = series
        api_key.group_id = normalized_group_id
        db.commit()
        db.refresh(api_key)
        return {
            "id": api_key.id,
            "name": api_key.name,
            **cls._group_payload(db, api_key),
        }

    @staticmethod
    def get_group_options(db: Session) -> dict:
        return ModelGroupService.list_options(db, include_disabled=False)

    @staticmethod
    def reveal_api_key(db: Session, user_id: int, key_id: int) -> dict:
        """
        Reveal the full API key.

        Raises:
            ServiceException: if key not found or not owned by user.
        """
        api_key = db.query(UserApiKey).filter(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user_id,
        ).first()
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")
        if not api_key.key_full:
            raise ServiceException(400, "Full key not available for this key", "KEY_NOT_AVAILABLE")

        return {
            "id": api_key.id,
            "name": api_key.name,
            "key": api_key.key_full,
        }

    @staticmethod
    def delete_api_key(db: Session, user_id: int, key_id: int) -> None:
        """
        Permanently delete an API key.

        Raises:
            ServiceException: if key not found or not owned by user.
        """
        api_key = db.query(UserApiKey).filter(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user_id,
        ).first()
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")

        db.delete(api_key)
        db.commit()

    @staticmethod
    def disable_api_key(db: Session, user_id: int, key_id: int) -> dict:
        """
        Disable an API key (set status to 'disabled').

        Raises:
            ServiceException: if key not found or not owned by user.
        """
        api_key = db.query(UserApiKey).filter(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user_id,
        ).first()
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")

        api_key.status = "disabled"
        db.commit()
        db.refresh(api_key)

        return {
            "id": api_key.id,
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "status": api_key.status,
        }

    @staticmethod
    def enable_api_key(db: Session, user_id: int, key_id: int) -> dict:
        """
        Re-enable an API key (set status to 'active').

        Raises:
            ServiceException: if key not found or not owned by user.
        """
        api_key = db.query(UserApiKey).filter(
            UserApiKey.id == key_id,
            UserApiKey.user_id == user_id,
        ).first()
        if not api_key:
            raise ServiceException(404, "API key not found", "KEY_NOT_FOUND")

        api_key.status = "active"
        db.commit()
        db.refresh(api_key)

        return {
            "id": api_key.id,
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "status": api_key.status,
        }
