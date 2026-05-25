import ipaddress

from fastapi import APIRouter, Depends, Header, Request
from jose import JWTError
from sqlalchemy.orm import Session
from app.config import settings
from app.core.security import verify_token
from app.database import get_db
from app.services.auth_service import AuthService
from app.services.auth_rate_limit_service import AuthRateLimitService
from app.services.auth_token_revocation_service import AuthTokenRevocationService
from app.services.email_verification_service import EmailVerificationService
from app.schemas.user import EmailCodeRequest, ForgotPasswordRequest, ForgotPasswordVerifyRequest, LoginRequest, RegisterRequest
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/auth", tags=["认证"])


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


def _limit(request: Request, action: str, subject: str, limit: int, window_seconds: int) -> None:
    key = AuthRateLimitService.build_key(action, _client_ip(request), subject)
    AuthRateLimitService.check(key, limit=limit, window_seconds=window_seconds)


@router.post("/email-code", response_model=ResponseModel)
def send_email_code(req: EmailCodeRequest, request: Request, db: Session = Depends(get_db)):
    _limit(
        request,
        "email-code",
        str(req.email),
        settings.AUTH_EMAIL_CODE_RATE_LIMIT_PER_HOUR,
        3600,
    )
    if req.purpose == "password_reset":
        AuthService.verify_password_reset_identity(
            db,
            username=req.username or "",
            email=str(req.email),
            request_host=request.headers.get("host"),
            x_site_host=request.headers.get("X-Site-Host"),
            origin=request.headers.get("Origin"),
            referer=request.headers.get("Referer"),
        )
    EmailVerificationService.send_code(str(req.email), purpose=req.purpose)
    return ResponseModel(message="验证码已发送")


@router.post("/logout", response_model=ResponseModel)
def logout(authorization: str = Header(None, alias="Authorization")):
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = verify_token(authorization[7:])
            AuthTokenRevocationService.revoke(payload.get("jti"), payload.get("exp"))
        except JWTError:
            pass
    return ResponseModel(message="已退出登录")


@router.post("/register", response_model=ResponseModel)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _limit(
        request,
        "register",
        f"{req.username}:{req.email}",
        settings.AUTH_REGISTER_RATE_LIMIT_PER_HOUR,
        3600,
    )
    result = AuthService.register(
        db,
        username=req.username,
        email=req.email,
        password=req.password,
        email_code=req.email_code,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(data=result)


@router.post("/login", response_model=ResponseModel)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = _client_ip(request)
    _limit(
        request,
        "login",
        req.username,
        settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE,
        60,
    )
    result = AuthService.login(
        db,
        username=req.username,
        password=req.password,
        client_ip=client_ip,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(data=result)


@router.post("/forgot-password", response_model=ResponseModel)
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    _limit(
        request,
        "forgot-password",
        f"{req.username}:{req.email}",
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_PER_HOUR,
        3600,
    )
    AuthService.reset_password_by_identity(
        db,
        username=req.username,
        email=req.email,
        email_code=req.email_code,
        new_password=req.new_password,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(message="密码重置成功")


@router.post("/forgot-password/verify", response_model=ResponseModel)
def verify_forgot_password(req: ForgotPasswordVerifyRequest, request: Request, db: Session = Depends(get_db)):
    _limit(
        request,
        "forgot-password-verify",
        f"{req.username}:{req.email}",
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_PER_HOUR,
        3600,
    )
    AuthService.verify_password_reset_identity(
        db,
        username=req.username,
        email=req.email,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(message="身份校验通过")
