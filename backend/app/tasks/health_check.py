"""
Health check task module.
The actual scheduler logic is in tasks/__init__.py.
This module provides additional utilities for health check management.
"""
from app.tasks import scheduler, health_check_job
import logging

logger = logging.getLogger(__name__)


async def trigger_manual_check():
    """Trigger an immediate health check (called from admin API)"""
    await health_check_job()


def update_check_interval(interval_seconds: int):
    """Update the health check interval dynamically"""
    try:
        scheduler.reschedule_job(
            'health_check',
            trigger='interval',
            seconds=interval_seconds,
        )
        logger.info(f"Health check interval updated to {interval_seconds}s")
    except Exception as e:
        logger.error(f"Failed to update health check interval: {e}")
