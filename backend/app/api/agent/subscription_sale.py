"""Agent-visible online subscription sale APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_agent_admin
from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ResponseModel
from app.services.agent_subscription_sale_service import AgentSubscriptionSaleService

router = APIRouter(prefix="/api/agent/subscription-sales", tags=["代理-套餐销售"])


@router.get("/summary", response_model=ResponseModel)
def get_agent_subscription_sale_summary(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    return ResponseModel(
        data=AgentSubscriptionSaleService.get_summary(
            db,
            agent_id=int(current_user.agent_id),
            start_date=start_date,
            end_date=end_date,
        )
    )


@router.get("", response_model=ResponseModel)
def list_agent_subscription_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    rebate_status: str = Query(None),
    payment_channel: str = Query(None),
    keyword: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_agent_admin),
):
    items, total = AgentSubscriptionSaleService.list_sales(
        db,
        page=page,
        page_size=page_size,
        agent_id=int(current_user.agent_id),
        user_id=user_id,
        rebate_status=rebate_status,
        payment_channel=payment_channel,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
    )
    return ResponseModel(data={"list": items, "total": total, "page": page, "page_size": page_size})
