"""Application configuration using pydantic-settings."""
from __future__ import annotations

import secrets
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:s1771746291@localhost:3306/modelinvoke"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    # JWT
    JWT_SECRET_KEY: str = "model-invoke-system-jwt-secret-key-2026-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Server
    SERVER_PORT: int = 8085

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:8080",
        "http://localhost:8081",
        "https://www.xiaoleai.team",
        "https://api.xiaoleai.team"
    ]
    CORS_ORIGIN_REGEX: str = (
        r"^https?://([a-z0-9-]+\.)*xiaoleai\.team(:\d+)?$|"
        r"^https?://([a-z0-9-]+\.)*(localhost|127\.0\.0\.1|local)(:\d+)?$"
    )

    # Platform hosts
    PLATFORM_FRONTEND_HOSTS: List[str] = [
        "www.xiaoleai.team",
        "xiaoleai.team",
        "localhost",
        "127.0.0.1",
        "platform.localhost",
        "platform.local",
    ]
    PLATFORM_API_HOSTS: List[str] = [
        "api.xiaoleai.team",
        "localhost",
        "127.0.0.1",
        "api.localhost",
        "api.local",
        "platform-api.localhost",
        "platform-api.local",
    ]

    # Platform site defaults
    PLATFORM_SITE_NAME: str = "小乐AI"
    PLATFORM_SITE_SUBTITLE: str = "一站式 AI 模型调用服务，让智能触手可及"
    PLATFORM_ANNOUNCEMENT_TITLE: str = "平台公告"
    PLATFORM_ANNOUNCEMENT_CONTENT: str = (
        "尊敬的用户，欢迎使用 AI 模型中转平台！\n\n"
        "支持Claude和GPT及Gemini全系列模型!\n\n"
        "新用户注册，立即赠送 $5 体验额度"
    )
    PLATFORM_SUPPORT_WECHAT: str = "Q-Free-M"
    PLATFORM_SUPPORT_QQ: str = "2222006406"
    PLATFORM_ALLOW_REGISTER: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
