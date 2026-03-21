from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import update
from app.database import get_db
from app.core.dependencies import require_admin
from app.models.user import SysUser
from app.services.cache_stats_service import CacheStatsService
from app.services.cache_service import cache_service
from app.services.log_service import LogService
from app.schemas.common import ResponseModel
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/cache", tags=["管理-缓存管理"])


class CacheConfigUpdate(BaseModel):
    cache_enabled: int
    cache_billing_enabled: int


@router.get("/stats/{user_id}", response_model=ResponseModel)
async def get_user_cache_stats(
    user_id: int,
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """Get user cache statistics (admin)."""
    stats_service = CacheStatsService(db)
    stats = await stats_service.get_user_stats(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    return ResponseModel(data=stats)


@router.delete("/clear/{user_id}", response_model=ResponseModel)
async def clear_user_cache(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """Clear user cache (admin)."""
    await cache_service.clear_user_cache(user_id)

    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "clear_cache", "user_cache", user_id,
        f"Cleared cache for user {user_id}",
        None,
    )

    return ResponseModel(message="Cache cleared successfully")


@router.put("/config/{user_id}", response_model=ResponseModel)
async def update_cache_config(
    user_id: int,
    data: CacheConfigUpdate,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_admin),
):
    """Update user cache configuration (admin)."""
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        return ResponseModel(code=404, message="User not found")

    await db.execute(
        update(SysUser)
        .where(SysUser.id == user_id)
        .values(
            cache_enabled=data.cache_enabled,
            cache_billing_enabled=data.cache_billing_enabled
        )
    )
    await db.commit()

    LogService.create_operation_log(
        db, current_user.id, current_user.username,
        "update_cache_config", "user_cache", user_id,
        f"Updated cache config: cache_enabled={data.cache_enabled}, cache_billing_enabled={data.cache_billing_enabled}",
        None,
    )

    return ResponseModel(message="Cache configuration updated successfully")
