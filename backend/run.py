"""Uvicorn startup script for the FastAPI application."""

import os

import uvicorn

from app.config import settings

if __name__ == "__main__":
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.SERVER_PORT,
        reload=reload_enabled,
    )
