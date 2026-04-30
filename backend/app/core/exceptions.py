"""Custom exceptions and global exception handlers for FastAPI."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ServiceException(Exception):
    """Business-logic exception that maps to an HTTP error response."""

    def __init__(self, status_code: int = 400, detail: str = "服务异常", error_code: str = "SERVICE_ERROR"):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


def _translate_validation_message(error: dict) -> str:
    """Return Chinese-only validation messages for API responses."""
    error_type = str(error.get("type") or "")
    ctx = error.get("ctx") or {}
    msg = str(error.get("msg") or "请求参数校验失败")
    if error_type in {"missing", "value_error.missing"}:
        return "字段必填"
    if error_type in {"greater_than", "value_error.number.not_gt"}:
        return f"必须大于 {ctx.get('gt')}" if ctx.get("gt") is not None else "必须大于指定值"
    if error_type in {"greater_than_equal", "value_error.number.not_ge"}:
        return f"必须大于或等于 {ctx.get('ge')}" if ctx.get("ge") is not None else "必须大于或等于指定值"
    if error_type in {"less_than", "value_error.number.not_lt"}:
        return f"必须小于 {ctx.get('lt')}" if ctx.get("lt") is not None else "必须小于指定值"
    if error_type in {"less_than_equal", "value_error.number.not_le"}:
        return f"必须小于或等于 {ctx.get('le')}" if ctx.get("le") is not None else "必须小于或等于指定值"
    if error_type in {"int_parsing", "type_error.integer"}:
        return "必须是整数"
    if error_type in {"float_parsing", "decimal_parsing", "type_error.float", "type_error.decimal"}:
        return "必须是数字"
    if error_type in {"string_too_short", "value_error.any_str.min_length"}:
        return f"长度不能少于 {ctx.get('min_length')} 个字符" if ctx.get("min_length") is not None else "长度过短"
    if error_type in {"string_too_long", "value_error.any_str.max_length"}:
        return f"长度不能超过 {ctx.get('max_length')} 个字符" if ctx.get("max_length") is not None else "长度过长"
    if msg.startswith("Value error, "):
        return msg.replace("Value error, ", "", 1)
    if msg.startswith("value is not a valid"):
        return "参数类型不正确"
    if msg.startswith("Input should be"):
        return "参数值不符合要求"
    if msg == "field required":
        return "字段必填"
    if msg.startswith("ensure this value is greater than"):
        return "必须大于指定值"
    if msg.startswith("ensure this value is greater than or equal to"):
        return "必须大于或等于指定值"
    if msg.startswith("ensure this value is less than"):
        return "必须小于指定值"
    if msg.startswith("ensure this value is less than or equal to"):
        return "必须小于或等于指定值"
    return msg


def _serialize_validation_errors(errors: list[dict]) -> list[dict]:
    return [
        {
            "loc": error.get("loc", []),
            "msg": _translate_validation_message(error),
            "type": "参数校验错误",
        }
        for error in errors
    ]


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
        message = _translate_validation_message(first_error)
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": f"请求参数校验失败，字段 [{field}]：{message}",
                "data": _serialize_validation_errors(errors),
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
                "message": "服务器内部错误，请稍后重试",
                "data": None,
            },
        )
