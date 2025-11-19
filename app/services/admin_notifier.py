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
                # exchange_rate for buy is stored as MMK per THB (e.g., 125.78)
                sent_amount = order.thb_amount or 0
                received_amount = order.mmk_amount or 0
                sent_currency = "THB"
                received_currency = "MMK"
                operation = "Buy"
                # Display rate as MMK per THB (already in correct format)
                if order.exchange_rate and order.exchange_rate > 0:
                    display_rate = order.exchange_rate
                else:
                    # Fallback: calculate from amounts if rate is missing
                    display_rate = received_amount / sent_amount if sent_amount > 0 else 0
                calculation = f"{sent_amount:,.2f} × {display_rate:.2f} = {received_amount:,.2f}"
            else:
                # Sell: user sends MMK, receives THB
                # exchange_rate for sell is stored as THB per MMK (e.g., 0.0081)
                # Need to invert to display as MMK per THB (e.g., 123.6)
                sent_amount = order.mmk_amount or 0
                received_amount = order.thb_amount or 0
                sent_currency = "MMK"
                received_currency = "THB"
                operation = "Sell"
                # Display rate as MMK per THB (invert the stored rate)
                if order.exchange_rate and order.exchange_rate > 0:
                    display_rate = 1 / order.exchange_rate
                else:
                    # Fallback: calculate from amounts if rate is missing
                    display_rate = sent_amount / received_amount if received_amount > 0 else 0
                calculation = f"{sent_amount:,.2f} ÷ {display_rate:.2f} = {received_amount:,.2f}"

            # Format user identification
            user_info = user_name or user_telegram_id

            # Format message - simplified single message format
            # Format: {order_id}\n{operation} {calculation}\n{user_bank_info}
            message = ""
            
            # Add order ID if available
            if order_id:
                message += f"{order_id}\n"
            
            # Add operation and calculation
            message += f"{operation} {calculation}\n"

            # Add user bank info if available
            if order.user_bank_info:
                message += f"{order.user_bank_info}"

            logger.info(
                f"Sending {order.order_type} order notification to topic {topic_id} "
                f"for user {user_telegram_id}"
            )

            # Send receipt image with caption containing all info (SINGLE MESSAGE)
            if order.receipt_file_ids and len(order.receipt_file_ids) > 0:
                # Send first receipt with caption
                await self.bot.send_photo(
                    chat_id=self.admin_group_id,
                    message_thread_id=topic_id,
                    photo=order.receipt_file_ids[0],
                    caption=message,
                )
                
                # Send additional receipts if any (without caption)
                if len(order.receipt_file_ids) > 1:
                    for file_id in order.receipt_file_ids[1:]:
                        await self.bot.send_photo(
                            chat_id=self.admin_group_id,
                            message_thread_id=topic_id,
                            photo=file_id,
                        )
            else:
                # No receipt image, send as text only
                await self.bot.send_message(
                    chat_id=self.admin_group_id, 
                    message_thread_id=topic_id, 
                    text=message
                )

            # Send user's bank QR code if provided (separate message)
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
        CSTZ (AYA W) - 16,000,000.00
        CSTZ (AYA) - 12,582,879.00
        THB
        TZH (Kbank) - 15,000.00
        MMN (SCB) - 46,761.82

        Args:
            myanmar_banks: List of Myanmar bank accounts
            thai_banks: List of Thai bank accounts
            balances: Optional dict mapping bank names/IDs to current balances

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
                        bank_id = bank.get("id")
                    else:
                        display = (
                            bank.display_name
                            if hasattr(bank, "display_name") and bank.display_name
                            else bank.bank_name
                        )
                        bank_name = bank.bank_name
                        bank_id = bank.id if hasattr(bank, "id") else None

                    # Try to get balance by bank_name first, then by id
                    balance = 0.0
                    if balances:
                        balance = balances.get(bank_name, 0.0)
                        if balance == 0.0 and bank_id:
                            balance = balances.get(str(bank_id), 0.0)
                    
                    # Format: DisplayName - Balance with 2 decimal places
                    message += f"{display} - {balance:,.2f}\n"
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
                        bank_id = bank.get("id")
                    else:
                        display = (
                            bank.display_name
                            if hasattr(bank, "display_name") and bank.display_name
                            else bank.bank_name
                        )
                        bank_name = bank.bank_name
                        bank_id = bank.id if hasattr(bank, "id") else None

                    # Try to get balance by bank_name first, then by id
                    balance = 0.0
                    if balances:
                        balance = balances.get(bank_name, 0.0)
                        if balance == 0.0 and bank_id:
                            balance = balances.get(str(bank_id), 0.0)
                    
                    # Format: DisplayName - Balance with 2 decimal places
                    message += f"{display} - {balance:,.2f}\n"
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
