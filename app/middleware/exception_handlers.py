"""
FastAPI exception handlers for common error types.

Provides custom exception handlers for validation errors, HTTP exceptions,
and other common error scenarios.
"""

from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from pydantic import ValidationError
from telegram.error import TelegramError

from app.logging_config import get_logger


logger = get_logger(__name__)


async def validation_exception_handler(
    request: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Args:
        request: The request that caused the error
        exc: The validation exception

    Returns:
        JSON response with validation error details
    """
    # Extract context
    context = {
        "path": request.url.path,
        "method": request.method,
        "client_ip": request.client.host if request.client else None,
    }

    # Log validation error
    logger.warning(
        "Validation error",
        extra={
            **context,
            "errors": exc.errors(),
        },
    )

    # Format error response
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "detail": exc.errors(),
            "path": request.url.path,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions.

    Args:
        request: The request that caused the error
        exc: The HTTP exception

    Returns:
        JSON response with error details
    """
    # Extract context
    context = {
        "path": request.url.path,
        "method": request.method,
        "status_code": exc.status_code,
        "client_ip": request.client.host if request.client else None,
    }

    # Log based on severity
    if exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code} error", extra={**context, "detail": exc.detail}
        )
    else:
        logger.warning(
            f"HTTP {exc.status_code} error", extra={**context, "detail": exc.detail}
        )

    # Return error response
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )


async def telegram_exception_handler(
    request: Request, exc: TelegramError
) -> JSONResponse:
    """
    Handle Telegram API errors.

    Args:
        request: The request that caused the error
        exc: The Telegram exception

    Returns:
        JSON response with error details
    """
    # Extract context
    context = {
        "path": request.url.path,
        "method": request.method,
        "error_type": type(exc).__name__,
        "client_ip": request.client.host if request.client else None,
    }

    # Log Telegram error
    logger.error(
        "Telegram API error",
        extra={
            **context,
            "error_message": str(exc),
        },
        exc_info=True,
    )

    # Return error response
    # Return 200 to Telegram to acknowledge webhook
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "ok": False,
            "error": "Telegram API error",
            "detail": str(exc),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle any unhandled exceptions.

    Args:
        request: The request that caused the error
        exc: The exception

    Returns:
        JSON response with error details
    """
    # Extract context
    context = {
        "path": request.url.path,
        "method": request.method,
        "error_type": type(exc).__name__,
        "client_ip": request.client.host if request.client else None,
    }

    # Log error
    logger.error(
        "Unhandled exception",
        extra={
            **context,
            "error_message": str(exc),
        },
        exc_info=True,
    )

    # Return generic error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred",
            "path": request.url.path,
        },
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(TelegramError, telegram_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("Exception handlers registered")
