"""Online recharge order service with Alipay and WeChat Pay support."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.exceptions import ServiceException
from app.models.log import ConsumptionRecord, ImageCreditRecord, UserBalance, UserImageBalance
from app.models.payment import (
    AgentCashBalance,
    AgentCashLedger,
    PaymentRechargeOrder,
    PaymentRechargeSettlement,
)
from app.models.user import SysUser
from app.services.agent_service import AgentService, AgentSiteContext

logger = logging.getLogger(__name__)


class PaymentService:
    """Unified online recharge flow for multiple payment channels."""

    CNY_SCALE = Decimal("0.01")
    USD_SCALE = Decimal("0.000001")
    ORDER_EXPIRE_MINUTES = 30
    DEFAULT_CHANNEL = "alipay"
    PAYMENT_CHANNELS = {"alipay", "wechat"}
    RECHARGE_TYPES = {"balance", "image_credit"}
    ALIPAY_ACCEPTED_TRADE_STATUSES = {"TRADE_SUCCESS", "TRADE_FINISHED"}
    WECHAT_PENDING_STATES = {"NOTPAY", "USERPAYING"}
    WECHAT_SUCCESS_STATES = {"SUCCESS"}
    WECHAT_CLOSED_STATES = {"CLOSED", "REVOKED"}
    WECHAT_FAILED_STATES = {"PAYERROR"}
    PAYMENT_CHANNEL_TEXT = {"alipay": "支付宝", "wechat": "微信"}
    RECHARGE_TYPE_TEXT = {"balance": "余额", "image_credit": "图片积分"}

    @staticmethod
    def _serialize_dt(dt: datetime | None, *, assume_utc: bool) -> str | None:
        if not dt:
            return None
        if dt.tzinfo is not None:
            return dt.isoformat()
        tz = timezone.utc if assume_utc else timezone(timedelta(hours=8))
        return dt.replace(tzinfo=tz).isoformat()

    @staticmethod
    def _quantize(value, scale: Decimal, code: str, allow_zero: bool = False) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(scale, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "金额格式不正确", code) from exc
        if allow_zero:
            if amount < Decimal("0"):
                raise ServiceException(400, "金额不能小于 0", code)
        elif amount <= Decimal("0"):
            raise ServiceException(400, "金额必须大于 0", code)
        return amount

    @staticmethod
    def _normalize_cny(value, code: str = "INVALID_RECHARGE_AMOUNT") -> Decimal:
        return PaymentService._quantize(value, PaymentService.CNY_SCALE, code)

    @staticmethod
    def _normalize_usd(value, code: str = "INVALID_USD_AMOUNT", allow_zero: bool = False) -> Decimal:
        return PaymentService._quantize(value, PaymentService.USD_SCALE, code, allow_zero=allow_zero)

    @staticmethod
    def _normalize_image_credits(value, code: str = "INVALID_IMAGE_CREDIT_AMOUNT", allow_zero: bool = False) -> Decimal:
        return PaymentService._quantize(value, Decimal("0.001"), code, allow_zero=allow_zero)

    @staticmethod
    def _try_normalize_cny(value) -> Decimal | None:
        if value is None:
            return None
        try:
            amount = Decimal(str(value)).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None
        return amount

    @staticmethod
    def _settings_decimal(value, code: str) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(500, "支付配置无效", code) from exc
        if amount <= Decimal("0"):
            raise ServiceException(500, "支付配置无效", code)
        return amount

    @staticmethod
    def _normalize_payment_channel(payment_channel: str | None) -> str:
        channel = str(payment_channel or PaymentService.DEFAULT_CHANNEL).strip().lower()
        if channel not in PaymentService.PAYMENT_CHANNELS:
            raise ServiceException(400, "不支持的支付渠道", "PAYMENT_CHANNEL_INVALID")
        return channel

    @staticmethod
    def _normalize_recharge_type(recharge_type: str | None) -> str:
        normalized = str(recharge_type or "balance").strip().lower()
        if normalized not in PaymentService.RECHARGE_TYPES:
            raise ServiceException(400, "不支持的充值类型", "RECHARGE_TYPE_INVALID")
        return normalized

    @staticmethod
    def _payment_channel_text(payment_channel: str | None) -> str:
        channel = str(payment_channel or "").strip().lower()
        return PaymentService.PAYMENT_CHANNEL_TEXT.get(channel, channel or "-")

    @staticmethod
    def _recharge_type_text(recharge_type: str | None) -> str:
        normalized = PaymentService._normalize_recharge_type(recharge_type)
        return PaymentService.RECHARGE_TYPE_TEXT.get(normalized, normalized)

    @staticmethod
    def _is_local_host(host: str | None) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"} or normalized.endswith(".localhost") or normalized.endswith(".local")

    @staticmethod
    def _build_origin_from_host(host: str | None) -> str:
        normalized = AgentService.normalize_host(host)
        if not normalized:
            raise ServiceException(500, "无法生成支付回跳地址", "PAYMENT_RETURN_HOST_MISSING")
        scheme = "http" if PaymentService._is_local_host(normalized) else "https"
        return f"{scheme}://{normalized}"

    @staticmethod
    def _build_origin_from_site_context(site_context: AgentSiteContext | None) -> str:
        if not site_context:
            return ""
        for raw_url in (getattr(site_context, "origin_url", ""), getattr(site_context, "referer_url", "")):
            value = str(raw_url or "").strip()
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return ""

    @staticmethod
    def _get_platform_frontend_host() -> str:
        for item in settings.PLATFORM_FRONTEND_HOSTS:
            normalized = AgentService.normalize_host(item)
            if normalized and not AgentService.is_platform_api_host(normalized):
                return normalized
        raise ServiceException(500, "未配置平台前台域名", "PAYMENT_PLATFORM_HOST_MISSING")

    @staticmethod
    def _append_query(url: str, params: dict[str, str]) -> str:
        parsed = urlparse(url)
        current = dict(parse_qsl(parsed.query, keep_blank_values=True))
        current.update({k: v for k, v in params.items() if v is not None})
        return urlunparse(parsed._replace(query=urlencode(current)))

    @staticmethod
    def _normalize_pem_text(raw_value: str | None) -> str:
        return str(raw_value or "").strip().replace("\\n", "\n")

    @staticmethod
    def _build_pem_key(raw_key: str, *, code: str, label: str) -> bytes:
        text = PaymentService._normalize_pem_text(raw_key)
        if not text:
            raise ServiceException(500, f"缺少{label}配置", code)
        if "BEGIN PUBLIC KEY" in text:
            return text.encode("utf-8")
        wrapped = "-----BEGIN PUBLIC KEY-----\n" + text + "\n-----END PUBLIC KEY-----\n"
        return wrapped.encode("utf-8")

    @staticmethod
    def _build_private_pem_key(raw_key: str, *, missing_code: str, invalid_code: str, label: str) -> bytes:
        text = PaymentService._normalize_pem_text(raw_key)
        if not text:
            raise ServiceException(500, f"缺少{label}配置", missing_code)

        if "BEGIN " not in text:
            text = "-----BEGIN PRIVATE KEY-----\n" + text + "\n-----END PRIVATE KEY-----\n"

        try:
            private_key = load_pem_private_key(text.encode("utf-8"), password=None)
        except Exception as exc:
            raise ServiceException(500, f"{label}格式无效", invalid_code) from exc

        return private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )

    @staticmethod
    def _build_wechat_private_key():
        raw_pem = PaymentService._build_private_pem_key(
            settings.WECHAT_PAY_PRIVATE_KEY,
            missing_code="WECHAT_PAY_PRIVATE_KEY_MISSING",
            invalid_code="WECHAT_PAY_PRIVATE_KEY_INVALID",
            label="微信支付商户私钥",
        )
        return load_pem_private_key(raw_pem, password=None)

    @staticmethod
    def _get_alipay_notify_url() -> str:
        configured = str(settings.ALIPAY_NOTIFY_URL or "").strip()
        if configured:
            return configured
        base = str(settings.PAYMENT_PUBLIC_BASE_URL or "").strip().rstrip("/")
        if not base:
            raise ServiceException(500, "缺少支付宝通知地址配置", "ALIPAY_NOTIFY_URL_MISSING")
        return f"{base}/api/public/payment/alipay/notify"

    @staticmethod
    def _get_wechat_notify_url() -> str:
        configured = str(settings.WECHAT_PAY_NOTIFY_URL or "").strip()
        if configured:
            return configured
        base = str(settings.PAYMENT_PUBLIC_BASE_URL or "").strip().rstrip("/")
        if not base:
            raise ServiceException(500, "缺少微信支付通知地址配置", "WECHAT_PAY_NOTIFY_URL_MISSING")
        return f"{base}/api/public/payment/wechat/notify"

    @staticmethod
    def _validate_alipay_config() -> None:
        if not bool(settings.ALIPAY_ENABLED):
            raise ServiceException(400, "在线充值暂未开启", "PAYMENT_DISABLED")
        if not str(settings.ALIPAY_APP_ID or "").strip():
            raise ServiceException(500, "缺少支付宝 AppId 配置", "ALIPAY_APP_ID_MISSING")
        if not str(settings.ALIPAY_APP_PRIVATE_KEY or "").strip():
            raise ServiceException(500, "缺少支付宝应用私钥配置", "ALIPAY_PRIVATE_KEY_MISSING")
        if not str(settings.ALIPAY_PUBLIC_KEY or "").strip():
            raise ServiceException(500, "缺少支付宝公钥配置", "ALIPAY_PUBLIC_KEY_MISSING")
        PaymentService._get_alipay_notify_url()

    @staticmethod
    def _validate_wechat_config() -> None:
        if not bool(settings.WECHAT_PAY_ENABLED):
            raise ServiceException(400, "微信支付暂未开启", "WECHAT_PAY_DISABLED")
        required = [
            (settings.WECHAT_PAY_APP_ID, "WECHAT_PAY_APP_ID_MISSING", "微信支付 AppId"),
            (settings.WECHAT_PAY_MCH_ID, "WECHAT_PAY_MCH_ID_MISSING", "微信支付商户号"),
            (settings.WECHAT_PAY_SERIAL_NO, "WECHAT_PAY_SERIAL_NO_MISSING", "微信支付商户证书序列号"),
            (settings.WECHAT_PAY_PRIVATE_KEY, "WECHAT_PAY_PRIVATE_KEY_MISSING", "微信支付商户私钥"),
            (settings.WECHAT_PAY_API_V3_KEY, "WECHAT_PAY_API_V3_KEY_MISSING", "微信支付 APIv3 密钥"),
        ]
        for value, code, label in required:
            if not str(value or "").strip():
                raise ServiceException(500, f"缺少{label}配置", code)
        if not str(settings.WECHAT_PAY_PLATFORM_CERT or settings.WECHAT_PAY_PLATFORM_PUBLIC_KEY or "").strip():
            raise ServiceException(500, "缺少微信支付平台证书或平台公钥配置", "WECHAT_PAY_PLATFORM_CERT_MISSING")
        PaymentService._get_wechat_notify_url()

    @staticmethod
    def _get_wechat_request_serial() -> str:
        public_key_id = str(settings.WECHAT_PAY_PUBLIC_KEY_ID or "").strip()
        if public_key_id:
            return public_key_id
        return str(settings.WECHAT_PAY_PLATFORM_SERIAL or "").strip()

    @staticmethod
    def _validate_payment_config(payment_channel: str) -> None:
        channel = PaymentService._normalize_payment_channel(payment_channel)
        if channel == "alipay":
            PaymentService._validate_alipay_config()
            return
        if channel == "wechat":
            PaymentService._validate_wechat_config()
            return
        raise ServiceException(400, "不支持的支付渠道", "PAYMENT_CHANNEL_INVALID")

    @staticmethod
    def assert_recharge_enabled_for_site(site_context: AgentSiteContext | None = None, payment_channel: str | None = None) -> None:
        channel = PaymentService._normalize_payment_channel(payment_channel)
        PaymentService._validate_payment_config(channel)
        if site_context and not AgentService.is_online_recharge_enabled(site_context):
            raise ServiceException(403, "当前站点未开启在线充值", "AGENT_ONLINE_RECHARGE_DISABLED")

    @staticmethod
    def _build_alipay_client():
        try:
            from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
            from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        config = AlipayClientConfig()
        config.server_url = settings.ALIPAY_SERVER_URL
        config.app_id = settings.ALIPAY_APP_ID
        config.app_private_key = PaymentService._build_private_pem_key(
            settings.ALIPAY_APP_PRIVATE_KEY,
            missing_code="ALIPAY_PRIVATE_KEY_MISSING",
            invalid_code="ALIPAY_PRIVATE_KEY_INVALID",
            label="支付宝应用私钥",
        ).decode("utf-8")
        config.alipay_public_key = load_pem_public_key(
            PaymentService._build_pem_key(
                settings.ALIPAY_PUBLIC_KEY,
                code="ALIPAY_PUBLIC_KEY_MISSING",
                label="支付宝公钥",
            )
        ).public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return DefaultAlipayClient(alipay_client_config=config)

    @staticmethod
    def _generate_order_no(payment_channel: str) -> str:
        prefix = "ALP" if payment_channel == "alipay" else "WXP"
        return prefix + datetime.utcnow().strftime("%Y%m%d%H%M%S") + secrets.token_hex(3).upper()

    @staticmethod
    def _build_subject(recharge_type: str = "balance") -> str:
        return f"AI 平台{PaymentService._recharge_type_text(recharge_type)}充值"

    @staticmethod
    def _build_body(recharge_type: str = "balance") -> str:
        if PaymentService._normalize_recharge_type(recharge_type) == "image_credit":
            return "用户在线充值图片积分"
        return "用户在线充值美元余额"

    @staticmethod
    def build_order_return_url(order: PaymentRechargeOrder, site_context: AgentSiteContext | None = None) -> str:
        explicit_origin = PaymentService._build_origin_from_site_context(site_context)
        if explicit_origin:
            base = f"{explicit_origin.rstrip('/')}{str(settings.ALIPAY_RETURN_PATH or '/user/recharge')}"
            return PaymentService._append_query(base, {"order_no": order.order_no})

        source_host = AgentService.normalize_host(getattr(site_context, "host", None) or order.source_host)
        if not source_host and order.site_scope == "agent":
            raise ServiceException(500, "代理站点缺少前台域名，无法创建回跳地址", "PAYMENT_RETURN_HOST_MISSING")
        if not source_host:
            source_host = PaymentService._get_platform_frontend_host()
        origin = PaymentService._build_origin_from_host(source_host)
        base = f"{origin.rstrip('/')}{str(settings.ALIPAY_RETURN_PATH or '/user/recharge')}"
        return PaymentService._append_query(base, {"order_no": order.order_no})

    @staticmethod
    def _calculate_amounts(amount_cny: Decimal, agent_id: int | None, recharge_type: str = "balance") -> tuple[Decimal, Decimal, Decimal, Decimal]:
        normalized_type = PaymentService._normalize_recharge_type(recharge_type)
        if normalized_type == "image_credit":
            user_rate = PaymentService._settings_decimal(
                settings.RECHARGE_IMAGE_CREDIT_USER_CNY_RATE,
                "RECHARGE_IMAGE_CREDIT_USER_RATE_INVALID",
            )
            agent_rate = PaymentService._settings_decimal(
                settings.RECHARGE_IMAGE_CREDIT_AGENT_CNY_RATE,
                "RECHARGE_IMAGE_CREDIT_AGENT_RATE_INVALID",
            )
            credited_image_credits = (amount_cny * user_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            if not agent_id:
                return Decimal("0.000000"), credited_image_credits, agent_rate, Decimal("0.00")

            agent_cost_cny = (credited_image_credits / agent_rate).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
            agent_income_cny = (amount_cny - agent_cost_cny).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
            if agent_income_cny < Decimal("0"):
                raise ServiceException(500, "代理图片积分结算比例配置错误，导致代理分润为负数", "RECHARGE_AGENT_INCOME_INVALID")
            return Decimal("0.000000"), credited_image_credits, agent_rate, agent_income_cny

        user_rate = PaymentService._settings_decimal(settings.RECHARGE_USER_CNY_TO_USD_RATE, "RECHARGE_USER_RATE_INVALID")
        agent_rate = PaymentService._settings_decimal(settings.RECHARGE_AGENT_CNY_TO_USD_SETTLEMENT_RATE, "RECHARGE_AGENT_RATE_INVALID")
        credited_usd = (amount_cny * user_rate).quantize(PaymentService.USD_SCALE, rounding=ROUND_HALF_UP)
        if not agent_id:
            return credited_usd, Decimal("0.000"), agent_rate, Decimal("0.00")

        agent_cost_cny = (credited_usd / agent_rate).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        agent_income_cny = (amount_cny - agent_cost_cny).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        if agent_income_cny < Decimal("0"):
            raise ServiceException(500, "代理结算比例配置错误，导致代理分润为负数", "RECHARGE_AGENT_INCOME_INVALID")
        return credited_usd, Decimal("0.000"), agent_rate, agent_income_cny

    @staticmethod
    def create_recharge_order(
        db: Session,
        user: SysUser,
        amount_cny,
        payment_channel: str = DEFAULT_CHANNEL,
        recharge_type: str = "balance",
        site_context: AgentSiteContext | None = None,
    ) -> dict:
        channel = PaymentService._normalize_payment_channel(payment_channel)
        normalized_type = PaymentService._normalize_recharge_type(recharge_type)
        PaymentService.assert_recharge_enabled_for_site(site_context, channel)
        amount_decimal = PaymentService._normalize_cny(amount_cny)
        credited_usd, credited_image_credits, agent_rate, agent_income_cny = PaymentService._calculate_amounts(amount_decimal, user.agent_id, normalized_type)
        order = PaymentRechargeOrder(
            order_no=PaymentService._generate_order_no(channel),
            payment_channel=channel,
            recharge_type=normalized_type,
            user_id=user.id,
            agent_id=user.agent_id,
            site_scope="agent" if user.agent_id else "platform",
            source_host=AgentService.normalize_host(getattr(site_context, "host", None) or getattr(site_context, "request_host", None)),
            amount_cny=amount_decimal,
            credited_usd=credited_usd,
            credited_image_credits=credited_image_credits,
            agent_settlement_rate=agent_rate,
            agent_income_cny=agent_income_cny,
            status="pending",
            subject=PaymentService._build_subject(normalized_type),
            body=PaymentService._build_body(normalized_type),
            expired_at=datetime.utcnow() + timedelta(minutes=PaymentService.ORDER_EXPIRE_MINUTES),
        )
        order.return_url_snapshot = PaymentService.build_order_return_url(order, site_context)
        db.add(order)
        db.flush()

        response_payload = {"order": PaymentService.serialize_order(order)}
        if channel == "alipay":
            response_payload["pay_url"] = PaymentService.build_alipay_page_pay_url(order, order.return_url_snapshot)
        elif channel == "wechat":
            wechat_payload = PaymentService.create_wechat_native_order(db, order)
            response_payload.update(wechat_payload)
        else:  # pragma: no cover - guarded by _normalize_payment_channel
            raise ServiceException(400, "不支持的支付渠道", "PAYMENT_CHANNEL_INVALID")

        db.commit()
        db.refresh(order)
        response_payload["order"] = PaymentService.serialize_order(order)
        return response_payload

    @staticmethod
    def _apply_request_urls(request, notify_url: str, return_url: str) -> None:
        if hasattr(request, "notify_url"):
            request.notify_url = notify_url
        if hasattr(request, "return_url"):
            request.return_url = return_url
        setter = getattr(request, "set_notify_url", None)
        if callable(setter):
            setter(notify_url)
        setter = getattr(request, "set_return_url", None)
        if callable(setter):
            setter(return_url)

    @staticmethod
    def build_alipay_page_pay_url(order: PaymentRechargeOrder, return_url: str) -> str:
        PaymentService._validate_alipay_config()
        try:
            from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
            from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        client = PaymentService._build_alipay_client()
        model = AlipayTradePagePayModel()
        model.out_trade_no = order.order_no
        model.total_amount = str(Decimal(str(order.amount_cny or 0)).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP))
        model.subject = order.subject
        model.body = order.body
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        model.timeout_express = f"{PaymentService.ORDER_EXPIRE_MINUTES}m"
        request = AlipayTradePagePayRequest(biz_model=model)
        PaymentService._apply_request_urls(request, PaymentService._get_alipay_notify_url(), return_url)
        response = client.page_execute(request, http_method="GET")
        if not response:
            raise ServiceException(500, "支付宝下单失败，请稍后重试", "ALIPAY_PAGE_PAY_FAILED")
        return response

    @staticmethod
    def _format_wechat_amount(amount_cny: Decimal) -> int:
        normalized = PaymentService._normalize_cny(amount_cny)
        return int((normalized * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _build_wechat_authorization(method: str, canonical_url: str, body: str) -> str:
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        nonce = secrets.token_hex(16)
        message = f"{method}\n{canonical_url}\n{timestamp}\n{nonce}\n{body}\n"
        private_key = PaymentService._build_wechat_private_key()
        signature = private_key.sign(
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        signed = base64.b64encode(signature).decode("utf-8")
        return (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{settings.WECHAT_PAY_MCH_ID}",'
            f'nonce_str="{nonce}",'
            f'signature="{signed}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{settings.WECHAT_PAY_SERIAL_NO}"'
        )

    @staticmethod
    def _wechat_headers(method: str, canonical_url: str, body: str) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": PaymentService._build_wechat_authorization(method, canonical_url, body),
            "User-Agent": "modelInvocationSystem/1.0",
        }
        request_serial = PaymentService._get_wechat_request_serial()
        if request_serial:
            headers["Wechatpay-Serial"] = request_serial
        return headers

    @staticmethod
    def _wechat_request(method: str, path: str, payload: dict | None = None) -> dict:
        PaymentService._validate_wechat_config()
        base_url = str(settings.WECHAT_PAY_SERVER_URL or "https://api.mch.weixin.qq.com").strip().rstrip("/")
        body = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")) if payload is not None else ""
        headers = PaymentService._wechat_headers(method, path, body)
        try:
            response = httpx.request(
                method=method,
                url=f"{base_url}{path}",
                content=body.encode("utf-8") if body else None,
                headers=headers,
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            raise ServiceException(500, "微信支付请求失败，请稍后重试", "WECHAT_PAY_REQUEST_FAILED") from exc
        if response.status_code >= 400:
            logger.error("WeChat pay request failed: status=%s body=%s", response.status_code, response.text)
            raise ServiceException(500, "微信支付请求失败", "WECHAT_PAY_REQUEST_FAILED")
        if not response.text:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ServiceException(500, "微信支付响应解析失败", "WECHAT_PAY_RESPONSE_INVALID") from exc

    @staticmethod
    def create_wechat_native_order(db: Session, order: PaymentRechargeOrder) -> dict:
        payload = {
            "appid": str(settings.WECHAT_PAY_APP_ID or "").strip(),
            "mchid": str(settings.WECHAT_PAY_MCH_ID or "").strip(),
            "description": order.subject,
            "out_trade_no": order.order_no,
            "notify_url": PaymentService._get_wechat_notify_url(),
            "amount": {
                "total": PaymentService._format_wechat_amount(Decimal(str(order.amount_cny or 0))),
                "currency": "CNY",
            },
        }
        response = PaymentService._wechat_request("POST", "/v3/pay/transactions/native", payload)
        code_url = str(response.get("code_url") or "").strip()
        if not code_url:
            raise ServiceException(500, "微信支付下单失败，未返回二维码链接", "WECHAT_PAY_CODE_URL_MISSING")
        order.wechat_code_url = code_url
        return {
            "display_mode": "qrcode",
            "wechat_code_url": code_url,
            "code_url": code_url,
        }

    @staticmethod
    def _serialize_query_response(response) -> dict:
        return {
            "trade_status": getattr(response, "trade_status", None),
            "alipay_trade_no": getattr(response, "trade_no", None),
            "buyer_logon_id": getattr(response, "buyer_logon_id", None),
            "buyer_user_id": getattr(response, "buyer_user_id", None),
            "total_amount": getattr(response, "total_amount", None),
        }

    @staticmethod
    def query_alipay_order(order_no: str) -> dict:
        PaymentService._validate_alipay_config()
        try:
            from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
            from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest
            from alipay.aop.api.response.AlipayTradeQueryResponse import AlipayTradeQueryResponse
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        client = PaymentService._build_alipay_client()
        model = AlipayTradeQueryModel()
        model.out_trade_no = order_no
        request = AlipayTradeQueryRequest(biz_model=model)
        response_content = client.execute(request)
        if not response_content:
            raise ServiceException(500, "支付宝查单失败", "ALIPAY_QUERY_FAILED")
        response = AlipayTradeQueryResponse()
        response.parse_response_content(response_content)
        if not response.is_success():
            code = str(getattr(response, "sub_code", None) or getattr(response, "code", None) or "")
            if code == "ACQ.TRADE_NOT_EXIST":
                return {"trade_status": "NOT_FOUND"}
            raise ServiceException(500, "支付宝查单失败", "ALIPAY_QUERY_FAILED")
        return PaymentService._serialize_query_response(response)

    @staticmethod
    def query_wechat_order(order_no: str) -> dict:
        path = f"/v3/pay/transactions/out-trade-no/{order_no}?mchid={settings.WECHAT_PAY_MCH_ID}"
        return PaymentService._wechat_request("GET", path)

    @staticmethod
    def _load_order_for_user(db: Session, order_no: str, user_id: int) -> PaymentRechargeOrder:
        order = (
            db.query(PaymentRechargeOrder)
            .filter(
                PaymentRechargeOrder.order_no == order_no,
                PaymentRechargeOrder.user_id == user_id,
            )
            .first()
        )
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
        return order

    @staticmethod
    def list_user_orders(db: Session, user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        query = db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.user_id == user_id)
        total = query.count()
        rows = (
            query.order_by(PaymentRechargeOrder.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [PaymentService.serialize_order(row) for row in rows], total

    @staticmethod
    def get_user_order(db: Session, user_id: int, order_no: str) -> dict:
        return PaymentService.serialize_order(PaymentService._load_order_for_user(db, order_no, user_id))

    @staticmethod
    def sync_order_status(db: Session, user_id: int, order_no: str) -> dict:
        order = PaymentService._load_order_for_user(db, order_no, user_id)
        if order.status == "paid":
            return PaymentService.serialize_order(order)

        channel = PaymentService._normalize_payment_channel(order.payment_channel)
        if channel == "alipay":
            upstream = PaymentService.query_alipay_order(order.order_no)
            trade_status = str(upstream.get("trade_status") or "")
            if trade_status in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES:
                return PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
            if trade_status == "TRADE_CLOSED":
                return PaymentService._mark_order_terminal(db, order.order_no, "closed", trade_status, payload=upstream, source="query")
            return PaymentService.serialize_order(order)

        upstream = PaymentService.query_wechat_order(order.order_no)
        trade_state = str(upstream.get("trade_state") or "").strip().upper()
        if trade_state in PaymentService.WECHAT_SUCCESS_STATES:
            return PaymentService._apply_paid_order(db, order.order_no, upstream, source="query")
        if trade_state in PaymentService.WECHAT_CLOSED_STATES:
            return PaymentService._mark_order_terminal(db, order.order_no, "closed", trade_state, payload=upstream, source="query")
        if trade_state in PaymentService.WECHAT_FAILED_STATES:
            return PaymentService._mark_order_terminal(db, order.order_no, "failed", trade_state, payload=upstream, source="query")
        return PaymentService.serialize_order(order)

    @staticmethod
    def sync_order_status_from_alipay(db: Session, user_id: int, order_no: str) -> dict:
        return PaymentService.sync_order_status(db, user_id, order_no)

    @staticmethod
    def _verify_alipay_signature(params: dict[str, str]) -> None:
        sign = str(params.get("sign") or "").strip()
        if not sign:
            raise ServiceException(400, "缺少支付宝签名", "ALIPAY_SIGN_MISSING")
        try:
            from alipay.aop.api.util.SignatureUtils import get_sign_content, verify_with_rsa
        except ImportError as exc:
            raise ServiceException(500, "未安装支付宝 SDK，请先安装依赖", "ALIPAY_SDK_NOT_INSTALLED") from exc

        public_key = str(settings.ALIPAY_PUBLIC_KEY or "").strip()
        candidates = [
            (
                "sdk_keep_sign_type",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key != "sign" and value is not None
                },
            ),
            (
                "doc_drop_sign_type",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key not in {"sign", "sign_type"} and value is not None
                },
            ),
            (
                "legacy_drop_empty",
                {
                    key: str(value)
                    for key, value in params.items()
                    if key not in {"sign", "sign_type"} and value is not None and str(value) != ""
                },
            ),
        ]

        seen_sign_contents: set[str] = set()
        errors: list[str] = []
        for strategy, candidate in candidates:
            sign_content = get_sign_content(candidate)
            if sign_content in seen_sign_contents:
                continue
            seen_sign_contents.add(sign_content)
            try:
                verified = bool(verify_with_rsa(public_key, sign_content.encode("utf-8"), sign))
            except Exception as exc:  # pragma: no cover - depends on upstream callback data
                errors.append(f"{strategy}:{exc}")
                continue
            if verified:
                if strategy != "sdk_keep_sign_type":
                    logger.warning("Alipay notify verified with fallback strategy: %s", strategy)
                return
            errors.append(f"{strategy}:verify_false")

        logger.error("Alipay signature verification failed. keys=%s errors=%s", sorted(params.keys()), errors)
        raise ServiceException(400, "支付宝签名校验失败", "ALIPAY_SIGN_INVALID")

    @staticmethod
    def _load_wechat_platform_public_key(serial_hint: str | None = None):
        serial_text = str(serial_hint or "").strip()
        public_key_id = str(settings.WECHAT_PAY_PUBLIC_KEY_ID or "").strip()
        if serial_text and public_key_id and serial_text == public_key_id:
            public_key = PaymentService._normalize_pem_text(settings.WECHAT_PAY_PLATFORM_PUBLIC_KEY)
            if not public_key:
                raise ServiceException(500, "缺少微信支付公钥配置", "WECHAT_PAY_PLATFORM_PUBLIC_KEY_MISSING")
            return load_pem_public_key(
                PaymentService._build_pem_key(public_key, code="WECHAT_PAY_PLATFORM_PUBLIC_KEY_MISSING", label="微信支付公钥")
            )

        if serial_text and serial_text.startswith("PUB_KEY_ID_"):
            raise ServiceException(
                500,
                f"回调使用了未知的微信支付公钥ID: {serial_text}",
                "WECHAT_PAY_PUBLIC_KEY_ID_MISMATCH",
            )

        if serial_text and not PaymentService._normalize_pem_text(settings.WECHAT_PAY_PLATFORM_CERT):
            raise ServiceException(
                500,
                f"当前回调使用平台证书序列号 {serial_text} 签名，但本地未配置 WECHAT_PAY_PLATFORM_CERT",
                "WECHAT_PAY_PLATFORM_CERT_MISSING",
            )

        cert_text = PaymentService._normalize_pem_text(settings.WECHAT_PAY_PLATFORM_CERT)
        if cert_text:
            if "BEGIN CERTIFICATE" in cert_text:
                cert = x509.load_pem_x509_certificate(cert_text.encode("utf-8"))
                return cert.public_key()
            if "BEGIN PUBLIC KEY" in cert_text:
                return load_pem_public_key(cert_text.encode("utf-8"))

        public_key = PaymentService._normalize_pem_text(settings.WECHAT_PAY_PLATFORM_PUBLIC_KEY)
        return load_pem_public_key(
            PaymentService._build_pem_key(public_key, code="WECHAT_PAY_PLATFORM_CERT_MISSING", label="微信支付平台公钥")
        )

    @staticmethod
    def _verify_wechat_notify_signature(headers: dict[str, str], body: str) -> None:
        normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
        timestamp = str(normalized_headers.get("wechatpay-timestamp") or "").strip()
        nonce = str(normalized_headers.get("wechatpay-nonce") or "").strip()
        signature = str(normalized_headers.get("wechatpay-signature") or "").strip()
        serial = str(normalized_headers.get("wechatpay-serial") or "").strip()
        if not timestamp or not nonce or not signature:
            raise ServiceException(400, "缺少微信支付签名头", "WECHAT_PAY_SIGN_HEADER_MISSING")
        message = f"{timestamp}\n{nonce}\n{body}\n"
        public_key = PaymentService._load_wechat_platform_public_key(serial)
        try:
            public_key.verify(
                base64.b64decode(signature),
                message.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception as exc:
            logger.error(
                "WeChat notify signature verify failed: serial=%s expected_public_key_id=%s has_platform_cert=%s timestamp=%s nonce_len=%s body_len=%s",
                serial or "<missing>",
                str(settings.WECHAT_PAY_PUBLIC_KEY_ID or "").strip() or "<missing>",
                bool(PaymentService._normalize_pem_text(settings.WECHAT_PAY_PLATFORM_CERT)),
                timestamp,
                len(nonce),
                len(body),
            )
            raise ServiceException(400, "微信支付签名校验失败", "WECHAT_PAY_SIGN_INVALID") from exc

    @staticmethod
    def _decrypt_wechat_resource(resource: dict) -> dict:
        nonce = str(resource.get("nonce") or "").strip()
        ciphertext = str(resource.get("ciphertext") or "").strip()
        associated_data = str(resource.get("associated_data") or "")
        if not nonce or not ciphertext:
            raise ServiceException(400, "微信支付通知报文不完整", "WECHAT_PAY_NOTIFY_RESOURCE_INVALID")
        key = str(settings.WECHAT_PAY_API_V3_KEY or "").encode("utf-8")
        try:
            decrypted = AESGCM(key).decrypt(
                nonce.encode("utf-8"),
                base64.b64decode(ciphertext),
                associated_data.encode("utf-8") if associated_data else None,
            )
            return json.loads(decrypted.decode("utf-8"))
        except Exception as exc:
            raise ServiceException(400, "微信支付通知解密失败", "WECHAT_PAY_NOTIFY_DECRYPT_FAILED") from exc

    @staticmethod
    def _get_order_for_update(db: Session, order_no: str) -> PaymentRechargeOrder:
        order = (
            db.query(PaymentRechargeOrder)
            .filter(PaymentRechargeOrder.order_no == order_no)
            .with_for_update()
            .first()
        )
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
        return order

    @staticmethod
    def _get_or_create_agent_cash_balance_for_update(db: Session, agent_id: int) -> AgentCashBalance:
        balance = (
            db.query(AgentCashBalance)
            .filter(AgentCashBalance.agent_id == agent_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = AgentCashBalance(agent_id=agent_id, balance=0, total_income=0, total_withdrawn=0, total_adjusted=0)
            db.add(balance)
            db.flush()
            balance = (
                db.query(AgentCashBalance)
                .filter(AgentCashBalance.agent_id == agent_id)
                .with_for_update()
                .first()
            )
        return balance

    @staticmethod
    def _credit_user_balance(db: Session, order: PaymentRechargeOrder) -> None:
        existing_record = (
            db.query(ConsumptionRecord.id)
            .filter(
                ConsumptionRecord.user_id == order.user_id,
                ConsumptionRecord.request_id == order.order_no,
                ConsumptionRecord.total_cost < Decimal("0"),
            )
            .first()
        )
        if existing_record:
            logger.warning("Skip duplicate balance recharge credit for order %s", order.order_no)
            return

        balance = (
            db.query(UserBalance)
            .filter(UserBalance.user_id == order.user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            raise ServiceException(404, "用户余额记录不存在", "BALANCE_NOT_FOUND")

        credited_usd = PaymentService._normalize_usd(order.credited_usd)
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + credited_usd
        balance.total_recharged = Decimal(str(balance.total_recharged or 0)) + credited_usd

        db.add(ConsumptionRecord(
            user_id=order.user_id,
            agent_id=order.agent_id,
            request_id=order.order_no,
            model_name=f"{PaymentService._payment_channel_text(order.payment_channel)}充值",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            total_cost=-credited_usd,
            balance_before=balance_before,
            balance_after=balance.balance,
            billing_mode="balance",
            operator_id=None,
            remark=PaymentService._payment_channel_text(order.payment_channel),
        ))

    @staticmethod
    def _credit_user_image_credits(db: Session, order: PaymentRechargeOrder) -> None:
        existing_record = (
            db.query(ImageCreditRecord.id)
            .filter(
                ImageCreditRecord.user_id == order.user_id,
                ImageCreditRecord.request_id == order.order_no,
                ImageCreditRecord.action_type == "recharge",
                ImageCreditRecord.change_amount > Decimal("0"),
            )
            .first()
        )
        if existing_record:
            logger.warning("Skip duplicate image credit recharge credit for order %s", order.order_no)
            return

        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == order.user_id)
            .with_for_update()
            .first()
        )
        if not balance:
            balance = UserImageBalance(user_id=order.user_id, balance=0, total_recharged=0, total_consumed=0)
            db.add(balance)
            db.flush()
            balance = (
                db.query(UserImageBalance)
                .filter(UserImageBalance.user_id == order.user_id)
                .with_for_update()
                .first()
            )

        credited = PaymentService._normalize_image_credits(order.credited_image_credits)
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + credited
        balance.total_recharged = Decimal(str(balance.total_recharged or 0)) + credited

        db.add(ImageCreditRecord(
            user_id=order.user_id,
            agent_id=order.agent_id,
            request_id=order.order_no,
            model_name=f"{PaymentService._payment_channel_text(order.payment_channel)}充值",
            change_amount=credited,
            balance_before=balance_before,
            balance_after=balance.balance,
            multiplier=Decimal("1"),
            action_type="recharge",
            operator_id=None,
            remark=PaymentService._payment_channel_text(order.payment_channel),
        ))

    @staticmethod
    def _credit_user_order_asset(db: Session, order: PaymentRechargeOrder) -> None:
        if PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None)) == "image_credit":
            PaymentService._credit_user_image_credits(db, order)
            return
        PaymentService._credit_user_balance(db, order)

    @staticmethod
    def _settlement_asset_type(order: PaymentRechargeOrder) -> str:
        if PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None)) == "image_credit":
            return "image_credit"
        return "balance"

    @staticmethod
    def _is_duplicate_settlement_integrity_error(exc: IntegrityError) -> bool:
        orig = getattr(exc, "orig", None)
        parts = []
        if orig is not None:
            parts.extend(str(item) for item in getattr(orig, "args", ()) or ())
        parts.append(str(exc))
        message = " ".join(parts).lower()
        duplicate_markers = (
            "duplicate entry",
            "duplicate key",
            "unique constraint failed",
            "unique violation",
            "violates unique constraint",
        )
        settlement_markers = (
            "uk_payment_recharge_settlement_order_asset",
            "payment_recharge_settlement.order_no",
            "payment_recharge_settlement.asset_type",
        )
        return any(marker in message for marker in duplicate_markers) and any(
            marker in message for marker in settlement_markers
        )

    @staticmethod
    def _claim_recharge_settlement(db: Session, order: PaymentRechargeOrder) -> PaymentRechargeSettlement | None:
        asset_type = PaymentService._settlement_asset_type(order)
        existing = (
            db.query(PaymentRechargeSettlement)
            .filter(
                PaymentRechargeSettlement.order_no == order.order_no,
                PaymentRechargeSettlement.asset_type == asset_type,
            )
            .first()
        )
        if existing:
            logger.warning("Skip duplicate recharge settlement for order %s asset %s", order.order_no, asset_type)
            return None

        settlement = PaymentRechargeSettlement(
            order_id=order.id,
            order_no=order.order_no,
            asset_type=asset_type,
            user_id=order.user_id,
            agent_id=order.agent_id,
            amount_cny=order.amount_cny,
            credited_usd=order.credited_usd,
            credited_image_credits=order.credited_image_credits,
            status="settling",
        )
        try:
            with db.begin_nested():
                db.add(settlement)
                db.flush()
        except IntegrityError as exc:
            if not PaymentService._is_duplicate_settlement_integrity_error(exc):
                raise
            logger.warning("Skip duplicate recharge settlement after unique-key conflict for order %s asset %s", order.order_no, asset_type)
            return None
        return settlement

    @staticmethod
    def _validate_paid_payload(db: Session, locked: PaymentRechargeOrder, payload: dict, source: str) -> dict:
        channel = PaymentService._normalize_payment_channel(locked.payment_channel)
        local_amount = PaymentService._normalize_cny(locked.amount_cny)
        if channel == "alipay":
            app_id = str(payload.get("app_id") or settings.ALIPAY_APP_ID or "").strip()
            if app_id and app_id != str(settings.ALIPAY_APP_ID or "").strip():
                raise ServiceException(400, "支付宝应用编号不匹配", "ALIPAY_APP_ID_MISMATCH")
            trade_status = str(payload.get("trade_status") or "").strip()
            if trade_status not in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES:
                raise ServiceException(400, "支付宝交易状态不支持入账", "ALIPAY_TRADE_STATUS_INVALID")
            total_amount = payload.get("total_amount")
            if total_amount is not None:
                remote_amount = PaymentService._normalize_cny(total_amount) if source == "notify" else PaymentService._try_normalize_cny(total_amount)
                if remote_amount is not None and remote_amount > Decimal("0") and remote_amount != local_amount:
                    raise ServiceException(400, "支付宝回调金额与本地订单不一致", "ALIPAY_AMOUNT_MISMATCH")
            alipay_trade_no = str(payload.get("alipay_trade_no") or payload.get("trade_no") or "").strip() or None
            if alipay_trade_no:
                exists = (
                    db.query(PaymentRechargeOrder)
                    .filter(
                        PaymentRechargeOrder.alipay_trade_no == alipay_trade_no,
                        PaymentRechargeOrder.order_no != locked.order_no,
                    )
                    .first()
                )
                if exists:
                    raise ServiceException(400, "支付宝交易号已被其他订单占用", "ALIPAY_TRADE_NO_CONFLICT")
            return {
                "trade_status": trade_status,
                "alipay_trade_no": alipay_trade_no,
                "buyer_logon_id": str(payload.get("buyer_logon_id") or locked.buyer_logon_id or ""),
                "buyer_user_id": str(payload.get("buyer_user_id") or locked.buyer_user_id or ""),
            }

        app_id = str(payload.get("appid") or "").strip()
        if app_id and app_id != str(settings.WECHAT_PAY_APP_ID or "").strip():
            raise ServiceException(400, "微信支付应用编号不匹配", "WECHAT_PAY_APP_ID_MISMATCH")
        mch_id = str(payload.get("mchid") or "").strip()
        if mch_id and mch_id != str(settings.WECHAT_PAY_MCH_ID or "").strip():
            raise ServiceException(400, "微信支付商户号不匹配", "WECHAT_PAY_MCH_ID_MISMATCH")
        trade_state = str(payload.get("trade_state") or payload.get("trade_state_desc") or "SUCCESS").strip().upper()
        if trade_state not in PaymentService.WECHAT_SUCCESS_STATES:
            raise ServiceException(400, "微信支付交易状态不支持入账", "WECHAT_PAY_TRADE_STATE_INVALID")
        amount_data = payload.get("amount")
        if not isinstance(amount_data, dict) or not amount_data:
            raise ServiceException(400, "微信支付回调金额格式无效", "WECHAT_PAY_AMOUNT_MISMATCH")
        # WeChat discounts reduce payer_total, while total remains the merchant order amount.
        total_amount = amount_data.get("total")
        if total_amount is None:
            total_amount = amount_data.get("payer_total")
        if total_amount is None:
            raise ServiceException(400, "微信支付回调金额格式无效", "WECHAT_PAY_AMOUNT_MISMATCH")
        try:
            remote_amount = (Decimal(str(total_amount)) / Decimal("100")).quantize(PaymentService.CNY_SCALE, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ServiceException(400, "微信支付回调金额格式无效", "WECHAT_PAY_AMOUNT_MISMATCH") from exc
        if remote_amount != local_amount:
            raise ServiceException(400, "微信支付回调金额与本地订单不一致", "WECHAT_PAY_AMOUNT_MISMATCH")
        transaction_id = str(payload.get("transaction_id") or "").strip() or None
        if transaction_id:
            exists = (
                db.query(PaymentRechargeOrder)
                .filter(
                    PaymentRechargeOrder.wechat_transaction_id == transaction_id,
                    PaymentRechargeOrder.order_no != locked.order_no,
                )
                .first()
            )
            if exists:
                raise ServiceException(400, "微信支付流水号已被其他订单占用", "WECHAT_PAY_TRANSACTION_ID_CONFLICT")
        return {
            "trade_status": trade_state,
            "wechat_transaction_id": transaction_id,
        }

    @staticmethod
    def _credit_agent_cash_balance(db: Session, order: PaymentRechargeOrder) -> None:
        if not order.agent_id:
            return
        income = PaymentService._try_normalize_cny(order.agent_income_cny)
        if income is None:
            raise ServiceException(500, "代理现金分润金额格式无效", "AGENT_CASH_INCOME_INVALID")
        if income <= Decimal("0"):
            return
        action_type = (
            "image_credit_recharge_commission"
            if PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None)) == "image_credit"
            else "balance_recharge_commission"
        )
        existing_ledger = (
            db.query(AgentCashLedger.id)
            .filter(
                AgentCashLedger.order_id == order.id,
                AgentCashLedger.action_type == action_type,
            )
            .first()
        )
        if existing_ledger:
            logger.warning("Skip duplicate agent cash recharge commission for order %s", order.order_no)
            return

        balance = PaymentService._get_or_create_agent_cash_balance_for_update(db, int(order.agent_id))
        balance_before = Decimal(str(balance.balance or 0))
        balance.balance = balance_before + income
        balance.total_income = Decimal(str(balance.total_income or 0)) + income
        db.add(AgentCashLedger(
            agent_id=int(order.agent_id),
            order_id=order.id,
            withdrawal_id=None,
            action_type=action_type,
            change_amount=income,
            balance_before=balance_before,
            balance_after=balance.balance,
            operator_user_id=None,
            remark=f"用户在线{PaymentService._recharge_type_text(getattr(order, 'recharge_type', None))}充值分润，订单 {order.order_no}",
        ))

    @staticmethod
    def _apply_paid_order(db: Session, order_no: str, payload: dict, source: str = "notify") -> dict:
        locked = PaymentService._get_order_for_update(db, order_no)
        if locked.status == "paid":
            return PaymentService.serialize_order(locked)
        if locked.status != "pending":
            raise ServiceException(400, "订单状态不允许再次入账", "RECHARGE_ORDER_STATUS_INVALID")
        validated = PaymentService._validate_paid_payload(db, locked, payload, source)
        settlement = PaymentService._claim_recharge_settlement(db, locked)
        is_new_settlement = settlement is not None

        if is_new_settlement:
            PaymentService._credit_user_order_asset(db, locked)
            PaymentService._credit_agent_cash_balance(db, locked)
            settlement.status = "applied"
            settlement.applied_at = datetime.utcnow()

        locked.status = "paid"
        if is_new_settlement or not locked.trade_status:
            locked.trade_status = str(validated.get("trade_status") or "")
        if locked.payment_channel == "alipay":
            if is_new_settlement or not locked.alipay_trade_no:
                locked.alipay_trade_no = validated.get("alipay_trade_no")
            if is_new_settlement or not locked.buyer_logon_id:
                locked.buyer_logon_id = str(validated.get("buyer_logon_id") or locked.buyer_logon_id or "")
            if is_new_settlement or not locked.buyer_user_id:
                locked.buyer_user_id = str(validated.get("buyer_user_id") or locked.buyer_user_id or "")
        elif locked.payment_channel == "wechat":
            if is_new_settlement or not locked.wechat_transaction_id:
                locked.wechat_transaction_id = validated.get("wechat_transaction_id")
        if is_new_settlement or not locked.paid_at:
            locked.paid_at = datetime.utcnow()
        if source == "notify" and (is_new_settlement or not locked.notify_raw):
            locked.notify_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        elif source != "notify" and (is_new_settlement or not locked.return_raw):
            locked.return_raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        db.commit()
        db.refresh(locked)
        return PaymentService.serialize_order(locked)

    @staticmethod
    def _mark_order_terminal(db: Session, order_no: str, status: str, trade_status: str, payload: dict | None = None, source: str = "query") -> dict:
        locked = PaymentService._get_order_for_update(db, order_no)
        if locked.status == "paid":
            return PaymentService.serialize_order(locked)
        if locked.status not in {"pending", status}:
            raise ServiceException(400, "订单状态不允许更新", "RECHARGE_ORDER_STATUS_INVALID")
        locked.status = status
        locked.trade_status = trade_status
        if status == "closed":
            locked.closed_at = datetime.utcnow()
        raw_text = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        if source == "notify":
            locked.notify_raw = raw_text
        else:
            locked.return_raw = raw_text
        db.commit()
        db.refresh(locked)
        return PaymentService.serialize_order(locked)

    @staticmethod
    def handle_alipay_notify(db: Session, form_data: dict[str, str]) -> bool:
        PaymentService._validate_alipay_config()
        params = {str(key): str(value) for key, value in form_data.items()}
        PaymentService._verify_alipay_signature(params)
        order_no = str(params.get("out_trade_no") or "").strip()
        if not order_no:
            raise ServiceException(400, "缺少订单号", "RECHARGE_ORDER_NO_MISSING")

        trade_status = str(params.get("trade_status") or "").strip()
        if trade_status in PaymentService.ALIPAY_ACCEPTED_TRADE_STATUSES:
            PaymentService._apply_paid_order(db, order_no, {
                "app_id": params.get("app_id"),
                "trade_status": trade_status,
                "total_amount": params.get("total_amount"),
                "alipay_trade_no": params.get("trade_no"),
                "buyer_logon_id": params.get("buyer_logon_id"),
                "buyer_user_id": params.get("buyer_user_id"),
                "notify_id": params.get("notify_id"),
                "raw": params,
            }, source="notify")
            return True

        if trade_status == "TRADE_CLOSED":
            PaymentService._mark_order_terminal(db, order_no, "closed", trade_status, payload=params, source="notify")
            return True
        return True

    @staticmethod
    def handle_wechat_notify(db: Session, headers: dict[str, str], body: str) -> bool:
        PaymentService._validate_wechat_config()
        PaymentService._verify_wechat_notify_signature(headers, body)
        try:
            payload = json.loads(body or "{}")
        except ValueError as exc:
            raise ServiceException(400, "微信支付通知报文格式无效", "WECHAT_PAY_NOTIFY_JSON_INVALID") from exc
        resource = payload.get("resource") or {}
        resource_data = PaymentService._decrypt_wechat_resource(resource)
        order_no = str(resource_data.get("out_trade_no") or "").strip()
        if not order_no:
            raise ServiceException(400, "缺少订单号", "RECHARGE_ORDER_NO_MISSING")
        trade_state = str(resource_data.get("trade_state") or "").strip().upper()
        if trade_state in PaymentService.WECHAT_SUCCESS_STATES:
            PaymentService._apply_paid_order(db, order_no, resource_data, source="notify")
            return True
        if trade_state in PaymentService.WECHAT_CLOSED_STATES:
            PaymentService._mark_order_terminal(db, order_no, "closed", trade_state, payload=resource_data, source="notify")
            return True
        if trade_state in PaymentService.WECHAT_FAILED_STATES:
            PaymentService._mark_order_terminal(db, order_no, "failed", trade_state, payload=resource_data, source="notify")
            return True
        return True

    @staticmethod
    def handle_alipay_return(db: Session, query_params: dict[str, str]) -> str:
        order_no = str(query_params.get("out_trade_no") or query_params.get("order_no") or "").strip()
        if not order_no:
            raise ServiceException(400, "缺少订单号", "RECHARGE_ORDER_NO_MISSING")
        order = db.query(PaymentRechargeOrder).filter(PaymentRechargeOrder.order_no == order_no).first()
        if not order:
            raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")

        order.return_raw = json.dumps({str(key): str(value) for key, value in query_params.items()}, ensure_ascii=False, sort_keys=True)
        db.commit()
        return PaymentService._append_query(
            order.return_url_snapshot or PaymentService.build_order_return_url(order),
            {"trade_status": str(query_params.get("trade_status") or ""), "order_no": order.order_no},
        )

    @staticmethod
    def serialize_order(order: PaymentRechargeOrder) -> dict:
        channel_trade_no = order.alipay_trade_no if order.payment_channel == "alipay" else order.wechat_transaction_id
        return {
            "id": order.id,
            "order_no": order.order_no,
            "payment_channel": order.payment_channel,
            "recharge_type": PaymentService._normalize_recharge_type(getattr(order, "recharge_type", None)),
            "recharge_type_text": PaymentService._recharge_type_text(getattr(order, "recharge_type", None)),
            "user_id": order.user_id,
            "agent_id": order.agent_id,
            "site_scope": order.site_scope,
            "source_host": order.source_host,
            "amount_cny": float(order.amount_cny or 0),
            "credited_usd": float(order.credited_usd or 0),
            "credited_image_credits": float(order.credited_image_credits or 0),
            "agent_income_cny": float(order.agent_income_cny or 0),
            "status": order.status,
            "trade_status": order.trade_status,
            "payment_channel_text": PaymentService._payment_channel_text(order.payment_channel),
            "subject": order.subject,
            "return_url_snapshot": order.return_url_snapshot,
            "alipay_trade_no": order.alipay_trade_no,
            "wechat_transaction_id": order.wechat_transaction_id,
            "wechat_code_url": order.wechat_code_url,
            "channel_trade_no": channel_trade_no,
            "paid_at": PaymentService._serialize_dt(order.paid_at, assume_utc=True),
            "expired_at": PaymentService._serialize_dt(order.expired_at, assume_utc=True),
            "closed_at": PaymentService._serialize_dt(order.closed_at, assume_utc=True),
            "created_at": PaymentService._serialize_dt(order.created_at, assume_utc=False),
            "updated_at": PaymentService._serialize_dt(order.updated_at, assume_utc=False),
        }
