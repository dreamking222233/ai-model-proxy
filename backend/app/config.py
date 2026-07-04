"""Application configuration using pydantic-settings."""
from __future__ import annotations

import secrets
from decimal import Decimal
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables or defaults."""

    # Database
    DATABASE_URL: str = "mysql+pymysql://root:s1771746291@localhost:3306/modelinvoke"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    CACHE_ENABLED: bool = True

    # JWT
    JWT_SECRET_KEY: str = "model-invoke-system-jwt-secret-key-2026-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Auth hardening
    AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    AUTH_REGISTER_RATE_LIMIT_PER_HOUR: int = 5
    AUTH_PASSWORD_RESET_RATE_LIMIT_PER_HOUR: int = 5
    AUTH_EMAIL_CODE_RATE_LIMIT_PER_HOUR: int = 5
    EMAIL_VERIFICATION_REQUIRED: bool = False
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 10
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True

    # Server
    SERVER_PORT: int = 8085
    STREAM_HEARTBEAT_INTERVAL_SECONDS: int = 20

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
    DYNAMIC_CORS_CACHE_TTL_SECONDS: int = 300

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

    # Alipay payment
    ALIPAY_ENABLED: bool = False
    ALIPAY_SERVER_URL: str = "https://openapi.alipay.com/gateway.do"
    ALIPAY_APP_ID: str = ""
    ALIPAY_APP_PRIVATE_KEY: str = ""
    ALIPAY_PUBLIC_KEY: str = ""
    ALIPAY_SIGN_TYPE: str = "RSA2"
    ALIPAY_NOTIFY_URL: str = ""
    ALIPAY_RETURN_PATH: str = "/user/recharge"
    PAYMENT_PUBLIC_BASE_URL: str = "https://api.xiaoleai.team"
    WECHAT_PAY_ENABLED: bool = False
    WECHAT_PAY_SERVER_URL: str = "https://api.mch.weixin.qq.com"
    WECHAT_PAY_APP_ID: str = ""
    WECHAT_PAY_MCH_ID: str = ""
    WECHAT_PAY_SERIAL_NO: str = ""
    WECHAT_PAY_PRIVATE_KEY: str = ""
    WECHAT_PAY_API_V3_KEY: str = ""
    WECHAT_PAY_PLATFORM_CERT: str = ""
    WECHAT_PAY_PLATFORM_PUBLIC_KEY: str = ""
    WECHAT_PAY_PLATFORM_SERIAL: str = ""
    WECHAT_PAY_PUBLIC_KEY_ID: str = ""
    WECHAT_PAY_NOTIFY_URL: str = ""
    RECHARGE_USER_CNY_TO_USD_RATE: Decimal = Decimal("5")
    RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE: Decimal = Decimal("10")
    RECHARGE_IMAGE_CREDIT_USER_CNY_RATE: Decimal = Decimal("5")
    RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE: Decimal = Decimal("10")

    class Config:
        env_file = str(BACKEND_ROOT / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
