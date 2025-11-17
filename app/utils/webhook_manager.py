"""
Webhook management utilities for Telegram bot.
"""

from urllib.parse import urlparse
from telegram import Bot
from telegram.error import TelegramError

from app.logging_config import get_logger


logger = get_logger(__name__)


class WebhookManager:
    """
    Manages Telegram webhook registration and deletion.
    """

    def __init__(self, bot: Bot, webhook_url: str, webhook_secret: str):
        """
        Initialize webhook manager.

        Args:
            bot: Telegram Bot instance
            webhook_url: Public URL for webhook endpoint
            webhook_secret: Secret token for webhook validation
        """
        self.bot = bot
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret

    def validate_webhook_url(self, url: str) -> tuple[bool, str]:
        """
        Validate webhook URL format and requirements.

        Telegram webhook requirements:
        - Must use HTTPS (except localhost for testing)
        - Must be a valid URL
        - Must not contain query parameters
        - Port must be 443, 80, 88, or 8443

        Args:
            url: Webhook URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "Webhook URL cannot be empty"

        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ["https", "http"]:
                return False, "Webhook URL must use HTTP or HTTPS protocol"

            # HTTPS required for production (allow HTTP for localhost testing)
            if parsed.scheme == "http" and parsed.hostname not in [
                "localhost",
                "127.0.0.1",
            ]:
                return (
                    False,
                    "Webhook URL must use HTTPS (HTTP only allowed for localhost)",
                )

            # Check hostname
            if not parsed.hostname:
                return False, "Webhook URL must have a valid hostname"

            # Check for query parameters (not allowed by Telegram)
            if parsed.query:
                return False, "Webhook URL cannot contain query parameters"

            # Check port (Telegram only allows specific ports)
            if parsed.port:
                allowed_ports = [443, 80, 88, 8443]
                if parsed.port not in allowed_ports:
                    return False, f"Webhook port must be one of {allowed_ports}"

            return True, ""

        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

    async def register_webhook(self) -> bool:
        """
        Register webhook with Telegram.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate webhook URL first
            is_valid, error_msg = self.validate_webhook_url(self.webhook_url)
            if not is_valid:
                logger.error(
                    "Invalid webhook URL",
                    extra={"error": error_msg, "url": self.webhook_url},
                )
                return False

            # Set webhook with secret token
            success = await self.bot.set_webhook(
                url=self.webhook_url,
                secret_token=self.webhook_secret,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=False,
            )

            if success:
                logger.info(
                    "Webhook registered successfully",
                    extra={"webhook_url": self.webhook_url},
                )

                # Verify webhook info
                webhook_info = await self.bot.get_webhook_info()
                logger.info(
                    "Webhook info",
                    extra={
                        "url": webhook_info.url,
                        "pending_update_count": webhook_info.pending_update_count,
                        "has_custom_certificate": webhook_info.has_custom_certificate,
                    },
                )
            else:
                logger.error("Failed to register webhook")

            return success

        except TelegramError as e:
            logger.error(
                "Telegram error during webhook registration",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error during webhook registration",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def delete_webhook(self) -> bool:
        """
        Delete webhook from Telegram.

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.bot.delete_webhook(drop_pending_updates=False)

            if success:
                logger.info("Webhook deleted successfully")
            else:
                logger.error("Failed to delete webhook")

            return success

        except TelegramError as e:
            logger.error(
                "Telegram error during webhook deletion",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error during webhook deletion",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    async def get_webhook_info(self):
        """
        Get current webhook information.

        Returns:
            WebhookInfo object or None
        """
        try:
            webhook_info = await self.bot.get_webhook_info()
            logger.info(
                "Retrieved webhook info",
                extra={
                    "url": webhook_info.url,
                    "pending_update_count": webhook_info.pending_update_count,
                    "last_error_date": webhook_info.last_error_date,
                    "last_error_message": webhook_info.last_error_message,
                },
            )
            return webhook_info

        except Exception as e:
            logger.error(
                "Error retrieving webhook info", extra={"error": str(e)}, exc_info=True
            )
            return None
