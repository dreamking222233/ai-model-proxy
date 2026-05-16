"""Public payment callbacks."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/public/payment", tags=["公开-支付回调"])
logger = logging.getLogger(__name__)


@router.get("/alipay/return")
def alipay_return(
    request: Request,
    db: Session = Depends(get_db),
):
    redirect_url = PaymentService.handle_alipay_return(
        db,
        {str(key): str(value) for key, value in request.query_params.items()},
    )
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/alipay/notify")
async def alipay_notify(
    request: Request,
    db: Session = Depends(get_db),
):
    form_payload: dict[str, str] = {}
    try:
        form_data = await request.form()
        form_payload = {str(key): str(value) for key, value in form_data.items()}
        PaymentService.handle_alipay_notify(
            db,
            form_payload,
        )
        return PlainTextResponse("success")
    except Exception:
        db.rollback()
        logger.exception("Alipay notify failed: payload=%s", form_payload)
        return PlainTextResponse("failure", status_code=500)
