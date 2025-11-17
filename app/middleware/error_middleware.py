"""
Error handling middleware for FastAPI application.

Provides centralized exception handling and request/response logging.
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger


logger = get_logger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling exceptions and logging requests/responses.

    Catches unhandled exceptions, logs them with context, and returns
    appropriate error responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and handle any exceptions.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response from the handler or error response
        """
        # Generate request ID for tracking
        request_id = f"{int(time.time() * 1000)}"

        # Extract context from request
        context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None,
        }

        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.url.path}", extra=context
        )

        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Log successful response
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    **context,
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s",
                },
            )

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            return response

        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time

            # Log error with full context
            logger.error(
                f"Unhandled exception during request: {request.method} {request.url.path}",
                extra={
                    **context,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "process_time": f"{process_time:.3f}s",
                    "traceback": traceback.format_exc(),
                },
                exc_info=True,
            )

            # Return appropriate error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                    "detail": (
                        str(e)
                        if logger.level == "DEBUG"
                        else "An error occurred processing your request"
                    ),
                },
                headers={
                    "X-Request-ID": request_id,
                    "X-Process-Time": f"{process_time:.3f}",
                },
            )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for detailed request/response logging.

    Logs request body, headers, and response details for debugging.
    Only active in development/debug mode.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request with detailed logging.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response from the handler
        """
        # Only log details in debug mode
        if logger.level != "DEBUG":
            return await call_next(request)

        # Log request details
        logger.debug(
            "Request details",
            extra={
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "path_params": request.path_params,
                "query_params": dict(request.query_params),
            },
        )

        # Process request
        response = await call_next(request)

        # Log response details
        logger.debug(
            "Response details",
            extra={
                "status_code": response.status_code,
                "headers": dict(response.headers),
            },
        )

        return response
