"""API key management service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import UserApiKey
from app.core.security import generate_api_key
from app.core.exceptions import ServiceException


class ApiKeyService:
    """CRUD operations for user API keys."""

    @staticmethod
    def create_api_key(db: Session, user_id: int, name: str) -> dict:
        """
        Generate and persist a new API key.

        Args:
            user_id: owning user id.
            name: human-readable key name.

        Returns:
            dict with ``id``, ``name``, ``key`` (full key, shown only once),
            ``key_prefix``, ``created_at``.
        """
        full_key, key_prefix, key_hash = generate_api_key()

        api_key = UserApiKey(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            key_full=full_key,
            status="active",
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
        }

    @staticmethod
    def list_api_keys(db: Session, user_id: int) -> list[dict]:
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

        return [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "status": k.status,
                "total_requests": k.total_requests,
                "total_tokens": k.total_tokens,
                "total_cost": float(k.total_cost) if k.total_cost else 0.0,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            }
            for k in keys
        ]

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
