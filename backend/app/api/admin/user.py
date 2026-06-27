from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.auth_service import AuthService
from app.services.balance_service import BalanceService
from app.services.image_credit_service import ImageCreditService
from app.services.log_service import LogService
from app.schemas.user import (
 UserUpdate,
 BalanceRechargeRequest,
 BalanceDeductRequest,
 ImageCreditRechargeRequest,
 ImageCreditDeductRequest,
)
from app.schemas.model import UserPriceAdjustmentRuleCreate, UserPriceAdjustmentRuleUpdate
from app.schemas.common import ResponseModel
from app.services.price_adjustment_service import PriceAdjustmentService

router = APIRouter(prefix="/api/admin/users", tags=["管理-用户管理"])


@router.get("", response_model=ResponseModel)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    roles: str = Query(None),
    sort_by: str = Query("id"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    role_list = [item.strip() for item in str(roles or "").split(",") if item.strip()] or None
    items, total = AuthService.list_users(db, page, page_size, keyword, sort_by, sort_order, roles=role_list)
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{user_id}/price-adjustments", response_model=ResponseModel)
def list_user_price_adjustment_rules(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    model_series: str = Query(None),
    model_type: str = Query(None),
    enabled: int = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    items, total = PriceAdjustmentService.list_user_rules(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        model_series=model_series,
        model_type=model_type,
        enabled=enabled,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{user_id}/price-adjustments/effective", response_model=ResponseModel)
def get_user_effective_price_adjustments(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    return ResponseModel(data=PriceAdjustmentService.list_user_effective_matrix(db, user_id))


@router.post("/{user_id}/price-adjustments", response_model=ResponseModel)
def create_user_price_adjustment_rule(
    user_id: int,
    data: UserPriceAdjustmentRuleCreate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    rule = PriceAdjustmentService.create_user_rule(db, user_id, data, current_user.id)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "create_user_price_adjustment", "user_price_adjustment_rule", rule.get("id"),
        f"Created user price adjustment for user {user_id}: {rule.get('model_series')}/{rule.get('model_type')} x{rule.get('multiplier')}",
        None,
    )
    return ResponseModel(data=rule, message="用户专属倍率规则已创建")


@router.put("/{user_id}/price-adjustments/{rule_id}", response_model=ResponseModel)
def update_user_price_adjustment_rule(
    user_id: int,
    rule_id: int,
    data: UserPriceAdjustmentRuleUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    rule = PriceAdjustmentService.update_user_rule(db, user_id, rule_id, data, current_user.id)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "update_user_price_adjustment", "user_price_adjustment_rule", rule_id,
        f"Updated user price adjustment for user {user_id}: {rule.get('model_series')}/{rule.get('model_type')} x{rule.get('multiplier')}, enabled={rule.get('enabled')}",
        None,
    )
    return ResponseModel(data=rule, message="用户专属倍率规则已保存")


@router.delete("/{user_id}/price-adjustments/{rule_id}", response_model=ResponseModel)
def delete_user_price_adjustment_rule(
    user_id: int,
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    PriceAdjustmentService.delete_user_rule(db, user_id, rule_id)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "delete_user_price_adjustment", "user_price_adjustment_rule", rule_id,
        f"Deleted user price adjustment {rule_id} for user {user_id}",
        None,
    )
    return ResponseModel(message="用户专属倍率规则已删除")


@router.get("/{user_id}", response_model=ResponseModel)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.get_user_detail(db, user_id)
    return ResponseModel(data=user)


@router.put("/{user_id}", response_model=ResponseModel)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.update_user(db, user_id, data)
    return ResponseModel(data=user)


@router.put("/{user_id}/status", response_model=ResponseModel)
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    user = AuthService.toggle_user_status(db, user_id)
    return ResponseModel(data={"id": user.id, "status": user.status})


@router.delete("/{user_id}", response_model=ResponseModel)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    AuthService.delete_user(db, user_id, current_user.id)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "delete", "user", user_id,
        f"Deleted user {user_id}",
        None,
    )
    return ResponseModel(message="User deleted")


@router.post("/recharge", response_model=ResponseModel)
def recharge_balance(
    data: BalanceRechargeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    balance = BalanceService.recharge(db, data.user_id, data.amount, current_user.id, data.reason)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "recharge", "user_balance", data.user_id,
        f"Recharged {data.amount} for user {data.user_id}" + (f": {data.reason}" if data.reason else ""),
        None,
    )
    return ResponseModel(data=balance)


@router.post("/deduct", response_model=ResponseModel)
def deduct_balance(
    data: BalanceDeductRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    balance = BalanceService.deduct(db, data.user_id, data.amount, current_user.id, data.reason)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "deduct", "user_balance", data.user_id,
        f"Deducted {data.amount} from user {data.user_id}" + (f": {data.reason}" if data.reason else ""),
        None,
    )
    return ResponseModel(data=balance)


@router.post("/image-credits/recharge", response_model=ResponseModel)
def recharge_image_credits(
    data: ImageCreditRechargeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    balance = ImageCreditService.recharge(db, data.user_id, data.amount, current_user.id, data.reason)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "image_credit_recharge", "user_image_balance", data.user_id,
        f"Recharged {data.amount} image credits for user {data.user_id}" + (f": {data.reason}" if data.reason else ""),
        None,
    )
    return ResponseModel(data=balance)


@router.post("/image-credits/deduct", response_model=ResponseModel)
def deduct_image_credits(
    data: ImageCreditDeductRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    balance = ImageCreditService.deduct(db, data.user_id, data.amount, current_user.id, data.reason)
    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "image_credit_deduct", "user_image_balance", data.user_id,
        f"Deducted {data.amount} image credits from user {data.user_id}" + (f": {data.reason}" if data.reason else ""),
        None,
    )
    return ResponseModel(data=balance)
