from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import require_agent_admin
from app.models.agent import AgentBalance
from app.models.log import RequestLog
from app.models.redemption import RedemptionCode
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.agent_service import AgentService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/agent/stats", tags=["代理-统计"])


@router.get("/workbench", response_model=ResponseModel)
def get_workbench_summary(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    agent_id = int(current_user.agent_id)
    agent = AgentService.get_agent(db, agent_id)
    balance_row = db.query(AgentBalance).filter(AgentBalance.agent_id == agent_id).first()
    inventory = AgentService.list_agent_subscription_inventory(db, agent_id)
    total_remaining = sum(int(item.get("remaining_count") or 0) for item in inventory)
    total_granted = sum(int(item.get("total_granted") or 0) for item in inventory)
    total_used = sum(int(item.get("total_used") or 0) for item in inventory)
    low_stock_count = sum(1 for item in inventory if 0 < int(item.get("remaining_count") or 0) <= 3)
    empty_stock_count = sum(1 for item in inventory if int(item.get("remaining_count") or 0) <= 0)
    frozen_balance = db.query(func.coalesce(func.sum(RedemptionCode.amount), 0)).filter(
        RedemptionCode.agent_id == agent_id,
        RedemptionCode.status == "unused",
    ).scalar() or 0
    frozen_code_count = db.query(func.count(RedemptionCode.id)).filter(
        RedemptionCode.agent_id == agent_id,
        RedemptionCode.status == "unused",
    ).scalar() or 0

    total_allocated = Decimal(str(balance_row.total_allocated or 0)) if balance_row else Decimal("0")
    total_reclaimed = Decimal(str(balance_row.total_reclaimed or 0)) if balance_row else Decimal("0")
    frozen_balance_decimal = Decimal(str(frozen_balance or 0))
    used_balance = total_allocated - total_reclaimed - frozen_balance_decimal
    if used_balance < Decimal("0"):
        used_balance = Decimal("0")

    return ResponseModel(data={
        "agent": agent,
        "balance": agent.get("balance", 0),
        "used_balance": float(used_balance),
        "frozen_balance": float(frozen_balance_decimal),
        "image_credit_balance": agent.get("image_credit_balance", 0),
        "redemption_summary": {
            "unused_code_count": int(frozen_code_count or 0),
            "unused_code_amount": float(frozen_balance_decimal),
        },
        "subscription_inventory": inventory,
        "subscription_summary": {
            "plan_count": len(inventory),
            "total_remaining": total_remaining,
            "total_granted": total_granted,
            "total_used": total_used,
            "low_stock_count": low_stock_count,
            "empty_stock_count": empty_stock_count,
        },
    })


@router.get("/dashboard", response_model=ResponseModel)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    start_time, _end_time = LogService._get_timezone_day_window(1)
    agent_id = int(current_user.agent_id)

    total_users = db.query(func.count(SysUser.id)).filter(
        SysUser.agent_id == agent_id,
        SysUser.role == "user",
    ).scalar()
    today_requests = db.query(func.count(RequestLog.id)).filter(
        RequestLog.agent_id == agent_id,
        RequestLog.created_at >= start_time,
    ).scalar()
    today_tokens = db.query(func.coalesce(func.sum(RequestLog.total_tokens), 0)).filter(
        RequestLog.agent_id == agent_id,
        RequestLog.created_at >= start_time,
    ).scalar()
    today_errors = db.query(func.count(RequestLog.id)).filter(
        RequestLog.agent_id == agent_id,
        RequestLog.created_at >= start_time,
        RequestLog.status != "success",
    ).scalar()

    return ResponseModel(data={
        "total_users": int(total_users or 0),
        "today_requests": int(today_requests or 0),
        "today_tokens": int(today_tokens or 0),
        "today_errors": int(today_errors or 0),
    })


@router.get("/requests", response_model=ResponseModel)
def get_request_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    stats = LogService.get_request_stats(
        db,
        days=days,
        agent_id=int(current_user.agent_id),
    )
    return ResponseModel(data=stats)


@router.get("/token-ranking", response_model=ResponseModel)
def get_token_ranking(
    days: int = Query(1, ge=1, le=30),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    ranking = LogService.get_agent_token_ranking(
        db,
        agent_id=int(current_user.agent_id),
        days=days,
        limit=limit,
    )
    return ResponseModel(data={"days": days, "ranking": ranking})
