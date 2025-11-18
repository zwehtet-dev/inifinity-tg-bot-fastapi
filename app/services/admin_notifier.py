"""
Admin notification service for sending order notifications and balance updates to admin group topics.
"""

import logging
from typing import List, Optional, Dict, Any
from telegram import Bot, InputMediaPhoto
from telegram.error import TelegramError

from app.models.order import OrderData
from app.models.receipt import BankAccount

logger = logging.getLogger(__name__)


class AdminNotificationError(Exception):
    """Base exception for admin notification errors."""

    pass


class AdminNotifier:
    """
    Service for sending notifications to admin Telegram group topics.
    Handles order notifications (Buy/Sell topics) and balance notifications (Balance topic).
    """

    def __init__(
        self,
        bot: Bot,
        admin_group_id: int,
        buy_topic_id: int,
        sell_topic_id: int,
        balance_topic_id: int,
    ):
        """
        Initialize admin notifier with bot and topic configuration.

        Args:
            bot: Telegram Bot instance
            admin_group_id: Telegram group ID for admin notifications
            buy_topic_id: Topic ID for buy orders
            sell_topic_id: Topic ID for sell orders
            balance_topic_id: Topic ID for balance updates
        """
        self.bot = bot
        self.admin_group_id = admin_group_id
        self.buy_topic_id = buy_topic_id
        self.sell_topic_id = sell_topic_id
        self.balance_topic_id = balance_topic_id

    async def send_order_notification(
        self, order: OrderData, user_telegram_id: str, user_name: Optional[str] = None, order_id: Optional[str] = None
    ) -> bool:
        """
        Send order notification to appropriate topic (Buy or Sell) based on order type.
        
        NO BUTTONS - Staff replies directly to this message with:
        - Receipt photo (for approval)
        - "Reject: {reason}" (for rejection)
        - "Complain: {message}" (for complaint)

        Format: 
        🧾 [User sent receipt]
        
        📝 Order: {order_id}
        📋 Order Type: {BUY/SELL}
        👤 User: {name}
        💰 {operation}: {sent_amount} {currency} × {rate} = {received_amount} {currency}
        🏦 User Bank: {bank_info}

        Args:
            order: OrderData containing order details
            user_telegram_id: User's Telegram ID
            user_name: Optional user's display name
            order_id: Optional order ID to include in notification

        Returns:
            True if notification sent successfully, False otherwise

        Raises:
            AdminNotificationError: If notification fails after retries
        """
        try:
            # Determine which topic to use based on order type
            topic_id = (
                self.buy_topic_id if order.order_type == "buy" else self.sell_topic_id
            )

            # Calculate amounts and format operation
            if order.order_type == "buy":
                # Buy: user sends THB, receives MMK
                sent_amount = order.thb_amount or 0
                received_amount = sent_amount * (order.exchange_rate or 0)
                sent_currency = "THB"
                received_currency = "MMK"
                operation = "Buy"
                calculation = f"{sent_amount:,.2f} × {order.exchange_rate:.2f} = {received_amount:,.2f}"
            else:
                # Sell: user sends MMK, receives THB
                sent_amount = order.mmk_amount or 0
                received_amount = sent_amount / (order.exchange_rate or 1)
                sent_currency = "MMK"
                received_currency = "THB"
                operation = "Sell"
                calculation = f"{sent_amount:,.2f} ÷ {order.exchange_rate:.2f} = {received_amount:,.2f}"

            # Format user identification
            user_info = user_name or user_telegram_id

            # Format message - clean and simple
            message = "🧾 [User sent receipt]\n\n"
            
            # Add order ID if available
            if order_id:
                message += f"📝 Order: {order_id}\n"
            
            message += (
                f"📋 Order Type: {order.order_type.upper()}\n"
                f"👤 User: {user_info}\n"
                f"💰 {operation} {calculation}\n"
            )

            # Add user bank info if available
            if order.user_bank_info:
                message += f"🏦 User Bank: {order.user_bank_info}\n"

            logger.info(
                f"Sending {order.order_type} order notification to topic {topic_id} "
                f"for user {user_telegram_id}"
            )

            # Send text message first (NO BUTTONS - staff replies directly)
            sent_message = await self.bot.send_message(
                chat_id=self.admin_group_id, message_thread_id=topic_id, text=message
            )

            # Send receipt images if available
            if order.receipt_file_ids:
                await self._send_receipt_images(
                    topic_id=topic_id,
                    file_ids=order.receipt_file_ids,
                    caption=f"Receipt(s) from {user_info}",
                )

            # Send user's bank QR code if provided
            if order.user_bank_qr_file_id:
                await self.bot.send_photo(
                    chat_id=self.admin_group_id,
                    message_thread_id=topic_id,
                    photo=order.user_bank_qr_file_id,
                    caption="🏦 User's Bank QR Code",
                )
                logger.info(f"Sent user's bank QR code to topic {topic_id}")

            logger.info(f"Successfully sent order notification to topic {topic_id}")
            return True

        except TelegramError as e:
            logger.error(f"Telegram error sending order notification: {e}")
            raise AdminNotificationError(f"Failed to send order notification: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error sending order notification: {e}", exc_info=True
            )
            raise AdminNotificationError(f"Unexpected error: {e}")

    async def _send_receipt_images(
        self, topic_id: int, file_ids: List[str], caption: Optional[str] = None
    ) -> None:
        """
        Send receipt images to admin group topic.
        Handles single or multiple images (media group).

        Args:
            topic_id: Topic ID to send to
            file_ids: List of Telegram file IDs
            caption: Optional caption for the images
        """
        try:
            if len(file_ids) == 1:
                # Single image
                await self.bot.send_photo(
                    chat_id=self.admin_group_id,
                    message_thread_id=topic_id,
                    photo=file_ids[0],
                    caption=caption,
                )
            else:
                # Multiple images as media group
                media = []
                for idx, file_id in enumerate(file_ids):
                    # Add caption only to first image
                    img_caption = caption if idx == 0 else None
                    media.append(InputMediaPhoto(media=file_id, caption=img_caption))

                await self.bot.send_media_group(
                    chat_id=self.admin_group_id, message_thread_id=topic_id, media=media
                )

            logger.info(f"Sent {len(file_ids)} receipt image(s) to topic {topic_id}")

        except TelegramError as e:
            logger.error(f"Error sending receipt images: {e}")
            raise

    async def send_balance_notification(
        self,
        myanmar_banks: List[BankAccount],
        thai_banks: List[BankAccount],
        balances: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Send balance update notification to Balance topic.

        Format:
        MMK
        MMN - 2000000 Khin Oo - 0
        THB
        MMN - 40265
        PPK - 31108
        NDT - 3805

        Args:
            myanmar_banks: List of Myanmar bank accounts
            thai_banks: List of Thai bank accounts
            balances: Optional dict mapping bank names to current balances

        Returns:
            True if notification sent successfully, False otherwise

        Raises:
            AdminNotificationError: If notification fails
        """
        try:
            # Build balance message in the required format
            message = "MMK\n"

            # Myanmar banks section (MMK)
            if myanmar_banks:
                for bank in myanmar_banks:
                    # Banks can be either dict or object, handle both
                    if isinstance(bank, dict):
                        display = bank.get("display_name") or bank.get(
                            "bank_name", "Unknown"
                        )
                        bank_name = bank.get("bank_name", "")
                    else:
                        display = (
                            bank.display_name
                            if hasattr(bank, "display_name") and bank.display_name
                            else bank.bank_name
                        )
                        bank_name = bank.bank_name

                    balance = balances.get(bank_name, 0.0) if balances else 0.0
                    # Format: DisplayName - Balance
                    message += f"{display} - {balance:,.0f}\n"
            else:
                message += "No Myanmar banks configured\n"

            # Thai banks section (THB)
            message += "THB\n"
            if thai_banks:
                for bank in thai_banks:
                    # Banks can be either dict or object, handle both
                    if isinstance(bank, dict):
                        display = bank.get("display_name") or bank.get(
                            "bank_name", "Unknown"
                        )
                        bank_name = bank.get("bank_name", "")
                    else:
                        display = (
                            bank.display_name
                            if hasattr(bank, "display_name") and bank.display_name
                            else bank.bank_name
                        )
                        bank_name = bank.bank_name

                    balance = balances.get(bank_name, 0.0) if balances else 0.0
                    # Format: DisplayName - Balance
                    message += f"{display} - {balance:,.0f}\n"
            else:
                message += "No Thai banks configured\n"

            logger.info("Sending balance notification to Balance topic")
            logger.info(f"Balance message preview:\n{message}")

            # Send to Balance topic
            await self.bot.send_message(
                chat_id=self.admin_group_id,
                message_thread_id=self.balance_topic_id,
                text=message,
            )

            logger.info("Successfully sent balance notification")
            return True

        except TelegramError as e:
            logger.error(f"Telegram error sending balance notification: {e}")
            raise AdminNotificationError(f"Failed to send balance notification: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error sending balance notification: {e}", exc_info=True
            )
            raise AdminNotificationError(f"Unexpected error: {e}")

    async def send_error_notification(
        self, error_message: str, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send error notification to admin group (Buy topic by default).

        Args:
            error_message: Error message to send
            context: Optional context information (user_id, order_id, etc.)

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            message = f"⚠️ **Error Alert**\n\n{error_message}\n"

            if context:
                message += "\n**Context:**\n"
                for key, value in context.items():
                    message += f"  • {key}: {value}\n"

            await self.bot.send_message(
                chat_id=self.admin_group_id,
                message_thread_id=self.buy_topic_id,  # Default to Buy topic
                text=message,
                parse_mode="Markdown",
            )

            logger.info("Sent error notification to admin group")
            return True

        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False
