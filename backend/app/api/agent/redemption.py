from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.log_service import LogService
from app.services.redemption_service import RedemptionService

router = APIRouter(prefix="/api/agent/redemption", tags=["代理-兑换码管理"])


class CreateAgentRedemptionCodeRequest(BaseModel):
    amount_rule_id: int = Field(..., gt=0)
    expires_days: Optional[int] = Field(None, ge=1, le=365)


@router.get("/amount-rules", response_model=ResponseModel)
def list_amount_rules(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    rules = RedemptionService.list_allowed_amount_rules(db, agent_id=int(current_user.agent_id))
    return ResponseModel(data=rules)


@router.get("", response_model=ResponseModel)
def list_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = RedemptionService.list_codes(
        db,
        page=page,
        page_size=page_size,
        status=status,
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.post("", response_model=ResponseModel)
def create_code(
    data: CreateAgentRedemptionCodeRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    result = RedemptionService.create_agent_redemption_code(
        db,
        agent_id=int(current_user.agent_id),
        operator_user_id=current_user.id,
        amount_rule_id=data.amount_rule_id,
        expires_days=data.expires_days,
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_create_redemption_code",
        target_type="redemption_code",
        target_id=result["id"],
        description=f"Agent created redemption code {result['code']}",
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=result, message="兑换码创建成功")


@router.delete("/{code_id}", response_model=ResponseModel)
def delete_code(
    code_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    RedemptionService.delete_agent_code(
        db,
        code_id=code_id,
        agent_id=int(current_user.agent_id),
        operator_user_id=current_user.id,
    )
    LogService.create_operation_log(
        db,
        current_user.id,
        current_user.username,
        "agent_delete_redemption_code",
        target_type="redemption_code",
        target_id=code_id,
        description=f"Agent deleted redemption code {code_id}",
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(message="兑换码删除成功")
