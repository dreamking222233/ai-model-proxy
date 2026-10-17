"""Email verification code generation, delivery, and validation."""
from __future__ import annotations

import json
import random
import smtplib
import threading
import time
from email.message import EmailMessage

from app.config import settings
from app.core.exceptions import ServiceException
from app.core.redis_client import redis_client
from app.core.security import hash_secret


class EmailVerificationService:
    """Manage short-lived email verification codes."""

    _memory_codes: dict[str, tuple[str, float]] = {}
    _memory_lock = threading.Lock()

    @staticmethod
    def _normalize_email(email: str) -> str:
        return str(email or "").strip().lower()

    @classmethod
    def _cache_key(cls, email: str, purpose: str, agent_id: int | None = None) -> str:
        tenant = f"agent:{int(agent_id)}:" if agent_id is not None else ""
        return f"email_code:{tenant}{purpose}:{cls._normalize_email(email)}"

    @staticmethod
    def _smtp_ready() -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_FROM)

    @classmethod
    def send_code(cls, email: str, *, purpose: str = "register", agent_id: int | None = None) -> None:
        normalized_email = cls._normalize_email(email)
        if not normalized_email:
            raise ServiceException(400, "邮箱不能为空", "INVALID_EMAIL")
        if not cls._smtp_ready():
            raise ServiceException(503, "邮箱验证码服务未配置，请联系管理员", "EMAIL_SERVICE_NOT_CONFIGURED")

        code = f"{random.SystemRandom().randint(0, 999999):06d}"
        expire_seconds = max(int(settings.EMAIL_VERIFICATION_EXPIRE_MINUTES or 10), 1) * 60
        payload = json.dumps({
            "hash": hash_secret(code, salt=normalized_email),
            "expires_at": int(time.time()) + expire_seconds,
        })
        cache_key = cls._cache_key(normalized_email, purpose, agent_id)
        if not redis_client.set(cache_key, payload, ex=expire_seconds):
            with cls._memory_lock:
                cls._memory_codes[cache_key] = (payload, time.time() + expire_seconds)

        msg = EmailMessage()
        msg["Subject"] = "邮箱验证码"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = normalized_email
        msg.set_content(f"您的验证码是：{code}\n\n验证码 {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES} 分钟内有效。")

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
        except Exception:
            redis_client.delete(cache_key)
            cls._memory_codes.pop(cache_key, None)
            raise ServiceException(503, "验证码邮件发送失败，请稍后再试", "EMAIL_SEND_FAILED")

    @classmethod
    def verify_code(
        cls,
        email: str,
        code: str,
        *,
        purpose: str = "register",
        agent_id: int | None = None,
    ) -> None:
        if not settings.EMAIL_VERIFICATION_REQUIRED:
            return
        normalized_email = cls._normalize_email(email)
        normalized_code = str(code or "").strip()
        if not normalized_code:
            raise ServiceException(400, "请输入邮箱验证码", "EMAIL_CODE_REQUIRED")

        cache_key = cls._cache_key(normalized_email, purpose, agent_id)
        raw = redis_client.get(cache_key)
        memory_fallback = False
        if not raw:
            with cls._memory_lock:
                item = cls._memory_codes.get(cache_key)
                if item and item[1] > time.time():
                    raw = item[0]
                    memory_fallback = True
                elif item:
                    cls._memory_codes.pop(cache_key, None)
        if not raw:
            raise ServiceException(400, "邮箱验证码无效或已过期", "EMAIL_CODE_INVALID")

        try:
            payload = json.loads(raw)
        except Exception:
            raise ServiceException(400, "邮箱验证码无效或已过期", "EMAIL_CODE_INVALID")

        if int(payload.get("expires_at") or 0) < int(time.time()):
            cls._memory_codes.pop(cache_key, None)
            redis_client.delete(cache_key)
            raise ServiceException(400, "邮箱验证码无效或已过期", "EMAIL_CODE_INVALID")
        if payload.get("hash") != hash_secret(normalized_code, salt=normalized_email):
            raise ServiceException(400, "邮箱验证码错误", "EMAIL_CODE_INVALID")
        if memory_fallback:
            with cls._memory_lock:
                current = cls._memory_codes.get(cache_key)
                if not current or current[0] != raw or current[1] <= time.time():
                    raise ServiceException(400, "邮箱验证码无效或已过期", "EMAIL_CODE_INVALID")
                cls._memory_codes.pop(cache_key, None)
        else:
            client = getattr(redis_client, "client", None)
            consumed = False
            if client:
                try:
                    consumed = bool(client.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                        1,
                        cache_key,
                        raw,
                    ))
                except Exception:
                    current = redis_client.get(cache_key)
                    if current == raw:
                        consumed = redis_client.delete(cache_key)
            else:
                current = redis_client.get(cache_key)
                consumed = current == raw and redis_client.delete(cache_key)
            if not consumed:
                raise ServiceException(400, "邮箱验证码无效或已过期", "EMAIL_CODE_INVALID")
