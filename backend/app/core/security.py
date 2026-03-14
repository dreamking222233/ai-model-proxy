"""Security utilities: JWT tokens, password hashing, API key generation."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        tuple of (full_key, key_prefix, key_hash)
        - full_key: "sk-" + 48 random hex characters
        - key_prefix: first 7 characters of the full key (e.g. "sk-abcd")
        - key_hash: SHA256 hex digest of the full key
    """
    random_hex = secrets.token_hex(24)  # 24 bytes = 48 hex chars
    full_key = f"sk-{random_hex}"
    key_prefix = full_key[:7]
    key_hash = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    return full_key, key_prefix, key_hash
