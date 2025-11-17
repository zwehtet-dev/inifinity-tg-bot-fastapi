"""
Message submission service for persisting user and bot messages to backend.

Handles message persistence including text, photos, buttons, and media groups.
"""

from typing import Optional, List, Dict, Any

from app.logging_config import get_logger
from app.services.backend_client import BackendClient


logger = get_logger(__name__)


class MessageService:
    """
    Service for submitting user and bot messages to the backend for persistence.

    Handles message submission with support for:
    - Text messages
    - Photo uploads (single and media groups)
    - Inline keyboard buttons
    - User and bot message differentiation
    """

    def __init__(self, backend_client: BackendClient):
        """
        Initialize the message service.

        Args:
            backend_client: BackendClient instance for API communication
        """
        self.backend_client = backend_client
        logger.info("MessageService initialized")

    async def submit_user_message(
        self,
        telegram_id: str,
        chat_id: int,
        content: str = "",
        chosen_option: str = "",
        image_file_ids: Optional[List[str]] = None,
        buttons: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Submit a user message to the backend.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
            content: Message content/text
            chosen_option: Selected option from buttons (if any)
            image_file_ids: List of Telegram file IDs for images
            buttons: Button data as dict (for messages with inline keyboards)

        Returns:
            True if submission successful, False otherwise
        """
        try:
            logger.debug(
                "Submitting user message",
                extra={
                    "telegram_id": telegram_id,
                    "chat_id": chat_id,
                    "has_images": bool(image_file_ids),
                    "has_buttons": bool(buttons),
                    "content_length": len(content),
                },
            )

            result = await self.backend_client.submit_message(
                telegram_id=telegram_id,
                chat_id=chat_id,
                content=content,
                chosen_option=chosen_option,
                image_file_ids=image_file_ids,
                from_bot=False,
                from_backend=False,
                buttons=buttons,
            )

            if result:
                logger.info(
                    "User message submitted successfully",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )
                return True
            else:
                logger.warning(
                    "Failed to submit user message",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )
                return False

        except Exception as e:
            logger.error(
                "Error submitting user message",
                extra={"telegram_id": telegram_id, "chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            return False

    async def submit_bot_message(
        self,
        telegram_id: str,
        chat_id: int,
        content: str = "",
        image_file_ids: Optional[List[str]] = None,
        buttons: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Submit a bot message to the backend.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
            content: Message content/text
            image_file_ids: List of Telegram file IDs for images
            buttons: Button data as dict (for messages with inline keyboards)

        Returns:
            True if submission successful, False otherwise
        """
        try:
            logger.debug(
                "Submitting bot message",
                extra={
                    "telegram_id": telegram_id,
                    "chat_id": chat_id,
                    "has_images": bool(image_file_ids),
                    "has_buttons": bool(buttons),
                    "content_length": len(content),
                },
            )

            result = await self.backend_client.submit_message(
                telegram_id=telegram_id,
                chat_id=chat_id,
                content=content,
                chosen_option="",
                image_file_ids=image_file_ids,
                from_bot=True,
                from_backend=False,
                buttons=buttons,
            )

            if result:
                logger.info(
                    "Bot message submitted successfully",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )
                return True
            else:
                logger.warning(
                    "Failed to submit bot message",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )
                return False

        except Exception as e:
            logger.error(
                "Error submitting bot message",
                extra={"telegram_id": telegram_id, "chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            return False

    async def submit_media_group(
        self,
        telegram_id: str,
        chat_id: int,
        content: str,
        image_file_ids: List[str],
        from_bot: bool = False,
    ) -> bool:
        """
        Submit a media group (multiple photos) as a single message.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
            content: Message content/caption
            image_file_ids: List of Telegram file IDs for all images in the group
            from_bot: Whether this is a bot message

        Returns:
            True if submission successful, False otherwise
        """
        try:
            logger.debug(
                "Submitting media group",
                extra={
                    "telegram_id": telegram_id,
                    "chat_id": chat_id,
                    "image_count": len(image_file_ids),
                    "from_bot": from_bot,
                },
            )

            result = await self.backend_client.submit_message(
                telegram_id=telegram_id,
                chat_id=chat_id,
                content=content,
                chosen_option="",
                image_file_ids=image_file_ids,
                from_bot=from_bot,
                from_backend=False,
                buttons=None,
            )

            if result:
                logger.info(
                    "Media group submitted successfully",
                    extra={
                        "telegram_id": telegram_id,
                        "chat_id": chat_id,
                        "image_count": len(image_file_ids),
                    },
                )
                return True
            else:
                logger.warning(
                    "Failed to submit media group",
                    extra={"telegram_id": telegram_id, "chat_id": chat_id},
                )
                return False

        except Exception as e:
            logger.error(
                "Error submitting media group",
                extra={"telegram_id": telegram_id, "chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            return False
