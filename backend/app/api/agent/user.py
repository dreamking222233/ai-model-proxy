from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.exceptions import ServiceException
from app.core.dependencies import require_agent_admin, assert_user_in_agent_scope
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.user import BalanceRechargeRequest, BalanceDeductRequest, ImageCreditRechargeRequest, ImageCreditDeductRequest
from app.services.agent_asset_service import AgentAssetService
from app.services.auth_service import AuthService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agent/users", tags=["代理-用户管理"])


@router.get("", response_model=ResponseModel)
def list_agent_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    sort_by: str = Query("id"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = AuthService.list_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        agent_id=int(current_user.agent_id),
        roles=["user"],
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.get("/{user_id}", response_model=ResponseModel)
def get_agent_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    data = AuthService.get_user_detail(db, user_id, agent_id=int(current_user.agent_id))
    return ResponseModel(data=data)


@router.put("/{user_id}/status", response_model=ResponseModel)
def toggle_agent_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    target_user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not target_user:
        raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
    if target_user.role != "user":
        raise ServiceException(403, "这里只能管理终端用户", "INVALID_AGENT_TARGET_USER")
    assert_user_in_agent_scope(target_user, int(current_user.agent_id))
    user = AuthService.toggle_user_status(db, user_id)
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_toggle_user_status",
        target_type="user",
        target_id=user_id,
        description=f"代理切换用户 {user_id} 状态为 {user.status}",
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data={"id": user.id, "status": user.status})


@router.post("/recharge", response_model=ResponseModel)
def recharge_balance(
    data: BalanceRechargeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentAssetService.grant_user_balance(
        db,
        agent_id=int(current_user.agent_id),
        user_id=data.user_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark="agent_recharge_balance",
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_recharge_balance",
        target_type="user_balance",
        target_id=data.user_id,
        description=f"代理为用户 {data.user_id} 充值余额 {data.amount}",
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=result)


@router.post("/deduct", response_model=ResponseModel)
def deduct_balance(
    data: BalanceDeductRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentAssetService.reclaim_user_balance(
        db,
        agent_id=int(current_user.agent_id),
        user_id=data.user_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.reason,
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_deduct_balance",
        target_type="user_balance",
        target_id=data.user_id,
        description=f"代理从用户 {data.user_id} 扣减余额 {data.amount}" + (f"：{data.reason}" if data.reason else ""),
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=result)


@router.post("/image-credits/recharge", response_model=ResponseModel)
def recharge_image_credits(
    data: ImageCreditRechargeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentAssetService.grant_user_image_credits(
        db,
        agent_id=int(current_user.agent_id),
        user_id=data.user_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.reason,
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_recharge_image_credits",
        target_type="user_image_balance",
        target_id=data.user_id,
        description=f"代理为用户 {data.user_id} 充值图片积分 {data.amount}" + (f"：{data.reason}" if data.reason else ""),
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=result)


@router.post("/image-credits/deduct", response_model=ResponseModel)
def deduct_image_credits(
    data: ImageCreditDeductRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = AgentAssetService.reclaim_user_image_credits(
        db,
        agent_id=int(current_user.agent_id),
        user_id=data.user_id,
        amount=data.amount,
        operator_user_id=current_user.id,
        remark=data.reason,
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_deduct_image_credits",
        target_type="user_image_balance",
        target_id=data.user_id,
        description=f"代理从用户 {data.user_id} 扣减图片积分 {data.amount}" + (f"：{data.reason}" if data.reason else ""),
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=result)
