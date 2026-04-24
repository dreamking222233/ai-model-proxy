"""SQLAlchemy database setup with synchronous pymysql driver."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_use_lifo=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def release_session_connection(db: Session | None) -> None:
    """Release the current database connection held by a request-scoped session."""
    if db is None:
        return
    try:
        db.close()
    except Exception as exc:
        logger.warning("Failed to release database session connection: %s", exc)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a short-lived session for isolated read/write operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_pool_status_snapshot() -> dict[str, Any]:
    """Return a structured snapshot of the current SQLAlchemy pool state."""
    pool = engine.pool
    snapshot: dict[str, Any] = {
        "pool_class": pool.__class__.__name__,
        "configured_pool_size": settings.DB_POOL_SIZE,
        "configured_max_overflow": settings.DB_MAX_OVERFLOW,
        "configured_pool_timeout": settings.DB_POOL_TIMEOUT,
        "configured_pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "status": pool.status() if hasattr(pool, "status") else None,
    }

    for attr in ("size", "checkedin", "checkedout", "overflow"):
        value = getattr(pool, attr, None)
        if callable(value):
            try:
                snapshot[attr] = value()
            except Exception:
                snapshot[attr] = None
        else:
            snapshot[attr] = None

    return snapshot
