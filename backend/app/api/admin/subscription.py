"""Admin API for subscription management."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.subscription_service import SubscriptionService
from app.schemas.common import ResponseModel, PageResponse


class ActivateSubscriptionRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")
    plan_name: str = Field(..., min_length=1, max_length=64, description="套餐名称")
    plan_type: str = Field(..., description="套餐类型: monthly/quarterly/yearly/custom")
    duration_days: int = Field(..., gt=0, description="套餐时长（天）")


router = APIRouter(prefix="/api/admin/subscription", tags=["管理员-套餐管理"])


@router.post("/activate", response_model=ResponseModel)
def activate_subscription(
    data: ActivateSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """为用户开通/续费时间套餐"""
    result = SubscriptionService.activate_subscription(
        db,
        user_id=data.user_id,
        plan_name=data.plan_name,
        plan_type=data.plan_type,
        duration_days=data.duration_days,
        operator_id=current_user.id,
    )
    return ResponseModel(data=result, message="套餐开通成功")


@router.post("/cancel/{user_id}", response_model=ResponseModel)
def cancel_subscription(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """取消用户套餐，切换为按量计费模式"""
    result = SubscriptionService.cancel_subscription(db, user_id)
    return ResponseModel(data=result, message="套餐已取消")


@router.get("/user/{user_id}", response_model=ResponseModel)
def get_user_subscriptions(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """查询指定用户的套餐记录"""
    records, total = SubscriptionService.get_user_subscriptions(db, user_id, page, page_size)
    return ResponseModel(
        data=PageResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/list", response_model=ResponseModel)
def list_all_subscriptions(
    status: str = Query(None, description="状态筛选: active/expired/cancelled"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """查询所有用户的套餐记录"""
    records, total = SubscriptionService.list_all_subscriptions(db, status, page, page_size)
    return ResponseModel(
        data=PageResponse(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/check-expired", response_model=ResponseModel)
def check_expired_subscriptions(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """手动触发过期套餐检查（通常由定时任务调用）"""
    count = SubscriptionService.check_and_expire_subscriptions(db)
    return ResponseModel(data={"expired_count": count}, message=f"已处理 {count} 个过期套餐")
