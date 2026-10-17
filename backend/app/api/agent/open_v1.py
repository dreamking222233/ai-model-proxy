"""Public, agent-key-authenticated APIs used by agent integrations."""
from __future__ import annotations

import ipaddress
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.dependencies import (
    OpenApiUserPrincipal,
    get_agent_open_api_principal,
    get_open_api_user,
    require_open_api_user_for_agent,
)
from app.core.exceptions import ServiceException
from app.database import SessionLocal, get_db
from app.models.log import UserBalance
from app.services.agent_cash_service import AgentCashService
from app.services.log_service import LogService
from app.schemas.common import ResponseModel
from app.schemas.agent_open_api import OpenApiEmailCodeRequest, OpenApiRechargeOrderRequest
from app.schemas.user import ApiKeyCreateRequest, RegisterRequest, LoginRequest
from app.services.agent_open_api_key_service import AgentOpenApiPrincipal, AgentOpenApiKeyService
from app.services.agent_open_api_service import AgentOpenApiService
from app.services.agent_service import AgentService
from app.services.api_key_service import ApiKeyService
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService

router = APIRouter(prefix="/api/agent/open/v1", tags=["代理开放接口"])


def _require_scope(principal: AgentOpenApiPrincipal, scope: str) -> None:
    if scope not in principal.scopes:
        raise ServiceException(403, "API Key 未开通此接口权限", "OPEN_API_SCOPE_REQUIRED")


def _client_ip(request: Request) -> str:
    peer_host = request.client.host if request.client else ""
    try:
        peer_ip = ipaddress.ip_address(peer_host)
    except ValueError:
        peer_ip = None
    if peer_ip and (peer_ip.is_loopback or peer_ip.is_private):
        real_ip = str(request.headers.get("X-Real-IP") or "").strip()
        if real_ip:
            try:
                return str(ipaddress.ip_address(real_ip))
            except ValueError:
                pass
    return peer_host or "unknown"


def _rate_limit(action: str, request: Request, principal: AgentOpenApiPrincipal, subject: str, limit: int, window: int) -> None:
    key = AuthRateLimitService.build_key(
        f"agent-open-{action}-key-{principal.key_id}",
        _client_ip(request),
        subject,
    )
    AuthRateLimitService.check(key, limit=limit, window_seconds=window)


@router.post("/auth/email-code", response_model=ResponseModel)
def send_open_api_email_code(
    data: OpenApiEmailCodeRequest,
    request: Request,
    response: Response,
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
):
    _require_scope(principal, "auth.register")
    email = str(data.email)
    _rate_limit("email-code", request, principal, email.lower(), 5, 3600)
    db = SessionLocal()
    try:
        AgentService.get_open_api_site_context(db, principal.agent_id, require_register=True)
    finally:
        db.close()
    EmailVerificationService.send_code(email, purpose="register", agent_id=principal.agent_id)
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(message="验证码已发送")


@router.post("/auth/register", response_model=ResponseModel)
def open_api_register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
):
    _require_scope(principal, "auth.register")
    _rate_limit("register", request, principal, f"{data.username}:{data.email}", 10, 3600)
    result = AuthService.register(
        db,
        username=data.username,
        email=str(data.email),
        password=data.password,
        email_code=data.email_code,
        invite_code=data.invite_code,
        trusted_agent_id=principal.agent_id,
    )
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=result)


@router.post("/auth/login", response_model=ResponseModel)
def open_api_login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
):
    _require_scope(principal, "auth.login")
    _rate_limit("login", request, principal, data.username, 20, 60)
    result = AuthService.login(
        db,
        username=data.username,
        password=data.password,
        client_ip=_client_ip(request),
        trusted_agent_id=principal.agent_id,
    )
    balance = db.query(UserBalance.balance).filter(UserBalance.user_id == int(result["user"]["id"])).scalar()
    result["balance"] = float(balance or 0)
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=result)


