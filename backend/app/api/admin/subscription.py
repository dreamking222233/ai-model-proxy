"""Admin API for subscription management."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.subscription_service import SubscriptionService
from app.schemas.common import ResponseModel


class ActivateSubscriptionRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")
    plan_name: str = Field(..., min_length=1, max_length=64, description="套餐名称")
    plan_type: str = Field(..., description="套餐类型: monthly/quarterly/yearly/custom")
    duration_days: int = Field(..., gt=0, description="套餐时长（天）")


class SubscriptionPlanRequest(BaseModel):
    plan_code: str = Field(..., min_length=2, max_length=64, description="套餐编码")
    plan_name: str = Field(..., min_length=1, max_length=64, description="套餐名称")
    plan_kind: str = Field(..., description="套餐模式: unlimited/daily_quota")
    duration_mode: str = Field("custom", description="时长模式")
    duration_days: int = Field(..., gt=0, description="套餐时长（天）")
    quota_metric: Optional[str] = Field(None, description="限额口径: total_tokens/cost_usd")
    quota_value: Optional[float] = Field(None, description="每日额度值")
    reset_period: Optional[str] = Field("day", description="刷新周期")
    reset_timezone: Optional[str] = Field("Asia/Shanghai", description="刷新时区")
    sort_order: Optional[int] = Field(0, description="排序")
    status: Optional[str] = Field("active", description="状态")
    description: Optional[str] = Field(None, max_length=255, description="描述")


class ActivatePlanSubscriptionRequest(BaseModel):
    user_id: int = Field(..., description="用户ID")
    plan_id: int = Field(..., description="套餐模板ID")
    activation_mode: str = Field("append", description="生效方式: append/override")


router = APIRouter(prefix="/api/admin/subscription", tags=["管理员-套餐管理"])


def _build_page_payload(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "list": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


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


@router.get("/plans", response_model=ResponseModel)
def list_subscription_plans(
    status: str = Query(None, description="状态筛选: active/inactive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = SubscriptionService.list_plans(db, status, page, page_size)
    return ResponseModel(data=_build_page_payload(items, total, page, page_size))


@router.post("/plans", response_model=ResponseModel)
def create_subscription_plan(
    data: SubscriptionPlanRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = SubscriptionService.create_plan(db, data.model_dump())
    return ResponseModel(data=result, message="套餐模板创建成功")


@router.put("/plans/{plan_id}", response_model=ResponseModel)
def update_subscription_plan(
    plan_id: int,
    data: SubscriptionPlanRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = SubscriptionService.update_plan(db, plan_id, data.model_dump())
    return ResponseModel(data=result, message="套餐模板更新成功")


@router.post("/activate-plan", response_model=ResponseModel)
def activate_plan_subscription(
    data: ActivatePlanSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    result = SubscriptionService.activate_plan_subscription(
        db,
        user_id=data.user_id,
        plan_id=data.plan_id,
        operator_id=current_user.id,
        activation_mode=data.activation_mode,
    )
    return ResponseModel(data=result, message="套餐发放成功")


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
    return ResponseModel(data=_build_page_payload(records, total, page, page_size))


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
    return ResponseModel(data=_build_page_payload(records, total, page, page_size))


@router.get("/{subscription_id}/usage", response_model=ResponseModel)
def get_subscription_usage_detail(
    subscription_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """查询单条套餐记录对应的使用明细"""
    result = SubscriptionService.get_subscription_usage_detail(
        db,
        subscription_id=subscription_id,
        page=page,
        page_size=page_size,
    )
    return ResponseModel(data=result)


@router.post("/check-expired", response_model=ResponseModel)
def check_expired_subscriptions(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """手动触发过期套餐检查（通常由定时任务调用）"""
    count = SubscriptionService.check_and_expire_subscriptions(db)
    return ResponseModel(data={"expired_count": count}, message=f"已处理 {count} 个过期套餐")
