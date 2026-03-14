from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import LoginRequest, RegisterRequest
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=ResponseModel)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    result = AuthService.register(
        db,
        username=req.username,
        email=req.email,
        password=req.password,
    )
    return ResponseModel(data=result)


@router.post("/login", response_model=ResponseModel)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else None
    result = AuthService.login(db, username=req.username, password=req.password, client_ip=client_ip)
    return ResponseModel(data=result)
