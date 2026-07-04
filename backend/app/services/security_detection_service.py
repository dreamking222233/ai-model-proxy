"""Security detection, request snapshot, and risk-event service."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import session_scope
from app.models.log import (
    OperationLog,
    SecurityRequestSnapshot,
    SecurityRiskEvent,
)
from app.models.user import SysUser, UserApiKey
from app.services.health_service import get_system_config
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


@dataclass
class SecurityDetectionResult:
    """Normalized security scan result."""

    risk_level: str = "none"
    action: str = "allow"
    categories: list[str] | None = None
    matched_rules: list[dict[str, Any]] | None = None
    reason: str = ""

    @property
    def should_block(self) -> bool:
        return self.action == "block" or self.risk_level in {"high", "blocked"}


class SecurityDetectionService:
    """Local security rules, short-lived request snapshots, and risk reports."""

    DEFAULT_PUBLIC_REPORT_URL = "https://api.xiaoleai.team/api/public/security/risk-report"
    RISK_MARKER_PATTERN = re.compile(
        r"\[MIS_RISK_REPORT\s+category=(?P<category>[a-zA-Z0-9_\-]+)\s+severity=(?P<severity>[a-zA-Z0-9_\-]+)[^\]]*\]",
        re.IGNORECASE,
    )
    _PUBLIC_REPORT_IP_BUCKETS: dict[str, list[float]] = {}

    SENSITIVE_KEYWORDS = (
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "password",
        "passwd",
        "secret",
        "cookie",
        "set-cookie",
        "key_full",
    )
    BINARY_KEYS = {
        "image",
        "images",
        "input_image",
        "input_images",
        "file",
        "files",
        "audio",
        "video",
        "b64_json",
        "base64",
        "data",
    }

    STUDENT_PRETEXT_TERMS = [
        "我是学生",
        "我是小学生",
        "我是初中生",
        "我是高中生",
        "我是大学生",
        "学校作业",
        "课程作业",
        "实验作业",
        "老师要求",
        "老师布置",
        "仅供学习",
        "只是学习",
        "学习用途",
        "研究用途",
        "ctf",
        "靶场",
    ]
    CYBER_ABUSE_TERMS = [
        "注册机",
        "keygen",
        "破解版",
        "破解网站",
        "网站破解",
        "后台爆破",
        "密码爆破",
        "撞库",
        "盗号",
        "验证码绕过",
        "风控绕过",
        "滑块绕过",
        "webshell",
        "getshell",
        "sql注入",
        "sql 注入",
        "rce",
        "远程代码执行",
        "木马",
        "免杀",
    ]
    AMBIGUOUS_CYBER_TERMS = {
        "crack": re.compile(
            r"\bcrack(?:ed|ing|s)?\b.{0,24}\b("
            r"password|account|license|serial|key|software|app|program|game|"
            r"activation|activate|auth|login|website|site|system"
            r")\b|"
            r"\b("
            r"password|account|license|serial|key|software|app|program|game|"
            r"activation|activate|auth|login|website|site|system"
            r")\b.{0,24}\bcrack(?:ed|ing|s)?\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "后门": re.compile(
            r"(植入|安装|留下|写入|添加|上传|隐藏|检测|查杀|绕过|利用|权限|远控|持久化|"
            r"软件|程序|代码|系统|网站|服务器|数据库|账号|漏洞|木马|webshell|shell|payload)"
            r".{0,16}后门|后门.{0,16}"
            r"(程序|代码|权限|账号|漏洞|木马|webshell|shell|payload|远控|持久化|检测|查杀|利用|绕过)",
            re.IGNORECASE | re.DOTALL,
        ),
    }
    PROMPT_JAILBREAK_TERMS = [
        "破限",
        "越狱提示词",
        "破限提示词",
        "绕过审查",
        "通过审查",
        "忽略系统提示",
        "忽略开发者消息",
        "泄露系统提示",
        "获取系统提示词",
        "dan",
        "无限制模式",
    ]
    AMBIGUOUS_PROMPT_JAILBREAK_TERMS = {
        "prompt injection": re.compile(
            r"\bprompt\s+injection\b.{0,96}\b("
            r"bypass|jailbreak|ignore|leak|extract|steal|reveal|override|payload|attack|"
            r"system\s+prompt|developer\s+message"
            r")\b|"
            r"\b("
            r"bypass|jailbreak|ignore|leak|extract|steal|reveal|override|payload|attack|"
            r"system\s+prompt|developer\s+message"
            r")\b.{0,96}\bprompt\s+injection\b|"
            r"(prompt\s+injection).{0,96}(绕过|越狱|忽略|泄露|获取|提取|套取|系统提示|开发者消息|"
            r"攻击教程|攻击方法|攻击代码|攻击载荷|攻击脚本|利用方法|利用代码|构造payload)|"
            r"(绕过|越狱|忽略|泄露|获取|提取|套取|系统提示|开发者消息|"
            r"攻击教程|攻击方法|攻击代码|攻击载荷|攻击脚本|利用方法|利用代码|构造payload).{0,96}(prompt\s+injection)|"
            r"(帮我|请|生成|写|构造|制作|设计|提供|创建|实现|开发).{0,48}(prompt\s+injection).{0,48}攻击|"
            r"(帮我|请|生成|写|构造|制作|设计|提供|创建|实现|开发).{0,48}攻击.{0,48}(prompt\s+injection)",
            re.IGNORECASE | re.DOTALL,
        ),
    }
    SEXUAL_HIGH_RISK_TERMS = [
        "裸聊",
        "文爱",
        "睡奸",
        "未成年色情",
        "性奴",
        "做爱",
        "自慰",
        "射精",
        "阴道",
        "阴茎",
        "龟头",
        "睾丸",
        "鸡巴",
        "操逼",
    ]
    AMBIGUOUS_SEXUAL_TERMS = {
        "色情": re.compile(r"(色情).{0,12}(内容|小说|作品|描写|情节|图片|视频|服务)|"
                         r"(生成|写|创作|制作|提供|寻找|推荐).{0,16}(色情)", re.IGNORECASE | re.DOTALL),
        "黄文": re.compile(r"(黄文)|((生成|写|创作|制作).{0,16}黄色.{0,8}(小说|文章|内容))", re.IGNORECASE | re.DOTALL),
        "色情小说": re.compile(r"色情小说", re.IGNORECASE),
        "萝莉": re.compile(r"(萝莉).{0,12}(色情|裸|性|调教|做爱|性交|文爱)|"
                         r"(色情|裸|性|调教|做爱|性交|文爱).{0,12}(萝莉)", re.IGNORECASE | re.DOTALL),
        "幼女": re.compile(r"(幼女).{0,12}(色情|裸|性|调教|做爱|性交|文爱)|"
                         r"(色情|裸|性|调教|做爱|性交|文爱).{0,12}(幼女)", re.IGNORECASE | re.DOTALL),
        "乱伦": re.compile(r"(乱伦).{0,12}(色情|小说|黄文|做爱|性交|文爱|情节|描写)|"
                         r"(写|生成|创作|制作).{0,16}(乱伦)", re.IGNORECASE | re.DOTALL),
        "强奸": re.compile(r"强奸(?!案|案件|罪|犯罪|事件|指控|审判|抗议|报道|史实)|"
                         r"(写|生成|创作|制作).{0,16}强奸.{0,12}(情节|描写|小说|内容)", re.IGNORECASE | re.DOTALL),
        "轮奸": re.compile(r"轮奸(?!案|案件|罪|犯罪|事件|指控|审判|抗议|报道|史实)|"
                         r"(写|生成|创作|制作).{0,16}轮奸.{0,12}(情节|描写|小说|内容)", re.IGNORECASE | re.DOTALL),
        "性交": re.compile(r"(?<!线)性交(?!织|流|换|付(?!费))", re.IGNORECASE),
        "口交": re.compile(r"(?<!人)口交(?!融)", re.IGNORECASE),
        "肛交": re.compile(r"肛交", re.IGNORECASE),
    }
    NEGATED_SAFETY_CONTEXT_PATTERN = re.compile(
        r"(不能|不要|不得|禁止|避免|拒绝|切记不能|不允许).{0,16}$",
        re.IGNORECASE | re.DOTALL,
    )
    ILLEGAL_AUTOMATION_TERMS = [
        "批量注册",
        "自动注册",
        "注册脚本",
        "接码平台",
        "短信接码",
        "代理池",
        "ip池",
        "指纹浏览器",
        "浏览器指纹伪装",
        "自动刷量",
        "刷接口",
        "刷注册",
        "刷登录",
        "薅羊毛脚本",
        "秒杀脚本",
        "抢券脚本",
        "反爬绕过",
        "限流绕过",
        "rate limit bypass",
    ]

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _get_bool_config(db: Session, key: str, default: bool) -> bool:
        return SecurityDetectionService._coerce_bool(get_system_config(db, key, default))

    @staticmethod
    def _get_int_config(db: Session, key: str, default: int) -> int:
        try:
            return int(get_system_config(db, key, default) or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        lowered = str(key or "").lower()
        return any(term in lowered for term in SecurityDetectionService.SENSITIVE_KEYWORDS)

    @staticmethod
    def _looks_like_base64(value: str) -> bool:
        text = str(value or "")
        if len(text) < 512:
            return False
        if text.startswith("data:"):
            return True
        sample = text[:1024]
        return bool(re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", sample))

    @staticmethod
    def _sanitize_payload(value: Any, key: str = "") -> Any:
        if SecurityDetectionService._is_sensitive_key(key):
            return "***"
        if isinstance(value, dict):
            return {
                str(item_key): SecurityDetectionService._sanitize_payload(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            if str(key).lower() in SecurityDetectionService.BINARY_KEYS:
                return {
                    "__omitted__": "list_payload",
                    "count": len(value),
                }
            return [SecurityDetectionService._sanitize_payload(item, key) for item in value]
        if isinstance(value, str):
            if str(key).lower() in SecurityDetectionService.BINARY_KEYS or SecurityDetectionService._looks_like_base64(value):
                return {
                    "__omitted__": "large_or_binary_string",
                    "size_chars": len(value),
                    "sha256": SecurityDetectionService._hash_text(value),
                }
            return value
        return value

    @staticmethod
    def _truncate_json_payload(value: Any, max_bytes: int) -> tuple[str, bool, int]:
        payload = SecurityDetectionService._stable_json(value)
        encoded = payload.encode("utf-8")
        if len(encoded) <= max_bytes:
            return payload, False, len(encoded)
        truncated = encoded[:max(max_bytes, 0)].decode("utf-8", errors="ignore")
        return truncated, True, len(encoded)

    @staticmethod
    def _extract_text_from_content(content: Any) -> str:
        parts: list[str] = []
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    item_type = str(item.get("type") or "")
                    if item_type in {"text", "input_text"} and item.get("text") is not None:
                        parts.append(str(item.get("text")))
        elif isinstance(content, dict):
            for key in ("text", "input", "prompt", "content"):
                if content.get(key) is not None:
                    parts.append(SecurityDetectionService._extract_text_from_content(content.get(key)))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def extract_user_text(request_data: Any, protocol_type: str = "") -> str:
        parts: list[str] = []
        if not isinstance(request_data, dict):
            return str(request_data or "")

        prompt = request_data.get("prompt")
        if prompt is not None:
            parts.append(str(prompt))

        messages = request_data.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "").lower()
                if role in {"user", "human"}:
                    parts.append(SecurityDetectionService._extract_text_from_content(message.get("content")))

        responses_input = request_data.get("input")
        if responses_input is not None:
            if isinstance(responses_input, str):
                parts.append(responses_input)
            elif isinstance(responses_input, list):
                for item in responses_input:
                    if isinstance(item, dict):
                        role = str(item.get("role") or "").lower()
                        if role in {"user", ""}:
                            parts.append(SecurityDetectionService._extract_text_from_content(item.get("content") or item))
                    else:
                        parts.append(SecurityDetectionService._extract_text_from_content(item))
            else:
                parts.append(SecurityDetectionService._extract_text_from_content(responses_input))

        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _strip_client_context_wrappers(text: str) -> str:
        cleaned = str(text or "")
        cleaned = re.sub(
            r"\n?\[CONTEXT\s+COMPACTION[^\]]*\].*",
            "\n",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        block_tags = (
            "system-reminder",
            "local-command-caveat",
            "command-name",
            "command-message",
            "command-args",
            "local-command-stdout",
            "local-command-stderr",
        )
        for tag in block_tags:
            cleaned = re.sub(
                rf"<{tag}\b[^>]*>.*?</{tag}>",
                "\n",
                cleaned,
                flags=re.IGNORECASE | re.DOTALL,
            )
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def extract_latest_user_text(request_data: Any, protocol_type: str = "") -> str:
        if not isinstance(request_data, dict):
            return SecurityDetectionService._strip_client_context_wrappers(str(request_data or ""))

        prompt = request_data.get("prompt")
        if prompt is not None:
            return SecurityDetectionService._strip_client_context_wrappers(str(prompt))

        messages = request_data.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "").lower()
                if role in {"user", "human"}:
                    text = SecurityDetectionService._strip_client_context_wrappers(
                        SecurityDetectionService._extract_text_from_content(message.get("content"))
                    )
                    if text:
                        return text

        responses_input = request_data.get("input")
        if isinstance(responses_input, str):
            return SecurityDetectionService._strip_client_context_wrappers(responses_input)
        if isinstance(responses_input, list):
            for item in reversed(responses_input):
                if isinstance(item, dict):
                    role = str(item.get("role") or "").lower()
                    if role not in {"user", ""}:
                        continue
                    text = SecurityDetectionService._strip_client_context_wrappers(
                        SecurityDetectionService._extract_text_from_content(item.get("content") or item)
                    )
                    if text:
                        return text
                else:
                    text = SecurityDetectionService._strip_client_context_wrappers(
                        SecurityDetectionService._extract_text_from_content(item)
                    )
                    if text:
                        return text
        elif responses_input is not None:
            return SecurityDetectionService._strip_client_context_wrappers(
                SecurityDetectionService._extract_text_from_content(responses_input)
            )

        return SecurityDetectionService._strip_client_context_wrappers(
            SecurityDetectionService.extract_user_text(request_data, protocol_type)
        )

    @staticmethod
    def _match_terms(text: str, terms: list[str], category: str) -> list[dict[str, Any]]:
        normalized = str(text or "").lower()
        matched = []
        for term in terms:
            if (
                SecurityDetectionService._term_matches(normalized, str(term))
                and not SecurityDetectionService._is_negated_safety_context(normalized, str(term))
            ):
                matched.append({"category": category, "term": term})
        return matched

    @staticmethod
    def _is_negated_safety_context(text: str, term: str) -> bool:
        normalized = str(text or "")
        normalized_term = str(term or "").strip().lower()
        if not normalized_term:
            return False
        start = normalized.find(normalized_term)
        while start >= 0:
            prefix = normalized[max(0, start - 24):start]
            suffix = normalized[start + len(normalized_term):start + len(normalized_term) + 16]
            if (
                SecurityDetectionService.NEGATED_SAFETY_CONTEXT_PATTERN.search(prefix)
                and re.search(r"(内容|描写|情节|词汇|低俗|违法|违规|敏感|擦边)", suffix)
            ):
                return True
            start = normalized.find(normalized_term, start + len(normalized_term))
        return False

    @staticmethod
    def _match_ambiguous_sexual_terms(text: str) -> list[dict[str, Any]]:
        normalized = str(text or "").lower()
        matched = []
        for term, pattern in SecurityDetectionService.AMBIGUOUS_SEXUAL_TERMS.items():
            if pattern.search(normalized) and not SecurityDetectionService._is_negated_safety_context(normalized, term):
                matched.append({"category": "sexual_content", "term": term})
        return matched

    @staticmethod
    def _match_ambiguous_cyber_terms(text: str) -> list[dict[str, Any]]:
        matched = []
        for term, pattern in SecurityDetectionService.AMBIGUOUS_CYBER_TERMS.items():
            if pattern.search(str(text or "")):
                matched.append({"category": "cyber_abuse", "term": term})
        return matched

    @staticmethod
    def _match_ambiguous_prompt_jailbreak_terms(text: str) -> list[dict[str, Any]]:
        matched = []
        for term, pattern in SecurityDetectionService.AMBIGUOUS_PROMPT_JAILBREAK_TERMS.items():
            if pattern.search(str(text or "")):
                matched.append({"category": "prompt_jailbreak", "term": term})
        return matched

    @staticmethod
    def _term_matches(normalized_text: str, term: str) -> bool:
        normalized = str(normalized_text or "").lower()
        normalized_term = str(term or "").strip().lower()
        if not normalized_term:
            return False
        if re.fullmatch(r"[a-z0-9][a-z0-9_\-\s]*", normalized_term):
            escaped = re.escape(normalized_term)
            escaped = re.sub(r"\\\s+", r"\\s+", escaped)
            return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", normalized))
        return normalized_term in normalized

    @staticmethod
    def scan_text(text: str) -> SecurityDetectionResult:
        normalized = str(text or "").strip()
        if not normalized:
            return SecurityDetectionResult(categories=[], matched_rules=[])

        matched_rules: list[dict[str, Any]] = []
        matched_rules.extend(SecurityDetectionService._match_terms(normalized, SecurityDetectionService.SEXUAL_HIGH_RISK_TERMS, "sexual_content"))
        matched_rules.extend(SecurityDetectionService._match_ambiguous_sexual_terms(normalized))
        matched_rules.extend(SecurityDetectionService._match_terms(normalized, SecurityDetectionService.PROMPT_JAILBREAK_TERMS, "prompt_jailbreak"))
        matched_rules.extend(SecurityDetectionService._match_ambiguous_prompt_jailbreak_terms(normalized))
        matched_rules.extend(SecurityDetectionService._match_terms(normalized, SecurityDetectionService.CYBER_ABUSE_TERMS, "cyber_abuse"))
        matched_rules.extend(SecurityDetectionService._match_ambiguous_cyber_terms(normalized))
        matched_rules.extend(SecurityDetectionService._match_terms(normalized, SecurityDetectionService.ILLEGAL_AUTOMATION_TERMS, "illegal_automation"))

        lower_text = normalized.lower()
        has_student_pretext = any(
            SecurityDetectionService._term_matches(lower_text, term)
            for term in SecurityDetectionService.STUDENT_PRETEXT_TERMS
        )
        has_abuse = any(
            SecurityDetectionService._term_matches(lower_text, term)
            for term in (SecurityDetectionService.CYBER_ABUSE_TERMS + SecurityDetectionService.ILLEGAL_AUTOMATION_TERMS)
        )
        has_abuse = has_abuse or bool(SecurityDetectionService._match_ambiguous_cyber_terms(normalized))
        if has_student_pretext and has_abuse:
            matched_rules.append({
                "category": "student_pretext_abuse",
                "term": "student_pretext + cyber_or_automation",
            })

        categories = sorted({rule["category"] for rule in matched_rules})
        if not matched_rules:
            return SecurityDetectionResult(categories=[], matched_rules=[])

        high_categories = {"sexual_content", "prompt_jailbreak", "cyber_abuse", "student_pretext_abuse"}
        risk_level = "high" if any(category in high_categories for category in categories) else "medium"
        action = "block" if risk_level == "high" else "review"
        reason = "命中安全风控规则：" + "、".join(categories)
        return SecurityDetectionResult(
            risk_level=risk_level,
            action=action,
            categories=categories,
            matched_rules=matched_rules,
            reason=reason,
        )

    @staticmethod
    def scan_request(db: Session, snapshot: Optional[SecurityRequestSnapshot], request_data: dict) -> SecurityDetectionResult:
        if not SecurityDetectionService._get_bool_config(db, "security_detection_enabled", True):
            return SecurityDetectionResult(categories=[], matched_rules=[])
        max_chars = SecurityDetectionService._get_int_config(db, "security_scan_max_text_chars", 20000)
        text = SecurityDetectionService.extract_latest_user_text(request_data)
        return SecurityDetectionService.scan_text(str(text or "")[:max_chars])

    @staticmethod
    def create_snapshot(
        db: Session,
        user: SysUser,
        api_key_record: Optional[UserApiKey],
        request_id: str,
        request_data: dict,
        protocol_type: str,
        request_type: str,
        requested_model: str,
        client_ip: Optional[str],
    ) -> tuple[Optional[SecurityRequestSnapshot], Optional[str]]:
        if not SecurityDetectionService._get_bool_config(db, "security_snapshot_enabled", True):
            return None, None

        max_bytes = SecurityDetectionService._get_int_config(db, "security_snapshot_max_body_bytes", 262144)
        ttl_seconds = SecurityDetectionService._get_int_config(db, "security_snapshot_ttl_seconds", 1800)
        snapshot_id = str(uuid.uuid4())
        report_token = secrets.token_urlsafe(32)
        sanitized = SecurityDetectionService._sanitize_payload(request_data)
        body_json, is_truncated, body_size_bytes = SecurityDetectionService._truncate_json_payload(sanitized, max_bytes)
        extracted_text = SecurityDetectionService.extract_user_text(request_data, protocol_type)
        request_hash = SecurityDetectionService._hash_text(SecurityDetectionService._stable_json(sanitized))
        preview = extracted_text[:1000]

        with session_scope() as write_db:
            snapshot = SecurityRequestSnapshot(
                snapshot_id=snapshot_id,
                request_id=request_id,
                user_id=getattr(user, "id", None),
                agent_id=getattr(user, "agent_id", None),
                user_api_key_id=getattr(api_key_record, "id", None),
                requested_model=requested_model,
                protocol_type=protocol_type,
                request_type=request_type,
                client_ip=client_ip,
                request_hash=request_hash,
                report_token_hash=SecurityDetectionService._hash_text(report_token),
                request_preview=preview,
                request_body_json=body_json,
                extracted_text=extracted_text,
                is_truncated=1 if is_truncated else 0,
                body_size_bytes=body_size_bytes,
                retention_status="temporary",
                risk_level="none",
                risk_categories_json="[]",
                expires_at=datetime.utcnow() + timedelta(seconds=max(ttl_seconds, 60)),
            )
            write_db.add(snapshot)
            write_db.flush()
            write_db.refresh(snapshot)
            snapshot_id_value = snapshot.snapshot_id

        # The request-scoped DB session may already hold a MySQL repeatable-read
        # snapshot and fail to see the row committed by session_scope() above.
        # Return the data the scanner needs directly instead of re-querying.
        return SimpleNamespace(
            id=None,
            snapshot_id=snapshot_id_value,
            request_id=request_id,
            user_id=getattr(user, "id", None),
            agent_id=getattr(user, "agent_id", None),
            user_api_key_id=getattr(api_key_record, "id", None),
            requested_model=requested_model,
            protocol_type=protocol_type,
            request_type=request_type,
            client_ip=client_ip,
            request_hash=request_hash,
            report_token_hash=SecurityDetectionService._hash_text(report_token),
            request_preview=preview,
            request_body_json=body_json,
            extracted_text=extracted_text,
            is_truncated=1 if is_truncated else 0,
            body_size_bytes=body_size_bytes,
            retention_status="temporary",
            risk_level="none",
            risk_categories_json="[]",
            expires_at=datetime.utcnow() + timedelta(seconds=max(ttl_seconds, 60)),
        ), report_token

    @staticmethod
    def record_risk_event(
        db: Session,
        snapshot: Optional[SecurityRequestSnapshot],
        source: str,
        result: SecurityDetectionResult,
        response_excerpt: Optional[str] = None,
    ) -> Optional[SecurityRiskEvent]:
        categories = result.categories or ["unknown"]
        matched_rules = result.matched_rules or []
        with session_scope() as write_db:
            write_snapshot = None
            if snapshot is not None:
                write_snapshot = write_db.query(SecurityRequestSnapshot).filter(
                    SecurityRequestSnapshot.snapshot_id == snapshot.snapshot_id
                ).first()
                if write_snapshot:
                    write_snapshot.retention_status = "flagged"
                    write_snapshot.risk_level = result.risk_level or "medium"
                    write_snapshot.risk_categories_json = json.dumps(categories, ensure_ascii=False)

            event = SecurityRiskEvent(
                event_id=str(uuid.uuid4()),
                snapshot_id=getattr(write_snapshot or snapshot, "snapshot_id", None),
                snapshot_db_id=getattr(write_snapshot or snapshot, "id", None),
                request_id=getattr(write_snapshot or snapshot, "request_id", None),
                user_id=getattr(write_snapshot or snapshot, "user_id", None),
                agent_id=getattr(write_snapshot or snapshot, "agent_id", None),
                requested_model=getattr(write_snapshot or snapshot, "requested_model", None),
                protocol_type=getattr(write_snapshot or snapshot, "protocol_type", None),
                event_source=source,
                risk_level=result.risk_level or "medium",
                category=categories[0],
                action=result.action or "review",
                matched_rules_json=json.dumps(matched_rules, ensure_ascii=False),
                reason=result.reason,
                response_excerpt=response_excerpt[:4000] if response_excerpt else None,
                status="open",
            )
            write_db.add(event)
            write_db.flush()
            write_db.refresh(event)
            event_id = event.event_id
        return db.query(SecurityRiskEvent).filter(SecurityRiskEvent.event_id == event_id).first()

    @staticmethod
    def ensure_allowed_or_raise(
        db: Session,
        snapshot: Optional[SecurityRequestSnapshot],
        request_data: dict,
    ) -> SecurityDetectionResult:
        result = SecurityDetectionService.scan_request(db, snapshot, request_data)
        if result.should_block and SecurityDetectionService._get_bool_config(db, "security_keyword_block_enabled", True):
            try:
                SecurityDetectionService.record_risk_event(db, snapshot, "keyword", result)
            except Exception as exc:
                logger.error("Failed to record blocked security risk event: %s", exc, exc_info=True)
            block_message = str(get_system_config(
                db,
                "security_block_message",
                "请求可能涉及违规或高风险内容，已被安全策略拦截。你可以改为询问合法合规的学习、防护或排查建议。",
            ))
            raise ServiceException(403, block_message, "SECURITY_RISK_BLOCKED")
        if result.risk_level != "none" and snapshot is not None:
            SecurityDetectionService.record_risk_event(db, snapshot, "keyword", result)
        return result

    @staticmethod
    def build_security_system_prompt(
        db: Session,
        snapshot: Optional[SecurityRequestSnapshot] = None,
        report_token: Optional[str] = None,
    ) -> str:
        if not SecurityDetectionService._get_bool_config(db, "security_model_prompt_enabled", True):
            return ""
        # Keep this prompt static. Prompt-cache providers key on exact prefix
        # content, so per-request values such as snapshot_id/report_token would
        # destroy cache reuse and can also distort model behavior.
        return (
            "安全策略：不得生成、补全、改写或指导任何色情、未成年人性内容、破限提示词、"
            "绕过审查、破解、注册机、盗号、撞库、验证码绕过、风控对抗、网站攻击、恶意自动化等内容。"
            "如果用户以学生、作业、老师要求、仅供学习、CTF、靶场、授权测试等理由请求上述内容，"
            "也必须拒绝具体步骤、代码和可执行方法，并提供合法合规的防护、学习或报告建议。"
            "当识别到用户请求存在上述风险时，先拒绝，再输出内部风险标记：[MIS_RISK_REPORT category=... severity=...]。"
        )

    @staticmethod
    def scan_model_output(
        db: Session,
        snapshot: Optional[SecurityRequestSnapshot],
        output_text: str,
        config_key: str = "security_output_scan_enabled",
    ) -> tuple[str, Optional[SecurityRiskEvent]]:
        text = str(output_text or "")
        if config_key and not SecurityDetectionService._get_bool_config(db, config_key, True):
            return text, None
        match = SecurityDetectionService.RISK_MARKER_PATTERN.search(text)
        if not match:
            return text, None
        category = match.group("category") or "unknown"
        severity = match.group("severity") or "medium"
        cleaned = SecurityDetectionService.RISK_MARKER_PATTERN.sub("", text).strip()
        result = SecurityDetectionResult(
            risk_level="high" if severity.lower() in {"high", "blocked"} else "medium",
            action="review",
            categories=[category],
            matched_rules=[{"category": category, "term": "MIS_RISK_REPORT"}],
            reason="模型输出风险上报标记",
        )
        event = SecurityDetectionService.record_risk_event(
            db,
            snapshot,
            "model_report",
            result,
            response_excerpt=cleaned[:4000],
        )
        return cleaned, event

    @staticmethod
    def _check_public_report_rate_limit(db: Session, client_ip: Optional[str]) -> None:
        limit = SecurityDetectionService._get_int_config(db, "security_public_report_rate_limit_per_minute", 60)
        if limit <= 0:
            return
        key = str(client_ip or "unknown")
        now = time.time()
        recent = [
            ts for ts in SecurityDetectionService._PUBLIC_REPORT_IP_BUCKETS.get(key, [])
            if now - ts < 60
        ]
        if len(recent) >= limit:
            raise ServiceException(429, "上报过于频繁，请稍后再试", "SECURITY_REPORT_RATE_LIMITED")
        recent.append(now)
        SecurityDetectionService._PUBLIC_REPORT_IP_BUCKETS[key] = recent

    @staticmethod
    def handle_public_report(db: Session, payload: dict[str, Any], client_ip: Optional[str]) -> dict[str, Any]:
        if not SecurityDetectionService._get_bool_config(db, "security_public_report_enabled", True):
            raise ServiceException(404, "风险上报接口未启用", "SECURITY_REPORT_DISABLED")
        SecurityDetectionService._check_public_report_rate_limit(db, client_ip)

        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        report_token = str(payload.get("report_token") or "").strip()
        if not snapshot_id or not report_token:
            raise ServiceException(400, "缺少上报凭证", "SECURITY_REPORT_INVALID")
        snapshot = db.query(SecurityRequestSnapshot).filter(
            SecurityRequestSnapshot.snapshot_id == snapshot_id
        ).first()
        if not snapshot or not snapshot.report_token_hash:
            raise ServiceException(403, "上报凭证无效", "SECURITY_REPORT_FORBIDDEN")
        if snapshot.expires_at and snapshot.expires_at < datetime.utcnow() and snapshot.retention_status != "flagged":
            raise ServiceException(403, "上报凭证已过期", "SECURITY_REPORT_EXPIRED")
        if SecurityDetectionService._hash_text(report_token) != snapshot.report_token_hash:
            raise ServiceException(403, "上报凭证无效", "SECURITY_REPORT_FORBIDDEN")

        category = str(payload.get("category") or "unknown").strip()[:64]
        severity = str(payload.get("severity") or "medium").strip().lower()
        reason = str(payload.get("reason") or "模型通过公开接口上报风险").strip()[:2000]
        existing = db.query(SecurityRiskEvent).filter(
            SecurityRiskEvent.snapshot_id == snapshot.snapshot_id,
            SecurityRiskEvent.category == category,
            SecurityRiskEvent.event_source == "model_report_api",
        ).first()
        if existing:
            return {"event_id": existing.event_id, "deduplicated": True}

        result = SecurityDetectionResult(
            risk_level="high" if severity in {"high", "blocked"} else "medium",
            action="review",
            categories=[category],
            matched_rules=[{"category": category, "term": "public_report"}],
            reason=reason,
        )
        event = SecurityDetectionService.record_risk_event(db, snapshot, "model_report_api", result)
        return {"event_id": event.event_id if event else None, "deduplicated": False}

    @staticmethod
    def purge_expired_snapshots(db: Session, limit: int = 500) -> int:
        now = datetime.utcnow()
        effective_limit = max(int(limit or 500), 1)
        rows = (
            db.query(SecurityRequestSnapshot)
            .filter(
                SecurityRequestSnapshot.retention_status == "temporary",
                SecurityRequestSnapshot.expires_at.isnot(None),
                SecurityRequestSnapshot.expires_at < now,
            )
            .order_by(SecurityRequestSnapshot.id.asc())
            .limit(effective_limit)
            .all()
        )

        remaining_limit = max(effective_limit - len(rows), 0)
        if remaining_limit > 0:
            retention_days = SecurityDetectionService._get_int_config(db, "security_flagged_retention_days", 30)
            if retention_days > 0:
                flagged_cutoff = now - timedelta(days=retention_days)
                rows.extend(
                    db.query(SecurityRequestSnapshot)
                    .filter(
                        SecurityRequestSnapshot.retention_status == "flagged",
                        SecurityRequestSnapshot.created_at < flagged_cutoff,
                    )
                    .order_by(SecurityRequestSnapshot.id.asc())
                    .limit(remaining_limit)
                    .all()
                )

        for row in rows:
            row.request_body_json = None
            row.extracted_text = None
            row.retention_status = "purged"
            row.purged_at = now
        db.commit()
        return len(rows)

    @staticmethod
    def _event_to_dict(event: SecurityRiskEvent, username: Optional[str] = None) -> dict[str, Any]:
        return {
            "id": event.id,
            "event_id": event.event_id,
            "snapshot_id": event.snapshot_id,
            "request_id": event.request_id,
            "user_id": event.user_id,
            "agent_id": event.agent_id,
            "username": username,
            "requested_model": event.requested_model,
            "protocol_type": event.protocol_type,
            "event_source": event.event_source,
            "risk_level": event.risk_level,
            "category": event.category,
            "action": event.action,
            "reason": event.reason,
            "status": event.status,
            "reviewer_id": event.reviewer_id,
            "review_note": event.review_note,
            "reviewed_at": event.reviewed_at.isoformat() if event.reviewed_at else None,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    @staticmethod
    def list_risk_events(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        risk_level: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        from app.models.user import SysUser

        query = db.query(SecurityRiskEvent)
        if user_id is not None:
            query = query.filter(SecurityRiskEvent.user_id == user_id)
        if category:
            query = query.filter(SecurityRiskEvent.category == category)
        if risk_level:
            query = query.filter(SecurityRiskEvent.risk_level == risk_level)
        if source:
            query = query.filter(SecurityRiskEvent.event_source == source)
        if status:
            query = query.filter(SecurityRiskEvent.status == status)
        total = query.order_by(None).count()
        events = (
            query.order_by(SecurityRiskEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        user_ids = {event.user_id for event in events if event.user_id is not None}
        user_map = {}
        if user_ids:
            user_map = {
                row.id: row.username
                for row in db.query(SysUser.id, SysUser.username).filter(SysUser.id.in_(user_ids)).all()
            }
        return [SecurityDetectionService._event_to_dict(event, user_map.get(event.user_id)) for event in events], total

    @staticmethod
    def get_risk_event_detail(
        db: Session,
        event_id: str,
        current_user: Optional[SysUser] = None,
        client_ip: Optional[str] = None,
    ) -> dict[str, Any]:
        event = db.query(SecurityRiskEvent).filter(SecurityRiskEvent.event_id == event_id).first()
        if not event:
            raise ServiceException(404, "风险事件不存在", "SECURITY_EVENT_NOT_FOUND")
        snapshot = None
        if event.snapshot_id:
            snapshot = db.query(SecurityRequestSnapshot).filter(
                SecurityRequestSnapshot.snapshot_id == event.snapshot_id
            ).first()
        if current_user is not None:
            db.add(OperationLog(
                user_id=current_user.id,
                username=current_user.username,
                action="security_risk_event_view",
                target_type="security_risk_event",
                target_id=event.id,
                description=f"查看安全风控事件 event_id={event.event_id} snapshot_id={event.snapshot_id}",
                ip_address=client_ip,
            ))
            db.commit()
        detail = SecurityDetectionService._event_to_dict(event)
        detail["matched_rules"] = json.loads(event.matched_rules_json or "[]")
        detail["response_excerpt"] = event.response_excerpt
        detail["snapshot"] = None
        if snapshot:
            detail["snapshot"] = {
                "snapshot_id": snapshot.snapshot_id,
                "retention_status": snapshot.retention_status,
                "request_id": snapshot.request_id,
                "request_preview": snapshot.request_preview,
                "request_body_json": snapshot.request_body_json,
                "extracted_text": snapshot.extracted_text,
                "is_truncated": bool(snapshot.is_truncated),
                "body_size_bytes": snapshot.body_size_bytes,
                "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
                "purged_at": snapshot.purged_at.isoformat() if snapshot.purged_at else None,
                "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
            }
        return detail

    @staticmethod
    def get_risk_stats(db: Session) -> dict[str, Any]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "open_count": db.query(SecurityRiskEvent).filter(SecurityRiskEvent.status == "open").count(),
            "high_count": db.query(SecurityRiskEvent).filter(SecurityRiskEvent.risk_level.in_(("high", "blocked"))).count(),
            "today_count": db.query(SecurityRiskEvent).filter(SecurityRiskEvent.created_at >= today).count(),
            "blocked_count": db.query(SecurityRiskEvent).filter(SecurityRiskEvent.action == "block").count(),
            "purged_snapshot_count": db.query(SecurityRequestSnapshot).filter(SecurityRequestSnapshot.retention_status == "purged").count(),
        }
