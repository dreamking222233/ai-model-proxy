"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cors import DynamicCORSMiddleware
from app.database import get_pool_status_snapshot
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestLoggingMiddleware

# Import all models to ensure they are registered with SQLAlchemy metadata
import app.models  # noqa: F401

# Import routers
from app.api.auth import router as auth_router
from app.api.public.site import router as public_site_router
from app.api.public.payment import router as public_payment_router
from app.api.admin.agent import router as admin_agent_router
from app.api.admin.payment import router as admin_payment_router
from app.api.admin.channel import router as admin_channel_router
from app.api.admin.model import router as admin_model_router
from app.api.admin.user import router as admin_user_router
from app.api.admin.log import router as admin_log_router
from app.api.admin.health import router as admin_health_router
from app.api.admin.system import router as admin_system_router
from app.api.admin.redemption import router as admin_redemption_router
from app.api.admin.subscription import router as admin_subscription_router
from app.api.admin.promotion import router as admin_promotion_router
from app.api.admin.price_adjustment import router as admin_price_adjustment_router
from app.api.user.api_key import router as user_api_key_router
from app.api.user.balance import router as user_balance_router
from app.api.user.payment import router as user_payment_router
from app.api.user.profile import router as user_profile_router
from app.api.user.models import router as user_models_router
from app.api.user.stats import router as user_stats_router
from app.api.user.redemption import router as user_redemption_router
from app.api.user.promotion import router as user_promotion_router
from app.api.agent.user import router as agent_user_router
from app.api.agent.payment import router as agent_payment_router
from app.api.agent.log import router as agent_log_router
from app.api.agent.stats import router as agent_stats_router
from app.api.agent.system import router as agent_system_router
from app.api.agent.subscription import router as agent_subscription_router
from app.api.agent.redemption import router as agent_redemption_router
from app.api.agent.promotion import router as agent_promotion_router
from app.api.proxy.openai_proxy import router as openai_proxy_router
from app.api.proxy.anthropic_proxy import router as anthropic_proxy_router
from app.api.proxy.image_proxy import router as image_proxy_router
from app.api.proxy.video_proxy import router as video_proxy_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info("Starting Model Invocation System...")
    logger.info("Initial DB pool status: %s", get_pool_status_snapshot())

    # Read health check interval from config
    from app.database import SessionLocal
    from app.models.log import SystemConfig
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "health_check_interval"
        ).first()
        interval = int(config.config_value) if config else 300
    finally:
        db.close()

    # Start health check scheduler
    from app.tasks import start_scheduler, run_startup_health_check
    start_scheduler(interval)

    # Run startup health check (non-blocking, don't fail startup)
    try:
        await run_startup_health_check()
    except Exception as e:
        logger.warning(f"Startup health check failed (non-critical): {e}")

    logger.info("Model Invocation System started successfully!")
    yield

    # Shutdown
    from app.tasks import scheduler
    scheduler.shutdown(wait=False)
    logger.info("Final DB pool status: %s", get_pool_status_snapshot())
    logger.info("Model Invocation System shutdown.")


app = FastAPI(
    title="Model Invocation System",
    description="AI Model Proxy Platform with multi-channel failover",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware: dynamic allowlist only. Avoid wildcard origin reflection with credentials.
app.add_middleware(DynamicCORSMiddleware)

# Custom middleware
app.add_middleware(RequestLoggingMiddleware)

# Exception handlers
register_exception_handlers(app)

# Register routers - Auth
app.include_router(auth_router)
app.include_router(public_site_router)
app.include_router(public_payment_router)

# Register routers - Admin
app.include_router(admin_channel_router)
app.include_router(admin_agent_router)
app.include_router(admin_model_router)
app.include_router(admin_user_router)
app.include_router(admin_log_router)
app.include_router(admin_health_router)
app.include_router(admin_system_router)
app.include_router(admin_redemption_router)
app.include_router(admin_subscription_router)
app.include_router(admin_payment_router)
app.include_router(admin_promotion_router)
app.include_router(admin_price_adjustment_router)

# Register routers - User
app.include_router(user_api_key_router)
app.include_router(user_balance_router)
app.include_router(user_payment_router)
app.include_router(user_profile_router)
app.include_router(user_models_router)
app.include_router(user_stats_router)
app.include_router(user_redemption_router)
app.include_router(user_promotion_router)

# Register routers - Agent
app.include_router(agent_user_router)
app.include_router(agent_payment_router)
app.include_router(agent_log_router)
app.include_router(agent_stats_router)
app.include_router(agent_system_router)
app.include_router(agent_subscription_router)
app.include_router(agent_redemption_router)
app.include_router(agent_promotion_router)

# Register routers - Proxy
app.include_router(openai_proxy_router)
app.include_router(anthropic_proxy_router)
app.include_router(image_proxy_router)
app.include_router(video_proxy_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
