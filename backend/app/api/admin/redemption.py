"""Admin API for managing redemption codes."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import SysUser
from app.services.redemption_service import RedemptionService
from app.schemas.common import ResponseModel
from pydantic import BaseModel, Field


class CreateCodeRequest(BaseModel):
    amount: float = Field(..., gt=0, description="兑换金额")
    expires_days: Optional[int] = Field(None, ge=1, le=365, description="有效期天数")


class BatchCreateCodeRequest(BaseModel):
    amount: float = Field(..., gt=0, description="兑换金额")
    count: int = Field(..., ge=1, le=1000, description="生成数量")
    expires_days: Optional[int] = Field(None, ge=1, le=365, description="有效期天数")


router = APIRouter(prefix="/api/admin/redemption", tags=["管理员-兑换码"])


@router.post("", response_model=ResponseModel, dependencies=[Depends(require_admin)])
def create_code(
    data: CreateCodeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """创建单个兑换码"""
    code = RedemptionService.create_redemption_code(
        db, current_user.id, data.amount, data.expires_days
    )
    return ResponseModel(data=code, message="兑换码创建成功")


@router.post("/batch", response_model=ResponseModel, dependencies=[Depends(require_admin)])
def batch_create_codes(
    data: BatchCreateCodeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """批量创建兑换码"""
    codes = RedemptionService.batch_create_codes(
        db, current_user.id, data.amount, data.count, data.expires_days
    )
    return ResponseModel(data=codes, message=f"成功生成 {len(codes)} 个兑换码")


@router.get("", response_model=ResponseModel, dependencies=[Depends(require_admin)])
def list_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    """查询兑换码列表"""
    items, total = RedemptionService.list_codes(db, page, page_size, status)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.delete("/{code_id}", response_model=ResponseModel, dependencies=[Depends(require_admin)])
def delete_code(
    code_id: int,
    db: Session = Depends(get_db),
):
    """删除兑换码（仅未使用的）"""
    RedemptionService.delete_code(db, code_id)
    return ResponseModel(message="兑换码删除成功")
