from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import SessionLocal
from app.services.health_service import HealthService
from app.services.subscription_service import SubscriptionService
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


async def subscription_maintenance_job():
    """Periodic subscription status sync for expiring plans."""
    logger.info("Starting scheduled subscription maintenance...")
    db = SessionLocal()
    try:
        expired_count = SubscriptionService.check_and_expire_subscriptions(db)
        logger.info("Subscription maintenance completed: expired=%s", expired_count)
    except Exception as e:
        logger.error(f"Subscription maintenance job failed: {e}")
    finally:
        db.close()


def start_scheduler(interval_seconds: int = 300):
    """Start background schedulers."""
    scheduler.add_job(
        health_check_job,
        'interval',
        seconds=interval_seconds,
        id='health_check',
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        subscription_maintenance_job,
        'interval',
        seconds=max(300, interval_seconds),
        id='subscription_maintenance',
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Schedulers started (health interval: {interval_seconds}s)")


async def run_startup_health_check():
    """Run an immediate health check on startup"""
    logger.info("Running startup health check...")
    await health_check_job()
