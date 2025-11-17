"""
Backend message polling service for receiving admin messages.

Polls the backend for unseen messages and sends them to users.
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.logging_config import get_logger
from app.services.backend_client import BackendClient


logger = get_logger(__name__)


class MessagePoller:
    """
    Service for polling backend for unseen messages and sending them to users.

    Runs as a background task that:
    - Polls backend every 5 seconds for new messages
    - Reconstructs inline keyboards from button data
    - Downloads and sends images to users
    - Handles media groups
    """

    def __init__(self, bot: Bot, backend_client: BackendClient, backend_url: str):
        """
        Initialize the message poller.

        Args:
            bot: Telegram Bot instance
            backend_client: BackendClient instance for API communication
            backend_url: Base URL of the backend (for image URLs)
        """
        self.bot = bot
        self.backend_client = backend_client
        self.backend_url = backend_url.rstrip("/")
        self._polling_tasks: Dict[int, asyncio.Task] = {}
        logger.info("MessagePoller initialized")

    def start_polling(self, telegram_id: str, chat_id: int):
        """
        Start polling for messages for a specific user.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
        """
        # Check if already polling for this chat
        if chat_id in self._polling_tasks:
            task = self._polling_tasks[chat_id]
            if not task.done():
                logger.debug(f"Already polling for chat_id={chat_id}")
                return

        # Start new polling task
        task = asyncio.create_task(self._poll_loop(telegram_id, chat_id))
        self._polling_tasks[chat_id] = task

        logger.info(
            "Started message polling",
            extra={"telegram_id": telegram_id, "chat_id": chat_id},
        )

    def stop_polling(self, chat_id: int):
        """
        Stop polling for messages for a specific user.

        Args:
            chat_id: Chat ID
        """
        if chat_id in self._polling_tasks:
            task = self._polling_tasks[chat_id]
            if not task.done():
                task.cancel()
            del self._polling_tasks[chat_id]

            logger.info("Stopped message polling", extra={"chat_id": chat_id})

    async def _poll_loop(self, telegram_id: str, chat_id: int):
        """
        Main polling loop that runs continuously.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
        """
        logger.info(
            "Polling loop started",
            extra={"telegram_id": telegram_id, "chat_id": chat_id},
        )

        try:
            while True:
                try:
                    # Poll for messages
                    messages = await self.poll_messages(telegram_id, chat_id)

                    # Send messages to user
                    if messages:
                        await self.send_polled_messages(chat_id, messages)

                    # Wait 5 seconds before next poll
                    await asyncio.sleep(5)

                except asyncio.CancelledError:
                    logger.info("Polling loop cancelled", extra={"chat_id": chat_id})
                    break

                except Exception as e:
                    logger.error(
                        "Error in polling loop",
                        extra={
                            "telegram_id": telegram_id,
                            "chat_id": chat_id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )
                    # Continue polling despite errors
                    await asyncio.sleep(5)

        finally:
            logger.info("Polling loop ended", extra={"chat_id": chat_id})

    async def poll_messages(
        self, telegram_id: str, chat_id: int
    ) -> List[Dict[str, Any]]:
        """
        Poll backend for unseen messages.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID

        Returns:
            List of message dictionaries
        """
        try:
            messages = await self.backend_client.poll_messages(
                telegram_id=telegram_id, chat_id=chat_id
            )

            if messages:
                logger.debug(
                    f"Polled {len(messages)} messages",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )

            return messages

        except Exception as e:
            logger.error(
                "Error polling messages",
                extra={"telegram_id": telegram_id, "chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            return []

    async def send_polled_messages(self, chat_id: int, messages: List[Dict[str, Any]]):
        """
        Send polled messages to user.

        Args:
            chat_id: Chat ID to send messages to
            messages: List of message dictionaries from backend
        """
        for msg in messages:
            try:
                await self.send_polled_message(chat_id, msg)
            except Exception as e:
                logger.error(
                    "Error sending polled message",
                    extra={
                        "chat_id": chat_id,
                        "message_id": msg.get("id"),
                        "error": str(e),
                    },
                    exc_info=True,
                )

    async def send_polled_message(self, chat_id: int, message: Dict[str, Any]):
        """
        Send a single polled message to user with inline keyboard reconstruction.

        Args:
            chat_id: Chat ID to send message to
            message: Message dictionary from backend
        """
        content = message.get("content", "")
        buttons_data = message.get("buttons")
        images = message.get("image")

        # Reconstruct inline keyboard if buttons exist
        reply_markup = None
        if buttons_data:
            try:
                # Parse buttons JSON if it's a string
                if isinstance(buttons_data, str):
                    buttons = json.loads(buttons_data)
                else:
                    buttons = buttons_data

                # Create inline keyboard
                # Format: {callback_data: button_text}
                keyboard = [
                    [InlineKeyboardButton(text=text, callback_data=key)]
                    for key, text in buttons.items()
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                logger.debug(
                    "Reconstructed inline keyboard",
                    extra={"chat_id": chat_id, "button_count": len(buttons)},
                )

            except Exception as e:
                logger.error(
                    "Error parsing buttons",
                    extra={"chat_id": chat_id, "error": str(e)},
                    exc_info=True,
                )

        # Handle images
        if images:
            await self._send_message_with_images(
                chat_id=chat_id,
                content=content,
                images=images,
                reply_markup=reply_markup,
            )
        else:
            # Send text-only message
            await self._send_text_message(
                chat_id=chat_id, text=content, reply_markup=reply_markup
            )

    async def _send_message_with_images(
        self,
        chat_id: int,
        content: str,
        images: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        """
        Send message with images (handles single and multiple images).

        Args:
            chat_id: Chat ID
            content: Message content/caption
            images: Comma-separated image paths
            reply_markup: Optional inline keyboard
        """
        # Parse image list (comma-separated)
        image_list = [img.strip() for img in images.split(",") if img.strip()]

        logger.debug(
            "Sending message with images",
            extra={"chat_id": chat_id, "image_count": len(image_list)},
        )

        # Download and send each image
        for idx, img_path in enumerate(image_list):
            try:
                # Construct full URL if needed
                if not img_path.startswith("http"):
                    img_url = f"{self.backend_url}/{img_path}"
                else:
                    img_url = img_path

                # Download image
                img_response = await self.backend_client.client.get(img_url)

                if img_response.status_code == 200:
                    img_bytes = img_response.content

                    # Send photo with caption on first image, reply_markup on last
                    caption = content if idx == 0 and content else None
                    markup = reply_markup if idx == len(image_list) - 1 else None

                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=img_bytes,
                        caption=caption,
                        reply_markup=markup,
                    )

                    logger.debug(
                        "Image sent successfully",
                        extra={"chat_id": chat_id, "image_index": idx},
                    )
                else:
                    logger.error(
                        "Failed to download image",
                        extra={
                            "chat_id": chat_id,
                            "img_url": img_url,
                            "status_code": img_response.status_code,
                        },
                    )

            except TelegramError as e:
                logger.error(
                    "Telegram error sending image",
                    extra={"chat_id": chat_id, "image_index": idx, "error": str(e)},
                    exc_info=True,
                )

            except Exception as e:
                logger.error(
                    "Error sending image",
                    extra={"chat_id": chat_id, "image_index": idx, "error": str(e)},
                    exc_info=True,
                )

    async def _send_text_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        """
        Send text-only message.

        Args:
            chat_id: Chat ID
            text: Message text
            reply_markup: Optional inline keyboard
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=reply_markup
            )

            logger.debug("Text message sent successfully", extra={"chat_id": chat_id})

        except TelegramError as e:
            logger.error(
                "Telegram error sending text message",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )

        except Exception as e:
            logger.error(
                "Error sending text message",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )

    def get_active_polling_count(self) -> int:
        """
        Get the number of active polling tasks.

        Returns:
            Number of active polling tasks
        """
        active_count = sum(
            1 for task in self._polling_tasks.values() if not task.done()
        )
        return active_count

    async def stop_all_polling(self):
        """Stop all active polling tasks."""
        logger.info("Stopping all polling tasks")

        for chat_id in list(self._polling_tasks.keys()):
            self.stop_polling(chat_id)

        # Wait for all tasks to complete
        if self._polling_tasks:
            await asyncio.gather(*self._polling_tasks.values(), return_exceptions=True)

        self._polling_tasks.clear()
        logger.info("All polling tasks stopped")
