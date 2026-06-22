"""Admin APIs for agent subscription sale rebate settlement."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_platform_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.schemas.payment import (
    AgentSubscriptionSaleBatchSettleRequest,
    AgentSubscriptionSaleSettleRequest,
)
from app.services.agent_subscription_sale_service import AgentSubscriptionSaleService

router = APIRouter(prefix="/api/admin/subscription-sales", tags=["管理-代理套餐销售"])


@router.get("/summary", response_model=ResponseModel)
def get_subscription_sale_summary(
    agent_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    return ResponseModel(data=AgentSubscriptionSaleService.get_summary(db, agent_id, start_date, end_date))


@router.get("", response_model=ResponseModel)
def list_subscription_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_id: int = Query(None),
    user_id: int = Query(None),
    rebate_status: str = Query(None),
    payment_channel: str = Query(None),
    keyword: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    items, total = AgentSubscriptionSaleService.list_sales(
        db,
        page=page,
        page_size=page_size,
        agent_id=agent_id,
        user_id=user_id,
        rebate_status=rebate_status,
        payment_channel=payment_channel,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})


@router.post("/batch-settle", response_model=ResponseModel)
def batch_settle_subscription_sales(
    data: AgentSubscriptionSaleBatchSettleRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentSubscriptionSaleService.batch_settle_sales(db, data.ids, current_user.id, data.remark)
    return ResponseModel(data=result, message="代理套餐销售记录核销成功")


@router.post("/{sale_id}/settle", response_model=ResponseModel)
def settle_subscription_sale(
    sale_id: int,
    data: AgentSubscriptionSaleSettleRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_platform_admin),
):
    result = AgentSubscriptionSaleService.settle_sale(db, sale_id, current_user.id, data.remark)
    return ResponseModel(data=result, message="代理套餐销售记录核销成功")
