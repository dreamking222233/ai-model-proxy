"""FastAPI dependencies for authentication and authorization."""
from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import Depends, Header, Request
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser, UserApiKey
from app.core.security import verify_token
from app.core.exceptions import ServiceException


def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> SysUser:
    """
    Extract and validate JWT token from the Authorization header.
    Expected format: "Bearer <token>"
    Returns the authenticated SysUser.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise ServiceException(status_code=401, detail="Missing or invalid authorization header", error_code="UNAUTHORIZED")

    token = authorization[7:]

    # If it looks like an API key, reject it here - use verify_api_key instead
    if token.startswith("sk-"):
        raise ServiceException(status_code=401, detail="API keys are not accepted for this endpoint. Use JWT token.", error_code="UNAUTHORIZED")

    try:
        payload = verify_token(token)
    except JWTError:
        raise ServiceException(status_code=401, detail="Invalid or expired token", error_code="UNAUTHORIZED")

    user_id = payload.get("sub")
    if user_id is None:
        raise ServiceException(status_code=401, detail="Invalid token payload", error_code="UNAUTHORIZED")

    user = db.query(SysUser).filter(SysUser.id == int(user_id)).first()
    if user is None:
        raise ServiceException(status_code=401, detail="User not found", error_code="UNAUTHORIZED")

    if user.status != 1:
        raise ServiceException(status_code=403, detail="User account is disabled", error_code="FORBIDDEN")

    return user


def require_admin(
    current_user: SysUser = Depends(get_current_user),
) -> SysUser:
    """Ensure the current user has admin role."""
    if current_user.role != "admin":
        raise ServiceException(status_code=403, detail="Admin privileges required", error_code="FORBIDDEN")
    return current_user


async def verify_api_key(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[SysUser, UserApiKey]:
    """
    Verify an API key from request headers.
    Checks both "Authorization: Bearer sk-xxx" and "X-API-Key: sk-xxx" headers.
    Returns the owning SysUser and the UserApiKey record.
    """
    api_key_value: str | None = None

    # Check X-API-Key header first
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key and x_api_key.startswith("sk-"):
        api_key_value = x_api_key

    # Fallback to Authorization: Bearer sk-xxx
    if not api_key_value:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer sk-"):
            api_key_value = auth_header[7:]

    if not api_key_value:
        raise ServiceException(status_code=401, detail="Missing API key", error_code="UNAUTHORIZED")

    # Look up by SHA256 hash
    key_hash = hashlib.sha256(api_key_value.encode("utf-8")).hexdigest()
    api_key_record = db.query(UserApiKey).filter(UserApiKey.key_hash == key_hash).first()

    if api_key_record is None:
        raise ServiceException(status_code=401, detail="Invalid API key", error_code="UNAUTHORIZED")

    if api_key_record.status != "active":
        raise ServiceException(status_code=401, detail="API key is not active", error_code="UNAUTHORIZED")

    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        raise ServiceException(status_code=401, detail="API key has expired", error_code="UNAUTHORIZED")

    # Look up the owning user
    user = db.query(SysUser).filter(SysUser.id == api_key_record.user_id).first()
    if user is None:
        raise ServiceException(status_code=401, detail="API key owner not found", error_code="UNAUTHORIZED")

    if user.status != 1:
        raise ServiceException(status_code=403, detail="User account is disabled", error_code="FORBIDDEN")

    return user, api_key_record
