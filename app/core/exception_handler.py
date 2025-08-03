import logging
from typing import Any, Dict
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import InternalServerError, AppException

logger = logging.getLogger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:

    if exc.status_code >= 500:
        logger.error(
            f"Server Error: {exc.error_code}",
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "detail": exc.detail,
                "context": exc.context,
                "path": request.url.path,
                "method": request.method,
            },
            exc_info=True,
        )
    elif exc.status_code >= 400:
        logger.warning(
            f"Client error: {exc.error_code}",
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "detail": exc.detail,
                "context": exc.context,
                "path": request.url.path,
                "method": request.method,
            },
        )
    return JSONResponse(
        status_code=exc.status_code, content=exc.to_dict(), headers=exc.headers
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI validation errors.

    Converts Pydantic validation errors into a consistent error response format.
    """
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        if "ctx" in error:
            error_detail["context"] = error["ctx"]
        errors.append(error_detail)

    logger.warning(
        "Validation error",
        extra={"errors": errors, "path": request.url.path, "method": request.method},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "status_code": 422,
                "context": {"errors": errors},
            }
        },
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette HTTP exceptions.

    Converts standard HTTP exceptions into our consistent error response format.
    """
    logger.warning(
        f"HTTP exception: {exc.status_code}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "status_code": exc.status_code,
                "context": {},
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unhandled exceptions.

    Catches any unhandled exceptions and converts them into 500 errors
    with a unique error ID for tracking.
    """
    error_id = str(uuid4())

    logger.error(
        f"Unhandled exception: {error_id}",
        extra={
            "error_id": error_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )

    # In production, don't expose internal error details
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "status_code": 500,
                "context": {"error_id": error_id},
            }
        },
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Register custom exception handler
    app.add_exception_handler(AppException, app_exception_handler)

    # Register validation exception handler
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Register HTTP exception handler
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Register catch-all exception handler
    app.add_exception_handler(Exception, unhandled_exception_handler)
