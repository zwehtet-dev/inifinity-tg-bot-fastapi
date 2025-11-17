"""
Error handling utilities for the FastAPI bot engine.

Provides centralized error handling for Telegram API, OCR, and backend API errors.
"""

from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import (
    TelegramError,
    NetworkError,
    TimedOut,
    BadRequest,
    Forbidden,
    ChatMigrated,
    RetryAfter,
    Conflict,
)
from openai import (
    APIError,
    APIConnectionError,
    RateLimitError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
)
import httpx

from app.logging_config import get_logger


logger = get_logger(__name__)


class ErrorHandler:
    """
    Centralized error handler for the bot engine.

    Handles errors from Telegram API, OpenAI OCR, and backend API with
    appropriate logging, user notifications, and admin alerts.
    """

    def __init__(
        self, bot: Bot, admin_group_id: int, admin_topic_id: Optional[int] = None
    ):
        """
        Initialize the error handler.

        Args:
            bot: Telegram Bot instance
            admin_group_id: Admin group ID for error notifications
            admin_topic_id: Optional topic ID for error notifications
        """
        self.bot = bot
        self.admin_group_id = admin_group_id
        self.admin_topic_id = admin_topic_id

    async def handle_telegram_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Handle errors from Telegram API.

        Args:
            error: The exception that occurred
            context: Optional context information (user_id, chat_id, etc.)

        Returns:
            True if error was handled and operation should be retried, False otherwise
        """
        context = context or {}
        user_id = context.get("user_id")
        chat_id = context.get("chat_id")
        operation = context.get("operation", "unknown")

        # Log error with context
        logger.error(
            f"Telegram API error during {operation}",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "user_id": user_id,
                "chat_id": chat_id,
                **context,
            },
            exc_info=True,
        )

        # Handle specific error types
        if isinstance(error, Forbidden):
            # Bot was blocked by user or doesn't have permission (e.g., kicked from group)
            logger.warning(
                f"Bot blocked by user or forbidden from chat",
                extra={"user_id": user_id, "chat_id": chat_id},
            )
            # Don't retry, don't notify user
            return False

        elif isinstance(error, ChatMigrated):
            # Chat was migrated to supergroup
            new_chat_id = error.new_chat_id
            logger.info(
                f"Chat migrated",
                extra={"old_chat_id": chat_id, "new_chat_id": new_chat_id},
            )
            # Update chat_id in context and retry
            if context:
                context["chat_id"] = new_chat_id
            return True

        elif isinstance(error, RetryAfter):
            # Rate limited by Telegram
            retry_after = error.retry_after
            logger.warning(
                f"Rate limited by Telegram, retry after {retry_after}s",
                extra={"retry_after": retry_after},
            )
            # Notify admin about rate limiting
            await self._notify_admin_error(
                f"⚠️ Rate Limited\n"
                f"Retry after: {retry_after}s\n"
                f"Operation: {operation}"
            )
            # Should retry after delay
            return True

        elif isinstance(error, BadRequest):
            # Bad request - likely a bug in our code
            # Check BadRequest before NetworkError since BadRequest inherits from NetworkError
            logger.error(
                f"Bad request to Telegram API",
                extra={"error": str(error), "operation": operation},
            )
            # Notify admin
            await self._notify_admin_error(
                f"🐛 Bad Request Error\n"
                f"Operation: {operation}\n"
                f"Error: {str(error)}\n"
                f"User: {user_id}"
            )
            # Don't retry
            return False

        elif isinstance(error, NetworkError) or isinstance(error, TimedOut):
            # Network or timeout error - transient
            logger.warning(
                f"Network/timeout error during {operation}", extra={"error": str(error)}
            )
            # Retry
            return True

        elif isinstance(error, Conflict):
            # Webhook conflict (multiple instances running)
            logger.critical(
                "Webhook conflict detected - multiple bot instances running!",
                extra={"error": str(error)},
            )
            await self._notify_admin_error(
                f"🚨 CRITICAL: Webhook Conflict\n"
                f"Multiple bot instances detected!\n"
                f"Error: {str(error)}"
            )
            # Don't retry
            return False

        else:
            # Unknown Telegram error
            logger.error(
                f"Unknown Telegram error",
                extra={"error_type": type(error).__name__, "error": str(error)},
            )
            # Notify admin
            await self._notify_admin_error(
                f"❌ Telegram Error\n"
                f"Type: {type(error).__name__}\n"
                f"Operation: {operation}\n"
                f"Error: {str(error)}"
            )
            # Don't retry unknown errors
            return False

    async def handle_ocr_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Handle errors from OpenAI OCR service.

        Args:
            error: The exception that occurred
            context: Optional context information (user_id, chat_id, etc.)

        Returns:
            User-friendly error message to display, or None if no message needed
        """
        context = context or {}
        user_id = context.get("user_id")
        chat_id = context.get("chat_id")

        # Log error with context
        logger.error(
            "OCR service error",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "user_id": user_id,
                "chat_id": chat_id,
                **context,
            },
            exc_info=True,
        )

        # Handle specific OpenAI error types
        if isinstance(error, RateLimitError):
            # Rate limited by OpenAI
            logger.warning("OpenAI rate limit exceeded")
            await self._notify_admin_error(
                f"⚠️ OpenAI Rate Limit\n"
                f"User: {user_id}\n"
                f"Consider upgrading API plan"
            )
            return (
                "⏳ Receipt verification is temporarily busy. "
                "Please wait a moment and try again."
            )

        elif isinstance(error, AuthenticationError):
            # Invalid API key
            logger.critical("OpenAI authentication failed - invalid API key!")
            await self._notify_admin_error(
                f"🚨 CRITICAL: OpenAI Auth Failed\n" f"Check API key configuration"
            )
            return (
                "❌ Receipt verification is unavailable. "
                "Your receipt will be reviewed manually by an admin."
            )

        elif isinstance(error, APITimeoutError):
            # Timeout
            logger.warning("OpenAI API timeout")
            return (
                "⏱️ Receipt verification timed out. "
                "Please try again with a clearer image."
            )

        elif isinstance(error, APIConnectionError):
            # Connection error
            logger.warning("OpenAI API connection error")
            return (
                "🔌 Connection error during receipt verification. "
                "Please try again in a moment."
            )

        elif isinstance(error, BadRequestError):
            # Bad request - likely invalid image
            logger.warning("OpenAI bad request - possibly invalid image")
            return (
                "📷 Unable to process this image. "
                "Please send a clear photo of your receipt."
            )

        elif isinstance(error, APIError):
            # General API error
            logger.error(f"OpenAI API error: {str(error)}")
            await self._notify_admin_error(
                f"❌ OpenAI API Error\n" f"User: {user_id}\n" f"Error: {str(error)}"
            )
            return (
                "❌ Receipt verification failed. "
                "Your receipt will be reviewed manually by an admin."
            )

        else:
            # Unknown error
            logger.error(
                f"Unknown OCR error: {type(error).__name__}",
                extra={"error": str(error)},
            )
            await self._notify_admin_error(
                f"❌ OCR Error\n"
                f"Type: {type(error).__name__}\n"
                f"User: {user_id}\n"
                f"Error: {str(error)}"
            )
            return (
                "❌ Receipt verification encountered an error. "
                "Your receipt will be reviewed manually by an admin."
            )

    async def handle_backend_error(
        self, error: Exception, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Handle errors from backend API.

        Args:
            error: The exception that occurred
            context: Optional context information (user_id, chat_id, endpoint, etc.)

        Returns:
            True if error was transient and operation should be retried, False otherwise
        """
        context = context or {}
        user_id = context.get("user_id")
        chat_id = context.get("chat_id")
        endpoint = context.get("endpoint", "unknown")

        # Log error with context
        logger.error(
            f"Backend API error at {endpoint}",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "user_id": user_id,
                "chat_id": chat_id,
                "endpoint": endpoint,
                **context,
            },
            exc_info=True,
        )

        # Handle specific httpx error types
        if isinstance(error, httpx.TimeoutException):
            # Timeout - transient
            logger.warning(f"Backend API timeout at {endpoint}")
            await self._notify_admin_error(
                f"⏱️ Backend Timeout\n" f"Endpoint: {endpoint}\n" f"User: {user_id}"
            )
            # Retry
            return True

        elif isinstance(error, httpx.ConnectError):
            # Connection error - backend might be down
            logger.error(f"Cannot connect to backend at {endpoint}")
            await self._notify_admin_error(
                f"🚨 Backend Connection Failed\n"
                f"Endpoint: {endpoint}\n"
                f"Backend may be down!"
            )
            # Retry
            return True

        elif isinstance(error, httpx.NetworkError):
            # Network error - transient
            logger.warning(f"Network error connecting to backend at {endpoint}")
            # Retry
            return True

        elif isinstance(error, httpx.HTTPStatusError):
            # HTTP error response
            status_code = error.response.status_code
            logger.error(
                f"Backend returned error status {status_code}",
                extra={"status_code": status_code, "response": error.response.text},
            )

            if status_code >= 500:
                # Server error - might be transient
                await self._notify_admin_error(
                    f"❌ Backend Server Error\n"
                    f"Status: {status_code}\n"
                    f"Endpoint: {endpoint}\n"
                    f"User: {user_id}"
                )
                # Retry server errors
                return True
            elif status_code == 429:
                # Rate limited
                await self._notify_admin_error(
                    f"⚠️ Backend Rate Limit\n" f"Endpoint: {endpoint}"
                )
                # Retry after delay
                return True
            else:
                # Client error (4xx) - don't retry
                await self._notify_admin_error(
                    f"❌ Backend Client Error\n"
                    f"Status: {status_code}\n"
                    f"Endpoint: {endpoint}\n"
                    f"User: {user_id}"
                )
                return False

        else:
            # Unknown error
            logger.error(
                f"Unknown backend error: {type(error).__name__}",
                extra={"error": str(error)},
            )
            await self._notify_admin_error(
                f"❌ Backend Error\n"
                f"Type: {type(error).__name__}\n"
                f"Endpoint: {endpoint}\n"
                f"User: {user_id}\n"
                f"Error: {str(error)}"
            )
            # Don't retry unknown errors
            return False

    async def _notify_admin_error(self, message: str):
        """
        Send error notification to admin group.

        Args:
            message: Error message to send
        """
        try:
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                message_thread_id=self.admin_topic_id,
                text=f"🔔 Error Notification\n\n{message}",
                parse_mode=None,
            )
        except Exception as e:
            # If we can't notify admin, just log it
            logger.error(
                f"Failed to send error notification to admin: {e}", exc_info=True
            )

    async def notify_critical_error(self, title: str, details: Dict[str, Any]):
        """
        Send critical error notification to admin group.

        Args:
            title: Error title
            details: Error details dictionary
        """
        message_parts = [f"🚨 CRITICAL ERROR: {title}\n"]

        for key, value in details.items():
            message_parts.append(f"{key}: {value}")

        message = "\n".join(message_parts)

        try:
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                message_thread_id=self.admin_topic_id,
                text=message,
                parse_mode=None,
            )
        except Exception as e:
            logger.error(
                f"Failed to send critical error notification: {e}", exc_info=True
            )


# Convenience functions for use throughout the application


async def handle_telegram_error(
    error: Exception,
    bot: Bot,
    admin_group_id: int,
    context: Optional[Dict[str, Any]] = None,
    admin_topic_id: Optional[int] = None,
) -> bool:
    """
    Convenience function to handle Telegram errors.

    Args:
        error: The exception that occurred
        bot: Telegram Bot instance
        admin_group_id: Admin group ID for notifications
        context: Optional context information
        admin_topic_id: Optional topic ID for notifications

    Returns:
        True if operation should be retried, False otherwise
    """
    handler = ErrorHandler(bot, admin_group_id, admin_topic_id)
    return await handler.handle_telegram_error(error, context)


async def handle_ocr_error(
    error: Exception,
    bot: Bot,
    admin_group_id: int,
    context: Optional[Dict[str, Any]] = None,
    admin_topic_id: Optional[int] = None,
) -> Optional[str]:
    """
    Convenience function to handle OCR errors.

    Args:
        error: The exception that occurred
        bot: Telegram Bot instance
        admin_group_id: Admin group ID for notifications
        context: Optional context information
        admin_topic_id: Optional topic ID for notifications

    Returns:
        User-friendly error message to display, or None
    """
    handler = ErrorHandler(bot, admin_group_id, admin_topic_id)
    return await handler.handle_ocr_error(error, context)


async def handle_backend_error(
    error: Exception,
    bot: Bot,
    admin_group_id: int,
    context: Optional[Dict[str, Any]] = None,
    admin_topic_id: Optional[int] = None,
) -> bool:
    """
    Convenience function to handle backend API errors.

    Args:
        error: The exception that occurred
        bot: Telegram Bot instance
        admin_group_id: Admin group ID for notifications
        context: Optional context information
        admin_topic_id: Optional topic ID for notifications

    Returns:
        True if operation should be retried, False otherwise
    """
    handler = ErrorHandler(bot, admin_group_id, admin_topic_id)
    return await handler.handle_backend_error(error, context)
