"""
Conversation flow handler for managing user interactions.
"""

from typing import Optional
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.models.conversation import ConversationState
from app.models.user_state import UserState
from app.models.order import OrderData
from app.services.state_manager import StateManager
from app.logging_config import get_logger


logger = get_logger(__name__)


class ConversationHandler:
    """
    Handles conversation flow logic for the bot.

    This handler manages the state transitions and user interactions
    throughout the order process.
    """

    def __init__(
        self,
        bot: Bot,
        state_manager: StateManager,
        message_service=None,
        message_poller=None,
        order_service=None,
        settings_service=None,
    ):
        """
        Initialize the conversation handler.

        Args:
            bot: Telegram Bot instance
            state_manager: StateManager instance for managing user states
            message_service: Optional MessageService for message persistence
            message_poller: Optional MessagePoller for polling backend messages
            order_service: Optional OrderService for order submission and queries
            settings_service: Optional SettingsService for exchange rates and bank accounts
        """
        self.bot = bot
        self.state_manager = state_manager
        self.message_service = message_service
        self.message_poller = message_poller
        self.order_service = order_service
        self.settings_service = settings_service
        logger.info("ConversationHandler initialized")

    async def handle_start(self, user_id: int, chat_id: int) -> None:
        """
        Handle /start command - initialize conversation.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
        """
        logger.info(
            "Handling start command", extra={"user_id": user_id, "chat_id": chat_id}
        )

        # Check maintenance mode
        if self.settings_service and self.settings_service.maintenance_mode:
            maintenance_message = (
                "🔧 System Maintenance\n\n"
                "The bot is currently under maintenance. "
                "Please try again later.\n\n"
                "We apologize for any inconvenience."
            )

            await self.bot.send_message(chat_id=chat_id, text=maintenance_message)

            # Submit bot message to backend
            if self.message_service:
                telegram_id = str(user_id)
                await self.message_service.submit_bot_message(
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    content=maintenance_message,
                )

            logger.info(
                "Blocked transaction due to maintenance mode",
                extra={"user_id": user_id, "chat_id": chat_id},
            )
            return

        # Check authentication requirement
        if self.settings_service and self.settings_service.auth_required:
            auth_message = (
                "🔐 Authentication Required\n\n"
                "You need to authenticate before using this service.\n\n"
                "Please contact our support team to set up your account."
            )

            await self.bot.send_message(chat_id=chat_id, text=auth_message)

            # Submit bot message to backend
            if self.message_service:
                telegram_id = str(user_id)
                await self.message_service.submit_bot_message(
                    telegram_id=telegram_id, chat_id=chat_id, content=auth_message
                )

            logger.info(
                "Blocked transaction due to auth requirement",
                extra={"user_id": user_id, "chat_id": chat_id},
            )
            return

        # Check for pending orders via backend API
        if self.order_service:
            has_pending = await self.order_service.check_pending_order(chat_id)

            if has_pending:
                # Block new orders if pending order exists
                pending_message = (
                    "⚠️ You have a pending order that is being processed.\n\n"
                    "Please wait for your current order to be completed before starting a new transaction.\n\n"
                    "If you have any questions, please contact our support team."
                )

                await self.bot.send_message(chat_id=chat_id, text=pending_message)

                # Submit bot message to backend
                if self.message_service:
                    telegram_id = str(user_id)
                    await self.message_service.submit_bot_message(
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        content=pending_message,
                    )

                logger.info(
                    "Blocked new order due to pending order",
                    extra={"user_id": user_id, "chat_id": chat_id},
                )
                return

        # Create or reset user state
        user_state = UserState(
            user_id=user_id,
            chat_id=chat_id,
            current_state=ConversationState.CHOOSE,
            order_data=OrderData(order_type=""),
        )
        self.state_manager.set_state(user_id, user_state)

        # Message polling disabled - using webhook-based notifications instead
        # Admin messages are now sent via backend webhook to bot
        logger.debug(
            "Message polling disabled (using webhooks)",
            extra={"user_id": user_id, "chat_id": chat_id},
        )

        # Show buy/sell options
        await self.show_choose_action(chat_id)

    async def handle_cancel(self, user_id: int, chat_id: int) -> None:
        """
        Handle /cancel command - cancel current conversation.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
        """
        logger.info(
            "Handling cancel command", extra={"user_id": user_id, "chat_id": chat_id}
        )

        # Clear user state
        self.state_manager.clear_state(user_id)

        # Send cancellation message
        cancel_text = (
            "❌ Operation cancelled.\n\nUse /start to begin a new transaction."
        )
        await self.bot.send_message(chat_id=chat_id, text=cancel_text)

        # Submit bot message to backend
        if self.message_service:
            telegram_id = str(user_id)
            await self.message_service.submit_bot_message(
                telegram_id=telegram_id, chat_id=chat_id, content=cancel_text
            )

    async def show_choose_action(self, chat_id: int) -> None:
        """
        Show buy/sell selection to user (CHOOSE state).

        Args:
            chat_id: Telegram chat ID
        """
        # Get exchange rates from settings service
        # Backend returns rates from BUSINESS perspective:
        #   buy = rate business BUYS MMK from user (user sells MMK)
        #   sell = rate business SELLS MMK to user (user buys MMK)
        # So from USER perspective:
        #   User buys MMK (sends THB) -> use backend's SELL rate
        #   User sells MMK (sends MMK) -> use backend's BUY rate

        thb_to_mmk = 285.71  # Default fallback (1 THB = 285.71 MMK)
        mmk_to_thb = 0.0035  # Default fallback (1 MMK = 0.0035 THB)

        if self.settings_service:
            # User buys MMK: use business sell rate (e.g., 125.78 MMK per THB)
            thb_to_mmk = (
                self.settings_service.sell_rate
                if self.settings_service.sell_rate > 0
                else thb_to_mmk
            )
            # User sells MMK: use business buy rate, inverted (e.g., 123.6 -> 1/123.6 THB per MMK)
            mmk_to_thb = (
                1 / self.settings_service.buy_rate
                if self.settings_service.buy_rate > 0
                else mmk_to_thb
            )

            logger.debug(
                "Exchange rates from backend",
                extra={
                    "backend_buy": self.settings_service.buy_rate,
                    "backend_sell": self.settings_service.sell_rate,
                    "display_thb_to_mmk": thb_to_mmk,
                    "display_mmk_to_thb": mmk_to_thb,
                },
            )

        welcome_text = (
            "Welcome to the Infinity Exchange Bot! 🎉\n\n"
            "This bot helps you exchange THB ↔️ MMK.\n\n"
            "Choose an option to get started:"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    f"💰 Buy MMK (1 THB = {thb_to_mmk:.2f} MMK)",
                    callback_data="action_buy",
                )
            ],
            [
                InlineKeyboardButton(
                    f"💵 Sell MMK (1 MMK = {mmk_to_thb:.6f} THB)",
                    callback_data="action_sell",
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.bot.send_message(
            chat_id=chat_id, text=welcome_text, reply_markup=reply_markup
        )

        # Submit bot message to backend
        if self.message_service:
            # Get user_id from state manager
            state = self.state_manager.get_state_by_chat_id(chat_id)
            if state:
                telegram_id = str(state.user_id)
                buttons = {
                    "action_buy": "💰 Buy MMK (Send THB)",
                    "action_sell": "💵 Sell MMK (Send MMK)",
                }
                await self.message_service.submit_bot_message(
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    content=welcome_text,
                    buttons=buttons,
                )

        logger.debug("Displayed choose action menu", extra={"chat_id": chat_id})

    async def handle_choose_action(
        self, user_id: int, chat_id: int, action: str
    ) -> None:
        """
        Handle buy/sell selection (CHOOSE state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            action: "buy" or "sell"
        """
        logger.info(
            "Handling action selection",
            extra={"user_id": user_id, "chat_id": chat_id, "action": action},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            await self.handle_start(user_id, chat_id)
            return

        # Validate action
        if action not in ["buy", "sell"]:
            logger.warning(
                "Invalid action", extra={"user_id": user_id, "action": action}
            )
            await self.show_choose_action(chat_id)
            return

        # Update state with selected action
        self.state_manager.update_state(
            user_id, new_state=ConversationState.SELECT_PAYMENT_BANK, order_type=action
        )

        # Fetch exchange rates from backend via settings_service
        # Backend rates are from BUSINESS perspective:
        #   buy = rate business BUYS MMK (user sells MMK to business)
        #   sell = rate business SELLS MMK (user buys MMK from business)
        if self.settings_service:
            if action == "buy":
                # User buys MMK (sends THB): use business SELL rate
                # Backend sell rate: 1 THB = X MMK (e.g., 125.78)
                exchange_rate = self.settings_service.sell_rate
                logger.debug(
                    f"User buy MMK rate: 1 THB = {exchange_rate} MMK",
                    extra={
                        "action": "buy",
                        "rate": exchange_rate,
                        "backend_sell": self.settings_service.sell_rate,
                    },
                )
            else:
                # User sells MMK (sends MMK): use business BUY rate
                # Backend buy rate: X MMK = 1 THB (e.g., 123.6)
                # So 1 MMK = 1/X THB
                exchange_rate = (
                    1 / self.settings_service.buy_rate
                    if self.settings_service.buy_rate > 0
                    else 0.0035
                )
                logger.debug(
                    f"User sell MMK rate: 1 MMK = {exchange_rate} THB (backend buy: {self.settings_service.buy_rate} MMK = 1 THB)",
                    extra={
                        "action": "sell",
                        "rate": exchange_rate,
                        "backend_buy": self.settings_service.buy_rate,
                    },
                )
        else:
            # Fallback to default rates if settings_service not available
            exchange_rate = 285.71 if action == "buy" else 0.0035

        self.state_manager.update_state(user_id, exchange_rate=exchange_rate)

        # Show payment bank selection (NEW FLOW)
        await self.show_payment_bank_selection(chat_id, action, exchange_rate)

    async def show_payment_bank_selection(
        self, chat_id: int, action: str, exchange_rate: float
    ) -> None:
        """
        Show bank selection buttons for user to choose which bank to pay to (SELECT_PAYMENT_BANK state).

        Args:
            chat_id: Telegram chat ID
            action: "buy" or "sell"
            exchange_rate: Current exchange rate
        """
        logger.info(
            "Showing payment bank selection",
            extra={"chat_id": chat_id, "action": action},
        )

        # Fetch bank accounts from backend via settings_service
        if action == "buy":
            # Buy: user sends THB, so show Thai banks
            bank_accounts = []
            if self.settings_service:
                bank_accounts = self.settings_service.thai_banks
            bank_type = "Thai"
            currency_send = "THB"
            currency_receive = "MMK"
            rate_display = f"1 THB = {exchange_rate:.2f} MMK"
        else:  # sell
            # Sell: user sends MMK, so show Myanmar banks
            bank_accounts = []
            if self.settings_service:
                bank_accounts = self.settings_service.myanmar_banks
            bank_type = "Myanmar"
            currency_send = "MMK"
            currency_receive = "THB"
            rate_display = f"1 MMK = {exchange_rate:.6f} THB"

        # Filter active banks
        active_banks = [bank for bank in bank_accounts if bank.get("on", True)]

        if not active_banks:
            error_msg = f"❌ No {bank_type} banks available at the moment.\n\nPlease contact admin: @infinityadmin001"
            logger.error(
                f"No active {bank_type} banks available for payment",
                extra={"chat_id": chat_id, "total_banks": len(bank_accounts)},
            )
            await self.bot.send_message(chat_id=chat_id, text=error_msg)
            return

        # Create message
        message = (
            f"💰 *{'Buy MMK (Send THB)' if action == 'buy' else 'Sell MMK (Send MMK)'}*\n\n"
            f"Exchange Rate: {rate_display}\n\n"
            f"Please select which {bank_type} bank you want to use for payment:"
        )

        # Create inline keyboard with bank buttons (1 per row for clarity)
        keyboard = []
        for bank in active_banks:
            button = InlineKeyboardButton(
                text=f"🏦 {bank['bank_name']}", callback_data=f"paybank_{bank['id']}"
            )
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        # Submit bot message to backend
        if self.message_service:
            state = self.state_manager.get_state_by_chat_id(chat_id)
            if state:
                telegram_id = str(state.user_id)
                buttons = {
                    f"paybank_{bank['id']}": f"🏦 {bank['bank_name']}"
                    for bank in active_banks
                }
                await self.message_service.submit_bot_message(
                    telegram_id=telegram_id,
                    chat_id=chat_id,
                    content=message,
                    buttons=buttons,
                )

        logger.debug(
            f"Showed {len(active_banks)} payment bank options",
            extra={"chat_id": chat_id, "bank_count": len(active_banks)},
        )

    async def handle_payment_bank_selection(
        self, user_id: int, chat_id: int, bank_id: int
    ) -> None:
        """
        Handle user's payment bank selection (SELECT_PAYMENT_BANK state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bank_id: Selected bank ID
        """
        logger.info(
            "Handling payment bank selection",
            extra={"user_id": user_id, "chat_id": chat_id, "bank_id": bank_id},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            await self.bot.send_message(
                chat_id=chat_id, text="Please use /start to begin a transaction."
            )
            return

        # Check if user is in correct state
        if state.current_state != ConversationState.SELECT_PAYMENT_BANK:
            logger.warning(
                "User not in SELECT_PAYMENT_BANK state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Get bank details based on order type
        if state.order_data.order_type == "buy":
            banks = self.settings_service.thai_banks if self.settings_service else []
        else:
            banks = self.settings_service.myanmar_banks if self.settings_service else []

        selected_bank = next((b for b in banks if b["id"] == bank_id), None)

        if not selected_bank:
            await self.bot.send_message(
                chat_id=chat_id, text="❌ Invalid bank selection. Please try again."
            )
            return

        # Update state with selected payment bank
        self.state_manager.update_state(
            user_id,
            new_state=ConversationState.WAIT_RECEIPT,
            selected_payment_bank_id=bank_id,
            selected_payment_bank_name=selected_bank["bank_name"],
        )

        # Show selected bank details with QR code
        await self.show_selected_bank_details(
            chat_id,
            selected_bank,
            state.order_data.order_type,
            state.order_data.exchange_rate or 0.0,
        )

        logger.debug(
            f"Payment bank selected: {selected_bank['bank_name']}",
            extra={"user_id": user_id, "bank_id": bank_id},
        )

    async def show_selected_bank_details(
        self, chat_id: int, bank: dict, order_type: str, exchange_rate: float
    ) -> None:
        """
        Show specific bank account details and QR code for selected bank (WAIT_RECEIPT state).

        Args:
            chat_id: Telegram chat ID
            bank: Selected bank dictionary
            order_type: "buy" or "sell"
            exchange_rate: Current exchange rate
        """
        # Build message with bank details
        if order_type == "buy":
            rate_display = f"1 THB = {exchange_rate:.2f} MMK"
            action_text = "Buy MMK (Send THB)"
        else:
            rate_display = f"1 MMK = {exchange_rate:.6f} THB"
            action_text = "Sell MMK (Send MMK)"

        message = (
            f"💰 *{action_text}*\n\n"
            f"Exchange Rate: {rate_display}\n\n"
            f"🏦 *Please transfer to:*\n"
            f"Bank: {bank['bank_name']}\n"
            f"Account Number: {bank['account_number']}\n"
            f"Account Name: {bank['account_name']}\n\n"
            f"📸 After transferring, please send a screenshot of your receipt."
        )

        # Send message
        await self.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown"
        )

        # Send QR code if available
        if bank.get("qr_image") and bank["qr_image"].strip():
            try:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=bank["qr_image"],
                    caption=f"💳 Scan to pay to {bank['bank_name']}",
                )
                logger.info(
                    f"Sent QR code for bank {bank['bank_name']}",
                    extra={"chat_id": chat_id, "bank_id": bank["id"]},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to send QR code: {e}",
                    extra={"chat_id": chat_id, "bank_id": bank["id"]},
                )

        # Submit bot message to backend
        if self.message_service:
            state = self.state_manager.get_state_by_chat_id(chat_id)
            if state:
                telegram_id = str(state.user_id)
                await self.message_service.submit_bot_message(
                    telegram_id=telegram_id, chat_id=chat_id, content=message
                )

        logger.debug(
            "Displayed selected bank details",
            extra={"chat_id": chat_id, "bank_name": bank["bank_name"]},
        )

    async def handle_receipt_photo(
        self,
        user_id: int,
        chat_id: int,
        file_id: str,
        media_group_id: Optional[str] = None,
    ) -> None:
        """
        Handle receipt photo submission (WAIT_RECEIPT or COLLECTING_RECEIPTS state handler).
        Also handles QR code photos in SELECT_USER_BANK state.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            file_id: Telegram file ID of the photo
            media_group_id: Optional media group ID for multiple photos
        """
        logger.info(
            "Handling receipt photo",
            extra={
                "user_id": user_id,
                "chat_id": chat_id,
                "file_id": file_id,
                "media_group_id": media_group_id,
            },
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            await self.bot.send_message(
                chat_id=chat_id, text="Please use /start to begin a transaction."
            )
            return

        # Check if user is trying to send QR code for bank info
        if state.current_state == ConversationState.SELECT_USER_BANK:
            logger.info("User sent QR code image for bank info")
            await self.handle_bank_qr_photo(user_id, chat_id, file_id)
            return

        # Check if user is in correct state for receipt
        if state.current_state not in [
            ConversationState.WAIT_RECEIPT,
            ConversationState.COLLECTING_RECEIPTS,
        ]:
            logger.warning(
                "User not in receipt collection state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Handle media groups (multiple photos sent at once)
        if media_group_id:
            # Check if this is a new media group
            if state.order_data.media_group_id != media_group_id:
                # New media group - reset collected photos
                self.state_manager.update_state(
                    user_id, media_group_id=media_group_id, collected_photos=[file_id]
                )
                logger.debug(
                    "Started collecting media group",
                    extra={"user_id": user_id, "media_group_id": media_group_id},
                )
                return
            else:
                # Same media group - add to collection
                state.order_data.collected_photos.append(file_id)
                self.state_manager.update_state(
                    user_id, collected_photos=state.order_data.collected_photos
                )
                logger.debug(
                    "Added photo to media group",
                    extra={
                        "user_id": user_id,
                        "photo_count": len(state.order_data.collected_photos),
                    },
                )
                return

        # Single photo - proceed with verification immediately
        # Update state to verifying
        self.state_manager.update_state(
            user_id, new_state=ConversationState.VERIFY_RECEIPT
        )

        # Send acknowledgment
        await self.bot.send_message(
            chat_id=chat_id,
            text="✅ Receipt received! Verifying...\n\nPlease wait a moment.",
        )

        # Trigger OCR verification for this single receipt
        await self.verify_receipt(user_id, chat_id, file_id)

    async def verify_receipt(self, user_id: int, chat_id: int, file_id: str) -> None:
        """
        Verify receipt using OCR (VERIFY_RECEIPT state handler).
        Supports multiple receipt flow with bank verification.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            file_id: File ID of the receipt to verify
        """
        logger.info(
            "Verifying receipt",
            extra={"user_id": user_id, "chat_id": chat_id, "file_id": file_id},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Get the selected payment bank for validation (only validate against ONE bank)
        admin_banks = []
        if self.settings_service and state.order_data.selected_payment_bank_id:
            # Get all banks based on order type
            if state.order_data.order_type == "buy":
                all_banks = self.settings_service.thai_banks
            else:
                all_banks = self.settings_service.myanmar_banks

            # Filter to only the selected payment bank
            selected_bank = next(
                (
                    b
                    for b in all_banks
                    if b["id"] == state.order_data.selected_payment_bank_id
                ),
                None,
            )
            if selected_bank:
                admin_banks = [selected_bank]
                logger.info(
                    f"Validating receipt against selected bank: {selected_bank['bank_name']}",
                    extra={"user_id": user_id, "bank_id": selected_bank["id"]},
                )
            else:
                logger.error(
                    f"Selected payment bank not found: {state.order_data.selected_payment_bank_id}",
                    extra={"user_id": user_id},
                )
        else:
            logger.warning(
                "No selected payment bank found, falling back to all banks",
                extra={"user_id": user_id},
            )
            # Fallback: validate against all banks (legacy behavior)
            if self.settings_service:
                if state.order_data.order_type == "buy":
                    admin_banks = self.settings_service.thai_banks
                else:
                    admin_banks = self.settings_service.myanmar_banks

        # Initialize OCR service with admin banks
        from app.services.ocr_service import OCRService
        from app.config import get_settings

        settings = get_settings()

        ocr_service = OCRService(
            openai_api_key=settings.openai_api_key, admin_banks=admin_banks
        )

        # Import receipt manager
        from app.services.receipt_manager import ReceiptManager

        receipt_manager = ReceiptManager()

        try:
            # Download the receipt image with retry logic
            image_bytes = None
            max_retries = 3

            for attempt in range(max_retries):
                try:
                    logger.info(
                        f"Downloading receipt image (attempt {attempt + 1}/{max_retries})"
                    )
                    file = await self.bot.get_file(file_id)
                    image_bytes = await file.download_as_bytearray()
                    logger.info(
                        f"Receipt image downloaded successfully ({len(image_bytes)} bytes)"
                    )
                    break
                except Exception as download_error:
                    logger.warning(
                        f"Download attempt {attempt + 1} failed: {download_error}",
                        extra={"user_id": user_id, "attempt": attempt + 1},
                    )
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        raise
                    # Wait before retry (exponential backoff)
                    import asyncio

                    await asyncio.sleep(2**attempt)

            if not image_bytes:
                raise Exception("Failed to download receipt image after retries")

            # Run OCR verification
            logger.info("Running OCR verification on receipt")
            receipt_data = await ocr_service.extract_with_retry(bytes(image_bytes))

            # Log detailed OCR results
            if receipt_data:
                logger.info(
                    "OCR Detection Results:",
                    extra={
                        "user_id": user_id,
                        "detected_bank_name": receipt_data.bank_name,
                        "detected_account_number": receipt_data.account_number,
                        "detected_account_holder": receipt_data.account_name,
                        "detected_amount": receipt_data.amount,
                        "confidence_score": receipt_data.confidence_score,
                        "transaction_date": receipt_data.transaction_date,
                        "transaction_id": receipt_data.transaction_id,
                        "matched_bank_id": receipt_data.matched_bank_id,
                    },
                )

                # Log admin banks for comparison
                logger.info(
                    f"Admin banks to match against ({len(admin_banks)} banks):",
                    extra={
                        "admin_banks": [
                            {
                                "id": bank.get("id"),
                                "bank_name": bank.get("bank_name"),
                                "account_number": bank.get("account_number"),
                                "account_name": bank.get("account_name"),
                            }
                            for bank in admin_banks
                        ]
                    },
                )
            else:
                logger.error("OCR returned None - no data extracted from receipt")

            if receipt_data and receipt_data.confidence_score >= 0.5:
                # Check if this receipt matches expected bank (for multiple receipts)
                is_bank_match, bank_error = receipt_manager.verify_bank_match(
                    receipt_data, state.order_data.expected_bank_id, admin_banks
                )

                if not is_bank_match:
                    # Bank mismatch - show error and buttons
                    logger.warning(
                        "Bank mismatch detected",
                        extra={
                            "user_id": user_id,
                            "expected_bank_id": state.order_data.expected_bank_id,
                            "received_bank_id": receipt_data.matched_bank_id,
                        },
                    )

                    # Return to collecting state
                    self.state_manager.update_state(
                        user_id, new_state=ConversationState.COLLECTING_RECEIPTS
                    )

                    # Show error with action buttons
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "🔄 Try Again", callback_data="receipt_retry"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "✅ Continue with Current Receipts",
                                callback_data="receipt_confirm",
                            )
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await self.bot.send_message(
                        chat_id=chat_id, text=bank_error, reply_markup=reply_markup
                    )
                    return

                # Verification passed
                verification_passed = True
                logger.info(
                    f"✅ Receipt VERIFIED with confidence {receipt_data.confidence_score:.2f}",
                    extra={
                        "user_id": user_id,
                        "bank_name": receipt_data.bank_name,
                        "account_number": receipt_data.account_number,
                        "confidence": receipt_data.confidence_score,
                        "matched_bank_id": receipt_data.matched_bank_id,
                    },
                )
            else:
                # Verification failed
                verification_passed = False
                confidence = receipt_data.confidence_score if receipt_data else 0.0
                logger.warning(
                    f"❌ Receipt REJECTED with confidence {confidence:.2f} (threshold: 0.5)",
                    extra={
                        "user_id": user_id,
                        "confidence": confidence,
                        "detected_bank": (
                            receipt_data.bank_name if receipt_data else None
                        ),
                        "detected_account": (
                            receipt_data.account_number if receipt_data else None
                        ),
                        "reason": "Confidence below threshold or no match with admin banks",
                    },
                )

        except Exception as e:
            from telegram.error import TimedOut, NetworkError

            logger.error(f"Error during OCR verification: {e}", exc_info=True)
            verification_passed = False

            # Provide specific error messages to user
            if isinstance(e, TimedOut):
                error_msg = (
                    "⏱️ Receipt download timed out. This might be due to:\n"
                    "• Large image size\n"
                    "• Slow network connection\n\n"
                    "Please try:\n"
                    "1. Send a smaller/compressed image\n"
                    "2. Try again in a moment\n\n"
                    "Or contact admin: @infinityadmin001"
                )
            elif isinstance(e, NetworkError):
                error_msg = (
                    "🌐 Network error occurred while processing your receipt.\n\n"
                    "Please try again in a moment.\n"
                    "If the problem persists, contact: @infinityadmin001"
                )
            else:
                error_msg = (
                    "❌ Unable to process receipt at this time.\n\n"
                    "Please try again or contact admin: @infinityadmin001"
                )

            # Send error message to user
            try:
                await self.bot.send_message(chat_id=chat_id, text=error_msg)
            except Exception as send_error:
                logger.error(f"Failed to send error message to user: {send_error}")

        if verification_passed:
            # Receipt verified - add to collection
            is_first_receipt = state.order_data.receipt_count == 0

            # Add receipt to collections
            state.order_data.receipt_file_ids.append(file_id)
            state.order_data.receipt_amounts.append(receipt_data.amount)
            state.order_data.receipt_bank_ids.append(receipt_data.matched_bank_id)
            state.order_data.receipt_count += 1

            # If first receipt, set expected bank
            if is_first_receipt:
                bank_name, account_number = receipt_manager.get_bank_details(
                    receipt_data.matched_bank_id, admin_banks
                )
                state.order_data.expected_bank_id = receipt_data.matched_bank_id
                state.order_data.expected_bank_name = bank_name
                state.order_data.expected_account_number = account_number
                state.order_data.detected_admin_bank_id = receipt_data.matched_bank_id

            # Calculate total
            state.order_data.total_amount = receipt_manager.calculate_total(
                state.order_data.receipt_amounts
            )

            # Store amount based on order type (for backward compatibility)
            if state.order_data.order_type == "buy":
                state.order_data.thb_amount = state.order_data.total_amount
            else:
                state.order_data.mmk_amount = state.order_data.total_amount

            # Update state
            self.state_manager.update_state(
                user_id,
                new_state=ConversationState.COLLECTING_RECEIPTS,
                receipt_file_ids=state.order_data.receipt_file_ids,
                receipt_amounts=state.order_data.receipt_amounts,
                receipt_bank_ids=state.order_data.receipt_bank_ids,
                receipt_count=state.order_data.receipt_count,
                expected_bank_id=state.order_data.expected_bank_id,
                expected_bank_name=state.order_data.expected_bank_name,
                expected_account_number=state.order_data.expected_account_number,
                total_amount=state.order_data.total_amount,
                thb_amount=state.order_data.thb_amount,
                mmk_amount=state.order_data.mmk_amount,
                detected_admin_bank_id=state.order_data.detected_admin_bank_id,
            )

            logger.info(
                f"Receipt {state.order_data.receipt_count} added to collection",
                extra={
                    "user_id": user_id,
                    "receipt_count": state.order_data.receipt_count,
                    "amount": receipt_data.amount,
                    "total_amount": state.order_data.total_amount,
                    "bank_id": receipt_data.matched_bank_id,
                },
            )

            # Determine currency
            currency = "THB" if state.order_data.order_type == "buy" else "MMK"

            # Format verification message
            message = receipt_manager.format_receipt_verified_message(
                receipt_number=state.order_data.receipt_count,
                amount=receipt_data.amount,
                currency=currency,
                total_amount=state.order_data.total_amount,
                bank_name=state.order_data.expected_bank_name,
                account_number=state.order_data.expected_account_number,
                is_first=is_first_receipt,
            )

            # Check receipt limit
            is_valid, limit_error = receipt_manager.validate_receipt_limit(
                state.order_data.receipt_count, max_receipts=10
            )

            # Create action buttons
            keyboard = []
            if is_valid:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "➕ Add Another Receipt", callback_data="receipt_add"
                        )
                    ]
                )
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✅ Confirm & Submit", callback_data="receipt_confirm"
                    )
                ]
            )
            keyboard.append(
                [InlineKeyboardButton("🔄 Start Over", callback_data="receipt_restart")]
            )

            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send message with buttons
            await self.bot.send_message(
                chat_id=chat_id, text=message, reply_markup=reply_markup
            )

            # Show limit warning if reached
            if not is_valid:
                await self.bot.send_message(chat_id=chat_id, text=limit_error)
        else:
            # Verification failed - request new receipt
            self.state_manager.update_state(
                user_id,
                new_state=ConversationState.WAIT_RECEIPT,
                receipt_file_ids=[],
                collected_photos=[],
                media_group_id=None,
            )

            await self.bot.send_message(
                chat_id=chat_id,
                text=(
                    "❌ Receipt verification failed.\n\n"
                    "Please check:\n"
                    "• Amount is correct\n"
                    "• Bank account matches our account\n"
                    "• Receipt is clear and readable\n\n"
                    "Please send a new receipt or use /cancel to abort."
                ),
            )

    async def request_user_bank_info(self, chat_id: int, order_type: str) -> None:
        """
        Request user's bank information (WAIT_USER_BANK state).

        Args:
            chat_id: Telegram chat ID
            order_type: "buy" or "sell"
        """
        if order_type == "buy":
            message = (
                "✅ Receipt verified!\n\n"
                "Please provide your Myanmar bank account information in this format:\n\n"
                "*Bank Name - Account Number - Account Holder Name*\n\n"
                "Example:\n"
                "KBZ Bank - 1234567890 - John Doe\n\n"
                "We will send MMK to this account."
            )
        else:  # sell
            message = (
                "✅ Receipt verified!\n\n"
                "Please provide your Thai bank account information in this format:\n\n"
                "*Bank Name - Account Number - Account Holder Name*\n\n"
                "Example:\n"
                "Bangkok Bank - 123-4-56789-0 - John Doe\n\n"
                "We will send THB to this account."
            )

        await self.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown"
        )

        logger.debug(
            "Requested user bank info",
            extra={"chat_id": chat_id, "order_type": order_type},
        )

    async def show_user_bank_selection(
        self, user_id: int, chat_id: int, order_type: str
    ) -> None:
        """
        Show bank selection buttons to user (SELECT_USER_BANK state).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            order_type: "buy" or "sell"
        """
        logger.info(
            "Showing bank selection",
            extra={"user_id": user_id, "chat_id": chat_id, "order_type": order_type},
        )

        if order_type == "buy":
            # User receives MMK, show Myanmar banks
            banks = self.settings_service.myanmar_banks if self.settings_service else []
            message = "✅ Receipt verified!\n\nPlease select your Myanmar bank where you want to receive MMK:\n\n💡 Or send a QR code image of your bank account"
            bank_type = "Myanmar"
        else:
            # User receives THB, show Thai banks
            banks = self.settings_service.thai_banks if self.settings_service else []
            message = "✅ Receipt verified!\n\nPlease select your Thai bank where you want to receive THB:\n\n💡 Or send a QR code image of your bank account (PromptPay supported)"
            bank_type = "Thai"

        logger.info(
            f"Fetched {len(banks)} {bank_type} banks from settings service",
            extra={"user_id": user_id, "bank_count": len(banks), "banks": banks},
        )

        # Backend already filters by on=True, so all banks should be active
        # But we still check for safety
        active_banks = [bank for bank in banks if bank.get("on", True)]

        if not active_banks:
            error_msg = f"❌ No {bank_type} banks available at the moment.\n\nPlease contact admin: @infinityadmin001"
            logger.error(
                f"No active {bank_type} banks available",
                extra={"user_id": user_id, "total_banks": len(banks)},
            )
            await self.bot.send_message(chat_id=chat_id, text=error_msg)
            return

        # Update state to SELECT_USER_BANK
        self.state_manager.update_state(
            user_id, new_state=ConversationState.SELECT_USER_BANK
        )

        # Create inline keyboard with bank buttons (2 columns)
        keyboard = []
        row = []
        for i, bank in enumerate(active_banks):
            button = InlineKeyboardButton(
                text=bank["bank_name"], callback_data=f"bank_{bank['id']}"
            )
            row.append(button)

            # Add row every 2 buttons or at the end
            if len(row) == 2 or i == len(active_banks) - 1:
                keyboard.append(row)
                row = []

        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.bot.send_message(
            chat_id=chat_id, text=message, reply_markup=reply_markup
        )

        logger.debug(
            f"Showed {len(active_banks)} bank options and updated state to SELECT_USER_BANK",
            extra={"user_id": user_id, "bank_count": len(active_banks)},
        )

    async def handle_bank_selection(
        self, user_id: int, chat_id: int, bank_id: int
    ) -> None:
        """
        Handle user's bank selection from buttons (SELECT_USER_BANK state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bank_id: Selected bank ID
        """
        logger.info(
            "Handling bank selection",
            extra={"user_id": user_id, "chat_id": chat_id, "bank_id": bank_id},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            await self.bot.send_message(
                chat_id=chat_id, text="Please use /start to begin a transaction."
            )
            return

        # Check if user is in correct state
        if state.current_state != ConversationState.SELECT_USER_BANK:
            logger.warning(
                "User not in SELECT_USER_BANK state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Get bank details
        if state.order_data.order_type == "buy":
            banks = self.settings_service.myanmar_banks if self.settings_service else []
        else:
            banks = self.settings_service.thai_banks if self.settings_service else []

        selected_bank = next((b for b in banks if b["id"] == bank_id), None)

        if not selected_bank:
            await self.bot.send_message(
                chat_id=chat_id, text="❌ Invalid bank selection. Please try again."
            )
            return

        # Update state
        self.state_manager.update_state(
            user_id,
            new_state=ConversationState.WAIT_ACCOUNT_NUMBER,
            selected_user_bank_id=bank_id,
            selected_user_bank_name=selected_bank["bank_name"],
        )

        # Ask for account number
        await self.bot.send_message(
            chat_id=chat_id,
            text=f"✅ {selected_bank['bank_name']} selected\n\nPlease enter your account number:",
        )

        logger.debug(
            f"Bank selected: {selected_bank['bank_name']}",
            extra={"user_id": user_id, "bank_id": bank_id},
        )

    async def handle_account_number(
        self, user_id: int, chat_id: int, account_number: str
    ) -> None:
        """
        Handle account number input (WAIT_ACCOUNT_NUMBER state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            account_number: User's account number
        """
        logger.info(
            "Handling account number", extra={"user_id": user_id, "chat_id": chat_id}
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Check if user is in correct state
        if state.current_state != ConversationState.WAIT_ACCOUNT_NUMBER:
            logger.warning(
                "User not in WAIT_ACCOUNT_NUMBER state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Basic validation
        cleaned_number = account_number.strip()
        if not cleaned_number or len(cleaned_number) < 5:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Invalid account number. Please enter a valid account number:",
            )
            return

        # Update state
        self.state_manager.update_state(
            user_id,
            new_state=ConversationState.WAIT_ACCOUNT_NAME,
            user_account_number=cleaned_number,
        )

        # Ask for account holder name
        await self.bot.send_message(
            chat_id=chat_id,
            text="✅ Account number saved\n\nPlease enter the account holder name:",
        )

        logger.debug("Account number saved", extra={"user_id": user_id})

    async def handle_account_name(
        self, user_id: int, chat_id: int, account_name: str
    ) -> None:
        """
        Handle account holder name input (WAIT_ACCOUNT_NAME state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            account_name: User's account holder name
        """
        logger.info(
            "Handling account name", extra={"user_id": user_id, "chat_id": chat_id}
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Check if user is in correct state
        if state.current_state != ConversationState.WAIT_ACCOUNT_NAME:
            logger.warning(
                "User not in WAIT_ACCOUNT_NAME state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Basic validation
        cleaned_name = account_name.strip()
        if not cleaned_name or len(cleaned_name) < 2:
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Invalid account holder name. Please enter a valid name:",
            )
            return

        # Build user_bank string
        user_bank = f"{state.order_data.selected_user_bank_name} - {state.order_data.user_account_number} - {cleaned_name}"

        # Update state
        self.state_manager.update_state(
            user_id, user_bank_info=user_bank, user_account_name=cleaned_name
        )

        logger.info(f"User bank info complete: {user_bank}", extra={"user_id": user_id})

        # Submit order
        await self.submit_order(user_id, chat_id)

    async def handle_user_bank_info(
        self, user_id: int, chat_id: int, bank_info: str
    ) -> None:
        """
        Handle user bank information submission (WAIT_USER_BANK state handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            bank_info: User's bank account information
        """
        logger.info(
            "Handling user bank info", extra={"user_id": user_id, "chat_id": chat_id}
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Check if user is in correct state
        if state.current_state != ConversationState.WAIT_USER_BANK:
            logger.warning(
                "User not in WAIT_USER_BANK state",
                extra={"user_id": user_id, "current_state": state.current_state.value},
            )
            return

        # Validate bank info format (basic validation)
        parts = bank_info.split("-")
        if len(parts) < 3:
            await self.bot.send_message(
                chat_id=chat_id,
                text=(
                    "❌ Invalid format.\n\n"
                    "Please use this format:\n"
                    "*Bank Name - Account Number - Account Holder Name*\n\n"
                    "Example:\n"
                    "KBZ Bank - 1234567890 - John Doe"
                ),
                parse_mode="Markdown",
            )
            return

        # Update state with user bank info
        self.state_manager.update_state(user_id, user_bank_info=bank_info.strip())

        # Submit order
        await self.submit_order(user_id, chat_id)

    async def submit_order(self, user_id: int, chat_id: int) -> None:
        """
        Submit order to backend (order submission handler).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
        """
        logger.info("Submitting order", extra={"user_id": user_id, "chat_id": chat_id})

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Validate required order data
        if not state.order_data.receipt_file_ids:
            logger.error(
                "Cannot submit order without receipt", extra={"user_id": user_id}
            )
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Error: No receipt found. Please use /start to begin again.",
            )
            return

        if not state.order_data.user_bank_info:
            logger.error(
                "Cannot submit order without user bank info", extra={"user_id": user_id}
            )
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Error: No bank information found. Please use /start to begin again.",
            )
            return

        # Submit order to backend via OrderService
        if self.order_service:
            # Calculate amount based on order type
            # For buy orders: user sends THB, amount is in THB
            # For sell orders: user sends MMK, amount is in MMK
            amount = state.order_data.thb_amount or state.order_data.mmk_amount or 0.0

            logger.info(
                f"📊 Amount calculation for order submission",
                extra={
                    "user_id": user_id,
                    "order_type": state.order_data.order_type,
                    "thb_amount": state.order_data.thb_amount,
                    "mmk_amount": state.order_data.mmk_amount,
                    "final_amount": amount,
                },
            )

            # Determine bank IDs based on order type
            # Use selected_payment_bank_id (bank user paid to) instead of detected_admin_bank_id
            if state.order_data.order_type == "buy":
                # Buy: user sends THB (selected payment bank), receives MMK (selected by user)
                thai_bank_id = state.order_data.selected_payment_bank_id
                myanmar_bank_id = state.order_data.selected_user_bank_id
                myanmar_bank_name = None
            else:
                # Sell: user sends MMK (selected payment bank), receives THB (selected by user)
                thai_bank_id = state.order_data.selected_user_bank_id
                myanmar_bank_id = state.order_data.selected_payment_bank_id
                myanmar_bank_name = None

            logger.info(
                f"📋 Bank details for order submission",
                extra={
                    "user_id": user_id,
                    "order_type": state.order_data.order_type,
                    "thai_bank_id": thai_bank_id,
                    "myanmar_bank_id": myanmar_bank_id,
                    "myanmar_bank_name": myanmar_bank_name,
                },
            )

            order_id = await self.order_service.submit_order(
                order_type=state.order_data.order_type,
                amount=amount,
                price=state.order_data.exchange_rate or 0.0,
                receipt_file_ids=state.order_data.receipt_file_ids,
                user_bank=state.order_data.user_bank_info,
                chat_id=chat_id,
                qr_file_id=state.order_data.qr_file_id,
                myanmar_bank=myanmar_bank_name,
                thai_bank_id=thai_bank_id,
                myanmar_bank_id=myanmar_bank_id,
            )

            if order_id:
                # Update state with order ID and set to PENDING
                self.state_manager.update_state(
                    user_id, new_state=ConversationState.PENDING, order_id=order_id
                )

                # Send confirmation to user
                order_type_text = (
                    "Buy MMK" if state.order_data.order_type == "buy" else "Sell MMK"
                )

                success_message = (
                    f"✅ *Order Submitted!*\n\n"
                    f"Order Type: {order_type_text}\n"
                    f"Order ID: {order_id}\n\n"
                    f"Your order has been sent to our admin team for review.\n"
                    f"You will receive a confirmation once the transfer is complete.\n\n"
                    f"Thank you for using Infinity Exchange Bot! 🎉"
                )

                await self.bot.send_message(
                    chat_id=chat_id, text=success_message, parse_mode="Markdown"
                )

                # Submit bot message to backend
                if self.message_service:
                    telegram_id = str(user_id)
                    await self.message_service.submit_bot_message(
                        telegram_id=telegram_id,
                        chat_id=chat_id,
                        content=success_message,
                    )

                # TODO: In Task 5, send notification to admin group

                logger.info(
                    "Order submitted successfully",
                    extra={
                        "user_id": user_id,
                        "order_id": order_id,
                        "order_type": state.order_data.order_type,
                    },
                )
            else:
                # Order submission failed
                error_message = (
                    "❌ Failed to submit order.\n\n"
                    "Please try again later or contact support if the problem persists.\n\n"
                    "Use /start to try again."
                )

                await self.bot.send_message(chat_id=chat_id, text=error_message)

                # Submit bot message to backend
                if self.message_service:
                    telegram_id = str(user_id)
                    await self.message_service.submit_bot_message(
                        telegram_id=telegram_id, chat_id=chat_id, content=error_message
                    )

                logger.error(
                    "Order submission failed",
                    extra={"user_id": user_id, "chat_id": chat_id},
                )
        else:
            # OrderService not available - fallback behavior
            logger.warning(
                "OrderService not available, using placeholder",
                extra={"user_id": user_id},
            )

            # Update state to PENDING with placeholder
            self.state_manager.update_state(
                user_id,
                new_state=ConversationState.PENDING,
                order_id="ORD-PLACEHOLDER-001",
            )

            # Send confirmation to user
            order_type_text = (
                "Buy MMK" if state.order_data.order_type == "buy" else "Sell MMK"
            )

            await self.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Order Submitted!*\n\n"
                    f"Order Type: {order_type_text}\n"
                    f"Order ID: {state.order_data.order_id}\n\n"
                    f"Your order has been sent to our admin team for review.\n"
                    f"You will receive a confirmation once the transfer is complete.\n\n"
                    f"Thank you for using Infinity Exchange Bot! 🎉"
                ),
                parse_mode="Markdown",
            )

    async def handle_bank_qr_photo(
        self, user_id: int, chat_id: int, file_id: str
    ) -> None:
        """
        Handle bank QR code photo for user bank information.
        Instead of scanning, we just store the photo and use it in admin notification.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            file_id: Telegram file ID of the QR code photo
        """
        logger.info(
            "Handling bank QR code photo",
            extra={"user_id": user_id, "chat_id": chat_id, "file_id": file_id},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            return

        # Store QR file ID for order submission
        self.state_manager.update_state(
            user_id,
            user_bank_qr_file_id=file_id,
            user_bank_info="QR Code Provided",  # Placeholder text
        )

        # Confirm and submit order
        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "✅ QR Code received!\n\n"
                "Your bank information will be shared with admin via QR code.\n\n"
                "Submitting your order..."
            ),
        )

        logger.info(
            "QR code photo stored, submitting order",
            extra={"user_id": user_id, "qr_file_id": file_id},
        )

        await self.submit_order(user_id, chat_id)

    async def handle_text_message(self, user_id: int, chat_id: int, text: str) -> None:
        """
        Handle text messages based on current state.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            text: Message text
        """
        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.debug(
                "No state found, ignoring text message", extra={"user_id": user_id}
            )
            await self.bot.send_message(
                chat_id=chat_id, text="Please use /start to begin a transaction."
            )
            return

        # Route based on current state
        if state.current_state == ConversationState.WAIT_USER_BANK:
            await self.handle_user_bank_info(user_id, chat_id, text)
        elif state.current_state == ConversationState.WAIT_ACCOUNT_NUMBER:
            await self.handle_account_number(user_id, chat_id, text)
        elif state.current_state == ConversationState.WAIT_ACCOUNT_NAME:
            await self.handle_account_name(user_id, chat_id, text)
        else:
            # Unexpected text in other states
            logger.debug(
                "Received text in unexpected state",
                extra={"user_id": user_id, "state": state.current_state.value},
            )

    async def handle_callback_query(
        self, user_id: int, chat_id: int, callback_data: str
    ) -> None:
        """
        Handle callback queries from inline buttons.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            callback_data: Callback data from button
        """
        logger.info(
            "Handling callback query",
            extra={"user_id": user_id, "chat_id": chat_id, "data": callback_data},
        )

        # Parse callback data
        if callback_data.startswith("action_"):
            action = callback_data.replace("action_", "")
            await self.handle_choose_action(user_id, chat_id, action)
        elif callback_data.startswith("paybank_"):
            # Handle payment bank selection (NEW)
            try:
                bank_id = int(callback_data.replace("paybank_", ""))
                await self.handle_payment_bank_selection(user_id, chat_id, bank_id)
            except ValueError:
                logger.error(
                    f"Invalid payment bank ID in callback data: {callback_data}"
                )
        elif callback_data.startswith("bank_"):
            # Handle user receiving bank selection
            try:
                bank_id = int(callback_data.replace("bank_", ""))
                await self.handle_bank_selection(user_id, chat_id, bank_id)
            except ValueError:
                logger.error(f"Invalid bank ID in callback data: {callback_data}")
        elif callback_data.startswith("receipt_"):
            # Handle receipt actions (add, confirm, restart, retry)
            action = callback_data.replace("receipt_", "")
            await self.handle_receipt_action(user_id, chat_id, action)
        else:
            logger.warning(
                "Unknown callback data",
                extra={"user_id": user_id, "data": callback_data},
            )

    async def handle_receipt_action(
        self, user_id: int, chat_id: int, action: str
    ) -> None:
        """
        Handle receipt action button clicks (add, confirm, restart, retry).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            action: Action to perform (add, confirm, restart, retry)
        """
        logger.info(
            "Handling receipt action",
            extra={"user_id": user_id, "chat_id": chat_id, "action": action},
        )

        # Get user state
        state = self.state_manager.get_state(user_id)
        if not state:
            logger.warning("No state found for user", extra={"user_id": user_id})
            await self.bot.send_message(
                chat_id=chat_id, text="Please use /start to begin a transaction."
            )
            return

        if action == "add":
            # User wants to add another receipt
            # Check receipt limit first
            from app.services.receipt_manager import ReceiptManager

            receipt_manager = ReceiptManager()

            is_valid, limit_error = receipt_manager.validate_receipt_limit(
                state.order_data.receipt_count, max_receipts=10
            )

            if not is_valid:
                await self.bot.send_message(chat_id=chat_id, text=limit_error)
                return

            # Update state to collecting receipts
            self.state_manager.update_state(
                user_id, new_state=ConversationState.COLLECTING_RECEIPTS
            )

            await self.bot.send_message(
                chat_id=chat_id, text="📸 Please send another receipt photo."
            )

        elif action == "confirm":
            # User confirms and wants to proceed
            # Show summary and move to user bank selection
            from app.services.receipt_manager import ReceiptManager

            receipt_manager = ReceiptManager()

            currency = "THB" if state.order_data.order_type == "buy" else "MMK"

            summary = receipt_manager.format_order_summary(
                order_type=state.order_data.order_type,
                receipt_count=state.order_data.receipt_count,
                total_amount=state.order_data.total_amount,
                currency=currency,
                bank_name=state.order_data.expected_bank_name or "Unknown",
                account_number=state.order_data.expected_account_number or "Unknown",
            )

            await self.bot.send_message(chat_id=chat_id, text=summary)

            # Move to user bank selection
            await self.show_user_bank_selection(
                user_id, chat_id, state.order_data.order_type
            )

        elif action == "restart":
            # User wants to start over
            # Clear all receipts and return to bank selection
            self.state_manager.update_state(
                user_id,
                new_state=ConversationState.SELECT_PAYMENT_BANK,
                receipt_file_ids=[],
                receipt_amounts=[],
                receipt_bank_ids=[],
                receipt_count=0,
                expected_bank_id=None,
                expected_bank_name=None,
                expected_account_number=None,
                total_amount=0.0,
                thb_amount=None,
                mmk_amount=None,
                detected_admin_bank_id=None,
                selected_payment_bank_id=None,
                selected_payment_bank_name=None,
                collected_photos=[],
                media_group_id=None,
            )

            await self.bot.send_message(
                chat_id=chat_id, text="🔄 Starting over...\n\nAll receipts cleared."
            )

            # Show bank selection again
            await self.show_payment_bank_selection(
                chat_id,
                state.order_data.order_type,
                state.order_data.exchange_rate or 0.0,
            )

        elif action == "retry":
            # User wants to retry uploading a receipt (after error)
            self.state_manager.update_state(
                user_id, new_state=ConversationState.COLLECTING_RECEIPTS
            )

            await self.bot.send_message(
                chat_id=chat_id, text="📸 Please send the receipt photo again."
            )

        else:
            logger.warning(
                "Unknown receipt action", extra={"user_id": user_id, "action": action}
            )
