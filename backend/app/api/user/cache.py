from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import SysUser
from app.services.cache_stats_service import CacheStatsService
from app.services.cache_service import cache_service
from app.schemas.common import ResponseModel

router = APIRouter(prefix="/api/user/cache", tags=["用户-缓存管理"])


@router.get("/stats", response_model=ResponseModel)
async def get_cache_stats(
    start_date: str = Query(None),
    end_date: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Get user cache statistics."""
    stats_service = CacheStatsService(db)
    stats = await stats_service.get_user_stats(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    return ResponseModel(data=stats)


@router.delete("/clear", response_model=ResponseModel)
async def clear_cache(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Clear user cache."""
    await cache_service.clear_user_cache(current_user.id)
    return ResponseModel(message="Cache cleared successfully")


@router.get("/config", response_model=ResponseModel)
def get_cache_config(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """Get user cache configuration."""
    return ResponseModel(data={
        "cache_enabled": current_user.cache_enabled,
        "cache_billing_enabled": current_user.cache_billing_enabled,
        "cache_hit_count": current_user.cache_hit_count,
        "cache_saved_tokens": current_user.cache_saved_tokens,
    })
