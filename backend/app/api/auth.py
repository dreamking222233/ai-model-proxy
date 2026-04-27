from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import ForgotPasswordRequest, ForgotPasswordVerifyRequest, LoginRequest, RegisterRequest
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=ResponseModel)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    result = AuthService.register(
        db,
        username=req.username,
        email=req.email,
        password=req.password,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(data=result)


@router.post("/login", response_model=ResponseModel)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
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
    AuthService.reset_password_by_identity(
        db,
        username=req.username,
        email=req.email,
        new_password=req.new_password,
        request_host=request.headers.get("host"),
        x_site_host=request.headers.get("X-Site-Host"),
        origin=request.headers.get("Origin"),
        referer=request.headers.get("Referer"),
    )
    return ResponseModel(message="密码重置成功")


@router.post("/forgot-password/verify", response_model=ResponseModel)
def verify_forgot_password(req: ForgotPasswordVerifyRequest, request: Request, db: Session = Depends(get_db)):
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
