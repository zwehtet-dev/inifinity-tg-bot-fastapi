"""
User notification service for sending success messages and order confirmations to users.
"""

import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from app.services.state_manager import StateManager

logger = logging.getLogger(__name__)


class UserNotificationError(Exception):
    """Base exception for user notification errors."""

    pass


class UserNotifier:
    """
    Service for sending notifications to users.
    Handles success messages, order confirmations, and admin receipt delivery.
    """

    def __init__(self, bot: Bot, state_manager: StateManager):
        """
        Initialize user notifier.

        Args:
            bot: Telegram Bot instance
            state_manager: StateManager instance for clearing user states
        """
        self.bot = bot
        self.state_manager = state_manager
        logger.info("UserNotifier initialized")

    async def send_success_message(
        self,
        chat_id: int,
        user_id: int,
        order_id: str,
        order_type: str,
        sent_amount: float,
        sent_currency: str,
        received_amount: float,
        received_currency: str,
        exchange_rate: float = 0,
        admin_receipt_file_id: Optional[str] = None,
    ) -> bool:
        """
        Send success message to user after order completion.

        Args:
            chat_id: User's chat ID
            user_id: User's Telegram ID
            order_id: Completed order ID
            order_type: Order type ("buy" or "sell")
            sent_amount: Amount user sent
            sent_currency: Currency user sent (THB or MMK)
            received_amount: Amount user will receive
            received_currency: Currency user will receive (MMK or THB)
            exchange_rate: Exchange rate used for the transaction
            admin_receipt_file_id: Optional Telegram file ID of admin confirmation receipt

        Returns:
            True if message sent successfully, False otherwise

        Raises:
            UserNotificationError: If notification fails
        """
        try:
            # Format success message with exchange rate calculation
            # BUY: User sends THB, receives MMK -> THB × rate = MMK
            # SELL: User sends MMK, receives THB -> MMK ÷ rate = THB
            if order_type == "buy":
                # Buy: THB × rate = MMK
                # exchange_rate is MMK per THB (e.g., 123.76)
                # Example: Buy 1,620.00 × 123.76 = 200,471.20
                message = (
                    f"Buy {sent_amount:,.2f} × {exchange_rate:.2f} = "
                    f"{received_amount:,.2f}"
                )
            else:
                # Sell: MMK ÷ rate = THB
                # exchange_rate might be THB per MMK (e.g., 0.0081)
                # We need to show MMK per THB (e.g., 123.76)
                # So invert if rate < 1
                display_rate = 1 / exchange_rate if exchange_rate > 0 and exchange_rate < 1 else exchange_rate
                # Example: Sell 4,950,500.00 ÷ 123.76 = 40,000.81
                message = (
                    f"Sell {sent_amount:,.2f} ÷ {display_rate:.2f} = "
                    f"{received_amount:,.2f}"
                )

            logger.info(
                f"📤 Sending success notification to user {user_id}",
                extra={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "order_id": order_id,
                    "order_type": order_type,
                    "notification_text": message,
                },
            )

            # Send admin receipt with calculation as caption (single message)
            if admin_receipt_file_id and admin_receipt_file_id.strip():
                try:
                    logger.info(f"📸 Sending admin receipt with calculation to user {user_id}")
                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=admin_receipt_file_id,
                        caption=message,  # Calculation as caption
                    )
                    logger.info(
                        f"✅ Sent admin receipt with calculation to user {user_id}",
                        extra={"user_id": user_id, "order_id": order_id},
                    )
                except Exception as receipt_error:
                    logger.error(
                        f"❌ Failed to send admin receipt: {receipt_error}",
                        extra={
                            "user_id": user_id,
                            "order_id": order_id,
                            "receipt_file_id": admin_receipt_file_id,
                        },
                        exc_info=True,
                    )
                    # Fallback: send as text message if photo fails
                    try:
                        await self.bot.send_message(chat_id=chat_id, text=message)
                        logger.info(f"✅ Sent calculation as text (fallback) to user {user_id}")
                    except Exception as text_error:
                        logger.error(f"❌ Failed to send text message: {text_error}")
                        raise
            else:
                # No receipt - send as text message
                try:
                    await self.bot.send_message(chat_id=chat_id, text=message)
                    logger.info(f"✅ Sent calculation as text to user {user_id}")
                except Exception as msg_error:
                    logger.error(
                        f"❌ Failed to send success message: {msg_error}", exc_info=True
                    )
                    raise

            # Clear user conversation state
            self.state_manager.clear_state(user_id)
            logger.info(
                f"Cleared conversation state for user {user_id}",
                extra={"user_id": user_id},
            )

            logger.info(
                f"Successfully sent success message to user {user_id}",
                extra={"user_id": user_id, "order_id": order_id},
            )
            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error sending success message to user {user_id}: {e}",
                extra={"user_id": user_id, "order_id": order_id},
            )
            raise UserNotificationError(f"Failed to send success message: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error sending success message to user {user_id}: {e}",
                extra={"user_id": user_id, "order_id": order_id},
                exc_info=True,
            )
            raise UserNotificationError(f"Unexpected error: {e}")

    async def send_order_rejected_message(
        self, chat_id: int, user_id: int, order_id: str, reason: Optional[str] = None
    ) -> bool:
        """
        Send rejection message to user when order is declined.

        Args:
            chat_id: User's chat ID
            user_id: User's Telegram ID
            order_id: Rejected order ID
            reason: Optional reason for rejection

        Returns:
            True if message sent successfully, False otherwise

        Raises:
            UserNotificationError: If notification fails
        """
        try:
            message = f"❌ **Order Declined**\n\n" f"📋 Order ID: `{order_id}`\n\n"

            if reason:
                message += f"Reason: {reason}\n\n"

            message += (
                "Please contact support if you have any questions.\n\n"
                "To start a new transaction, use /start command."
            )

            logger.info(
                f"Sending rejection message to user {user_id}",
                extra={"user_id": user_id, "chat_id": chat_id, "order_id": order_id},
            )

            await self.bot.send_message(
                chat_id=chat_id, text=message, parse_mode="Markdown"
            )

            # Clear user conversation state
            self.state_manager.clear_state(user_id)
            logger.info(
                f"Cleared conversation state for user {user_id} after rejection",
                extra={"user_id": user_id},
            )

            logger.info(
                f"Successfully sent rejection message to user {user_id}",
                extra={"user_id": user_id, "order_id": order_id},
            )
            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error sending rejection message to user {user_id}: {e}",
                extra={"user_id": user_id, "order_id": order_id},
            )
            raise UserNotificationError(f"Failed to send rejection message: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error sending rejection message to user {user_id}: {e}",
                extra={"user_id": user_id, "order_id": order_id},
                exc_info=True,
            )
            raise UserNotificationError(f"Unexpected error: {e}")

    async def send_error_message(
        self, chat_id: int, user_id: int, error_message: str
    ) -> bool:
        """
        Send error message to user.

        Args:
            chat_id: User's chat ID
            user_id: User's Telegram ID
            error_message: Error message to send

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            message = (
                f"⚠️ **Error**\n\n"
                f"{error_message}\n\n"
                f"Please try again or contact support if the issue persists."
            )

            logger.info(
                f"Sending error message to user {user_id}",
                extra={"user_id": user_id, "chat_id": chat_id},
            )

            await self.bot.send_message(
                chat_id=chat_id, text=message, parse_mode="Markdown"
            )

            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error sending error message to user {user_id}: {e}",
                extra={"user_id": user_id},
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending error message to user {user_id}: {e}",
                extra={"user_id": user_id},
                exc_info=True,
            )
            return False

    async def send_instructions(self, chat_id: int, instructions: str) -> bool:
        """
        Send instructions or informational message to user.

        Args:
            chat_id: User's chat ID
            instructions: Instructions text to send

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id, text=instructions, parse_mode="Markdown"
            )

            logger.info(
                f"Sent instructions to chat {chat_id}", extra={"chat_id": chat_id}
            )
            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error sending instructions to chat {chat_id}: {e}",
                extra={"chat_id": chat_id},
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending instructions to chat {chat_id}: {e}",
                extra={"chat_id": chat_id},
                exc_info=True,
            )
            return False
