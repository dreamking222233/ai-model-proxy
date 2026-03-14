from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.services.health_service import HealthService
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def health_check_job():
    """Periodic health check for all enabled channels"""
    logger.info("Starting scheduled health check...")
    db = SessionLocal()
    try:
        results = await HealthService.check_all_channels(db)
        healthy = sum(1 for r in results if r["is_healthy"])
        logger.info(f"Health check completed: {healthy}/{len(results)} channels healthy")
    except Exception as e:
        logger.error(f"Health check job failed: {e}")
    finally:
        db.close()


def start_scheduler(interval_seconds: int = 300):
    """Start the health check scheduler"""
    scheduler.add_job(
        health_check_job,
        'interval',
        seconds=interval_seconds,
        id='health_check',
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Health check scheduler started (interval: {interval_seconds}s)")


async def run_startup_health_check():
    """Run an immediate health check on startup"""
    logger.info("Running startup health check...")
    await health_check_job()
