"""Custom middleware for the FastAPI application."""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request method, path, response status, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "%s %s -> %d (%.2f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response
