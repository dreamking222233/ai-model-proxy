"""Application configuration using pydantic-settings."""
from __future__ import annotations

import secrets
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:s1771746291@localhost:3306/modelinvoke"

    # JWT
    JWT_SECRET_KEY: str = "model-invoke-system-jwt-secret-key-2026-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Server
    SERVER_PORT: int = 8085

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8080", "http://localhost:8081"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