@router.get("/user/api-keys/group-options", response_model=ResponseModel)
def open_api_user_api_key_group_options(
    response: Response,
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
    user: OpenApiUserPrincipal = Depends(get_open_api_user),
):
    _require_scope(principal, "user.api_key.create")
    require_open_api_user_for_agent(user, principal)
    return ResponseModel(data=ApiKeyService.get_group_options(db))


@router.post("/user/api-keys", response_model=ResponseModel)
def open_api_create_user_api_key(
    data: ApiKeyCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
    user: OpenApiUserPrincipal = Depends(get_open_api_user),
):
    _require_scope(principal, "user.api_key.create")
    require_open_api_user_for_agent(user, principal)
    result = ApiKeyService.create_api_key(
        db,
        user.user_id,
        data.name,
        data.group_mode,
        data.group_model_series,
        data.group_id,
        data.daily_limit_usd,
    )
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=result)


@router.post("/users/recharge-orders", response_model=ResponseModel)
def open_api_create_recharge_order(
    data: OpenApiRechargeOrderRequest,
    request: Request,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
    user: OpenApiUserPrincipal = Depends(get_open_api_user),
):
    _require_scope(principal, "user.recharge")
    require_open_api_user_for_agent(user, principal)
    result = AgentOpenApiService.create_recharge_order(
        principal=principal,
        user_id=user.user_id,
        amount_cny=data.amount_cny,
        payment_channel=data.payment_channel,
        recharge_rate_code=data.recharge_rate_code,
        idempotency_key=idempotency_key,
        request_ip=_client_ip(request),
    )
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=result, message="充值订单已创建")


@router.post("/users/recharge-orders/{order_no}/wait", response_model=ResponseModel)
async def open_api_wait_recharge_order(
    order_no: str,
    request: Request,
    response: Response,
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
    user: OpenApiUserPrincipal = Depends(get_open_api_user),
):
    _require_scope(principal, "user.recharge")
    require_open_api_user_for_agent(user, principal)
    if not order_no or len(order_no) > 64:
        raise ServiceException(404, "充值订单不存在", "RECHARGE_ORDER_NOT_FOUND")
    result = await AgentOpenApiService.wait_for_recharge(
        principal=principal,
        user_id=user.user_id,
        order_no=order_no,
        request_ip=_client_ip(request),
        deadline=(
            float(request.state.request_started_monotonic) + AgentOpenApiService.WAIT_SECONDS
            if getattr(request.state, "request_started_monotonic", None) is not None
            else None
        ),
    )
    response.headers["Cache-Control"] = "no-store"
    return ResponseModel(data=result)


@router.get("/agent/requests/{request_id}", response_model=ResponseModel)
def get_open_api_request_detail(
    request_id: UUID,
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
):
    _require_scope(principal, "agent.request_detail")
    detail = LogService.get_agent_request_detail(db, str(request_id), int(principal.agent_id))
    if detail is None:
        raise ServiceException(404, "请求记录不存在", "REQUEST_LOG_NOT_FOUND")
    return ResponseModel(data=detail)


@router.get("/agent/payments", response_model=ResponseModel)
def list_open_api_agent_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None, gt=0),
    status: str | None = Query(None, pattern=r"^(pending|paid|closed|failed)$"),
    payment_channel: str | None = Query(None, pattern=r"^(alipay|wechat)$"),
    recharge_type: str | None = Query(None, pattern=r"^(balance|image_credit|subscription)$"),
    start_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    principal: AgentOpenApiPrincipal = Depends(get_agent_open_api_principal),
):
    _require_scope(principal, "agent.recharge_records")
    items, total = AgentCashService.list_agent_open_api_recharge_orders(
        db,
        agent_id=int(principal.agent_id),
        page=page,
        page_size=page_size,
        user_id=user_id,
        status=status,
        payment_channel=payment_channel,
        recharge_type=recharge_type,
        start_date=start_date,
        end_date=end_date,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
