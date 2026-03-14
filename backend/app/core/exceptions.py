"""Custom exceptions and global exception handlers for FastAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ServiceException(Exception):
    """Business-logic exception that maps to an HTTP error response."""

    def __init__(self, status_code: int = 400, detail: str = "Service error", error_code: str = "SERVICE_ERROR"):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(ServiceException)
    async def service_exception_handler(request: Request, exc: ServiceException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.error_code,
                "message": exc.detail,
                "data": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        field = " -> ".join(str(loc) for loc in first_error.get("loc", []))
        message = first_error.get("msg", "Validation error")
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": f"Validation error on field [{field}]: {message}",
                "data": errors,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        import logging
        logging.getLogger(__name__).error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "data": None,
            },
        )
