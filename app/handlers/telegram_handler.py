"""
Telegram update handler and message router.
"""

from typing import Dict, Any, Optional
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.logging_config import get_logger
from app.handlers.conversation_handler import ConversationHandler
from app.services.state_manager import StateManager
from app.services.message_service import MessageService
from app.services.message_poller import MessagePoller


logger = get_logger(__name__)


class TelegramHandler:
    """
    Handles incoming Telegram updates and routes them to appropriate handlers.
    """

    def __init__(
        self,
        bot: Bot,
        state_manager: StateManager,
        message_service: Optional[MessageService] = None,
        message_poller: Optional[MessagePoller] = None,
        order_service=None,
        settings_service=None,
        admin_message_handler=None,
    ):
        """
        Initialize the Telegram handler.

        Args:
            bot: Telegram Bot instance
            state_manager: StateManager instance for conversation state
            message_service: Optional MessageService for message persistence
            message_poller: Optional MessagePoller for polling backend messages
            order_service: Optional OrderService for order submission and queries
            settings_service: Optional SettingsService for exchange rates and bank accounts
            admin_message_handler: Optional AdminMessageHandler for admin group messages
        """
        self.bot = bot
        self.state_manager = state_manager
        self.message_service = message_service
        self.message_poller = message_poller
        self.order_service = order_service
        self.settings_service = settings_service
        self.admin_message_handler = admin_message_handler
        
        # Get admin_notifier from admin_message_handler if available
        admin_notifier = None
        if admin_message_handler and hasattr(admin_message_handler, 'admin_notifier'):
            admin_notifier = admin_message_handler.admin_notifier
        
        self.conversation_handler = ConversationHandler(
            bot,
            state_manager,
            message_service,
            message_poller,
            order_service,
            settings_service,
            admin_notifier,
        )
        logger.info("TelegramHandler initialized")

    async def process_update(self, update_data: Dict[str, Any]):
        """
        Process incoming Telegram update.

        Args:
            update_data: Raw update data from Telegram
        """
        try:
            # Create Update object from dict
            update = Update.de_json(update_data, self.bot)

            if not update:
                logger.warning("Failed to parse update data")
                return

            # Route to appropriate handler
            if update.message:
                await self.handle_message(update)
            elif update.callback_query:
                await self.handle_callback_query(update)
            else:
                logger.debug(f"Unhandled update type: {update}")

        except Exception as e:
            logger.error(
                "Error processing update", extra={"error": str(e)}, exc_info=True
            )

    async def handle_message(self, update: Update):
        """
        Handle incoming messages.

        Args:
            update: Telegram Update object
        """
        message = update.message
        user_id = message.from_user.id
        chat_id = message.chat_id
        telegram_id = str(user_id)

        logger.info(
            "Received message",
            extra={
                "user_id": user_id,
                "chat_id": chat_id,
                "message_type": (
                    "text" if message.text else "photo" if message.photo else "other"
                ),
            },
        )

        # Check if message is from admin group - route to admin message handler
        if self.admin_message_handler and hasattr(
            self.admin_message_handler, "admin_group_id"
        ):
            if chat_id == self.admin_message_handler.admin_group_id:
                logger.info(
                    f"Routing message to admin message handler (admin group: {chat_id})"
                )

                # Create a minimal context object for compatibility
                class MinimalContext:
                    pass

                context = MinimalContext()
                await self.admin_message_handler.handle_message(update, context)
                return

        # Submit user message to backend for persistence
        if self.message_service:
            content = message.text or message.caption or ""
            image_file_ids = None

            if message.photo:
                # Get the largest photo
                photo = message.photo[-1]
                image_file_ids = [photo.file_id]

            await self.message_service.submit_user_message(
                telegram_id=telegram_id,
                chat_id=chat_id,
                content=content,
                image_file_ids=image_file_ids,
            )

        # Handle commands
        if message.text and message.text.startswith("/"):
            await self.handle_command(update)
        # Handle photo messages
        elif message.photo:
            await self.handle_photo(update)
        # Handle text messages
        elif message.text:
            await self.handle_text(update)
        else:
            logger.debug(f"Unhandled message type from user {user_id}")

    async def handle_command(self, update: Update):
        """
        Handle command messages.

        Args:
            update: Telegram Update object
        """
        message = update.message
        command = message.text.split()[0].lower()
        user_id = message.from_user.id
        chat_id = message.chat_id

        logger.info(
            "Received command",
            extra={"user_id": user_id, "chat_id": chat_id, "command": command},
        )

        if command == "/start":
            await self.handle_start_command(update)
        elif command == "/cancel":
            await self.handle_cancel_command(update)
        else:
            await self.send_message(chat_id=chat_id, text=f"Unknown command: {command}")

    async def handle_start_command(self, update: Update):
        """
        Handle /start command.

        Args:
            update: Telegram Update object
        """
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id

        logger.info(f"User {user_id} started conversation")

        # Delegate to conversation handler
        await self.conversation_handler.handle_start(user_id, chat_id)

    async def handle_cancel_command(self, update: Update):
        """
        Handle /cancel command.

        Args:
            update: Telegram Update object
        """
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id

        logger.info(f"User {user_id} cancelled conversation")

        # Delegate to conversation handler
        await self.conversation_handler.handle_cancel(user_id, chat_id)

    async def handle_callback_query(self, update: Update):
        """
        Handle callback queries from inline buttons.

        Args:
            update: Telegram Update object
        """
        callback_query = update.callback_query
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat_id
        data = callback_query.data
        telegram_id = str(user_id)

        logger.info(
            "Received callback query",
            extra={"user_id": user_id, "chat_id": chat_id, "data": data},
        )

        # Submit user interaction to backend for persistence
        if self.message_service:
            await self.message_service.submit_user_message(
                telegram_id=telegram_id, chat_id=chat_id, content="", chosen_option=data
            )

        # Answer the callback query to remove loading state
        await callback_query.answer()

        # Delegate to conversation handler
        await self.conversation_handler.handle_callback_query(user_id, chat_id, data)

    async def handle_photo(self, update: Update):
        """
        Handle photo messages.

        Args:
            update: Telegram Update object
        """
        message = update.message
        user_id = message.from_user.id
        chat_id = message.chat_id

        # Get the largest photo
        photo = message.photo[-1]
        file_id = photo.file_id

        # Get media group ID if present (for multiple photos)
        media_group_id = (
            message.media_group_id if hasattr(message, "media_group_id") else None
        )

        logger.info(
            "Received photo",
            extra={
                "user_id": user_id,
                "chat_id": chat_id,
                "file_id": file_id,
                "file_size": photo.file_size,
                "media_group_id": media_group_id,
            },
        )

        # Delegate to conversation handler
        await self.conversation_handler.handle_receipt_photo(
            user_id, chat_id, file_id, media_group_id
        )

    async def handle_text(self, update: Update):
        """
        Handle text messages.

        Args:
            update: Telegram Update object
        """
        message = update.message
        user_id = message.from_user.id
        chat_id = message.chat_id
        text = message.text

        logger.info(
            "Received text message",
            extra={"user_id": user_id, "chat_id": chat_id, "text_length": len(text)},
        )

        # Delegate to conversation handler
        await self.conversation_handler.handle_text_message(user_id, chat_id, text)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: Optional[str] = None,
    ):
        """
        Send a text message to a chat.

        Args:
            chat_id: Chat ID to send message to
            text: Message text
            reply_markup: Optional inline keyboard
            parse_mode: Optional parse mode (Markdown, HTML)
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            logger.debug(f"Message sent to chat {chat_id}")

        except TelegramError as e:
            logger.error(
                "Telegram error sending message",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Error sending message",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )

    async def send_photo(
        self,
        chat_id: int,
        photo: bytes,
        caption: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        """
        Send a photo to a chat.

        Args:
            chat_id: Chat ID to send photo to
            photo: Photo bytes
            caption: Optional caption
            reply_markup: Optional inline keyboard
        """
        try:
            await self.bot.send_photo(
                chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup
            )
            logger.debug(f"Photo sent to chat {chat_id}")

        except TelegramError as e:
            logger.error(
                "Telegram error sending photo",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Error sending photo",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
