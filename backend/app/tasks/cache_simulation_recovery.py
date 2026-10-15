"""Recover durable local settlement decisions without replaying upstream calls."""
import asyncio
import logging

from app.services.cache_simulation_service import CacheSimulationService

logger = logging.getLogger(__name__)


async def cache_simulation_recovery_job():
    try:
        count = await asyncio.to_thread(CacheSimulationService.recover_due, 50)
        if count:
            logger.info("Cache simulation recovery settled %s requests", count)
    except Exception:
        logger.exception("Cache simulation recovery job failed")
