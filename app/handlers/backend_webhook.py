"""
Backend webhook handler for processing notifications from the backend system.
"""

from typing import Optional
from telegram import Bot

from app.logging_config import get_logger
from app.services.user_notifier import UserNotifier
from app.services.admin_notifier import AdminNotifier
from app.services.order_completion import OrderCompletionService
from app.services.state_manager import StateManager


logger = get_logger(__name__)


class BackendWebhookHandler:
    """
    Handles webhook notifications from the backend system.

    Processes order status changes and admin replies.
    Routes notifications to appropriate services.
    """

    def __init__(
        self,
        bot: Bot,
        user_notifier: UserNotifier,
        admin_notifier: AdminNotifier,
        order_completion_service: OrderCompletionService,
        state_manager: StateManager,
    ):
        """
        Initialize the backend webhook handler.

        Args:
            bot: Telegram Bot instance
            user_notifier: UserNotifier service for sending messages to users
            admin_notifier: AdminNotifier service for sending messages to admin group
            order_completion_service: OrderCompletionService for handling order completion
            state_manager: StateManager for managing conversation states
        """
        self.bot = bot
        self.user_notifier = user_notifier
        self.admin_notifier = admin_notifier
        self.order_completion_service = order_completion_service
        self.state_manager = state_manager
        logger.info("BackendWebhookHandler initialized")

    async def handle_order_verified(self, payload):
        """
        Handle order verification notifications.

        When admin verifies an order, send notification to admin group
        with order details and receipt, waiting for staff to reply with receipt.

        Args:
            payload: BackendWebhookPayload with order information
        """
        logger.info(
            "🔔 Handling order verification",
            extra={
                "order_id": payload.order_id,
                "chat_id": payload.chat_id,
                "telegram_id": payload.telegram_id,
                "order_type": payload.order_type,
                "amount": payload.amount,
            },
        )

        try:
            # Fetch order details from backend to get complete information
            order_details = await self._fetch_order_details(payload.order_id)

            if not order_details:
                logger.error(f"❌ Could not fetch order details for {payload.order_id}")
                return

            logger.info(f"✅ Order details fetched: {order_details}")

            # Extract order information
            stored_rate = order_details.get("price", 0)
            user_bank_info = order_details.get("user_bank", "")
            receipt_paths = order_details.get(
                "receipt", ""
            )  # Can be comma-separated paths

            # Fetch current exchange rates from backend
            exchange_rates = await self._fetch_exchange_rates()

            # Use the correct rate based on order type
            if payload.order_type == "buy":
                exchange_rate = (
                    exchange_rates.get("buy", stored_rate)
                    if exchange_rates
                    else stored_rate
                )
            else:
                exchange_rate = (
                    exchange_rates.get("sell", stored_rate)
                    if exchange_rates
                    else stored_rate
                )

            logger.info(
                f"💱 Using exchange rate: {exchange_rate} for {payload.order_type} order"
            )

            # Calculate amounts based on order type
            if payload.order_type == "buy":
                sent_currency = "THB"
                received_currency = "MMK"
                sent_amount = payload.amount

                if exchange_rate < 1:
                    raw_mmk = sent_amount / exchange_rate
                    operation_symbol = "÷"
                else:
                    raw_mmk = sent_amount * exchange_rate
                    operation_symbol = "×"

                import math

                received_amount = math.ceil(raw_mmk / 100) * 100
            else:
                sent_currency = "MMK"
                received_currency = "THB"
                sent_amount = payload.amount

                if exchange_rate < 1:
                    received_amount = sent_amount * exchange_rate
                    operation_symbol = "×"
                else:
                    received_amount = sent_amount / exchange_rate
                    operation_symbol = "÷"

            # Send notification to admin buy/sell topic
            topic_id = (
                self.admin_notifier.buy_topic_id
                if payload.order_type == "buy"
                else self.admin_notifier.sell_topic_id
            )

            # Format message for admin (will be used as photo caption)
            admin_message = (
                f"Order: {payload.order_id}\n"
                f"{'Buy' if payload.order_type == 'buy' else 'Sell'} "
                f"{sent_amount:,.0f} {operation_symbol} {exchange_rate:.2f} = "
                f"{received_amount:,.0f}\n"
                f"{user_bank_info}"
            )

            logger.info(f"📤 Sending notification to admin topic {topic_id}")

            # Send receipt photo(s) with order details as caption
            if receipt_paths:
                await self._send_receipt_to_admin(
                    topic_id=topic_id,
                    receipt_paths=receipt_paths,
                    caption=admin_message,
                )
                logger.info(f"✅ Admin topic notification sent with receipt")
            else:
                # If no receipt, send as text message
                await self.bot.send_message(
                    chat_id=self.admin_notifier.admin_group_id,
                    message_thread_id=topic_id,
                    text=admin_message,
                )
                logger.info(f"✅ Admin topic notification sent (no receipt)")

            logger.info(f"Successfully processed verified order {payload.order_id}")

        except Exception as e:
            logger.error(
                f"Error handling verified order: {e}",
                extra={"order_id": payload.order_id},
                exc_info=True,
            )

    async def handle_order_status_changed(self, payload):
        """
        Handle order status change notifications.

        Routes to appropriate handler based on status:
        - "approved" or "completed": Send success message to user
        - "declined" or "rejected": Send rejection message to user

        Args:
            payload: BackendWebhookPayload with order status information
        """
        logger.info(
            "🔔 Handling order status change",
            extra={
                "order_id": payload.order_id,
                "status": payload.status,
                "chat_id": payload.chat_id,
                "telegram_id": payload.telegram_id,
                "order_type": payload.order_type,
                "amount": payload.amount,
            },
        )

        try:
            # Use chat_id as user_id (it's the numeric Telegram user ID)
            user_id = payload.chat_id

            logger.info(
                f"Processing order {payload.order_id} with user_id={user_id}, chat_id={payload.chat_id}"
            )

            # Handle approved/completed orders
            if payload.status in ["approved", "completed"]:
                logger.info(f"✅ Order approved, calling _handle_order_approved")
                await self._handle_order_approved(payload, user_id)

            # Handle declined/rejected orders
            elif payload.status in ["declined", "rejected"]:
                logger.info(f"❌ Order declined, calling _handle_order_rejected")
                await self._handle_order_rejected(payload, user_id)

            else:
                logger.warning(
                    f"Unknown order status: {payload.status}",
                    extra={"order_id": payload.order_id, "status": payload.status},
                )

        except Exception as e:
            logger.error(
                f"💥 Error handling order status change: {e}",
                extra={
                    "order_id": payload.order_id,
                    "status": payload.status,
                    "error": str(e),
                },
                exc_info=True,
            )

    async def _handle_order_approved(self, payload, user_id: int):
        """
        Handle approved order - send success message to user and notification to admin.

        Args:
            payload: BackendWebhookPayload with order information
            user_id: User's Telegram ID
        """
        try:
            logger.info(f"📥 Fetching order details for {payload.order_id}")

            # Fetch order details from backend to get complete information
            order_details = await self._fetch_order_details(payload.order_id)

            if not order_details:
                logger.error(f"❌ Could not fetch order details for {payload.order_id}")
                return

            logger.info(f"✅ Order details fetched: {order_details}")

            # Extract order information
            stored_rate = order_details.get("price", 0)
            user_bank_info = order_details.get("user_bank", "")
            receipt_paths = order_details.get(
                "receipt", ""
            )  # Can be comma-separated paths

            # Fetch current exchange rates from backend
            exchange_rates = await self._fetch_exchange_rates()

            # Use the correct rate based on order type
            if payload.order_type == "buy":
                # For buy orders, use buy rate
                exchange_rate = (
                    exchange_rates.get("buy", stored_rate)
                    if exchange_rates
                    else stored_rate
                )
            else:
                # For sell orders, use sell rate
                exchange_rate = (
                    exchange_rates.get("sell", stored_rate)
                    if exchange_rates
                    else stored_rate
                )

            logger.info(
                f"💱 Using exchange rate: {exchange_rate} for {payload.order_type} order"
            )

            # Determine currencies and calculate amounts based on order type
            # Note: exchange_rate format depends on how it's stored in database
            # If rate < 1 (e.g., 0.0035): it means 1 MMK = 0.0035 THB, so THB = MMK * rate
            # If rate > 1 (e.g., 125.78): it means 1 THB = 125.78 MMK, so MMK = THB * rate

            if payload.order_type == "buy":
                # Buy: user sends THB, receives MMK
                sent_currency = "THB"
                received_currency = "MMK"
                sent_amount = payload.amount

                # Determine calculation based on rate magnitude
                if exchange_rate < 1:
                    # Rate is MMK to THB (e.g., 0.0035 means 1 MMK = 0.0035 THB)
                    # So: MMK = THB / rate
                    raw_mmk = sent_amount / exchange_rate
                    operation_symbol = "÷"
                    logger.info(
                        f"💰 Buy calculation (rate<1): {sent_amount} / {exchange_rate} = {raw_mmk}"
                    )
                else:
                    # Rate is THB to MMK (e.g., 125.78 means 1 THB = 125.78 MMK)
                    # So: MMK = THB * rate
                    raw_mmk = sent_amount * exchange_rate
                    operation_symbol = "×"
                    logger.info(
                        f"💰 Buy calculation (rate>1): {sent_amount} * {exchange_rate} = {raw_mmk}"
                    )

                # Round to nearest 100
                # If amount ends in 01-99, round UP to next 100
                # If amount ends in 00, keep as is
                import math

                received_amount = math.ceil(raw_mmk / 100) * 100
                logger.info(f"💰 Rounded: {raw_mmk} → {received_amount}")
            else:
                # Sell: user sends MMK, receives THB
                sent_currency = "MMK"
                received_currency = "THB"
                sent_amount = payload.amount

                # Determine calculation based on rate magnitude
                if exchange_rate < 1:
                    # Rate is MMK to THB (e.g., 0.0034 means 1 MMK = 0.0034 THB)
                    # So: THB = MMK * rate
                    received_amount = sent_amount * exchange_rate
                    operation_symbol = "×"
                    logger.info(
                        f"💰 Sell calculation (rate<1): {sent_amount} * {exchange_rate} = {received_amount}"
                    )
                else:
                    # Rate is THB to MMK (e.g., 125.78 means 1 THB = 125.78 MMK)
                    # So: THB = MMK / rate
                    received_amount = sent_amount / exchange_rate
                    operation_symbol = "÷"
                    logger.info(
                        f"💰 Sell calculation (rate>1): {sent_amount} / {exchange_rate} = {received_amount}"
                    )

            # Format message for user (without currency suffixes, single line)
            user_message = (
                f"{'Buy' if payload.order_type == 'buy' else 'Sell'} "
                f"{sent_amount:,.0f} {operation_symbol} {exchange_rate:.2f} = "
                f"{received_amount:,.0f}"
            )

            # Note: Admin notification was already sent when order was verified
            # This handler is called when order status changes to "approved" after staff receipt verification
            # Success message to user and balance notification are sent by admin message handler

            logger.info(
                f"Successfully processed approved order {payload.order_id}",
                extra={"order_id": payload.order_id, "user_id": user_id},
            )

        except Exception as e:
            logger.error(
                f"Error handling approved order: {e}",
                extra={"order_id": payload.order_id, "user_id": user_id},
                exc_info=True,
            )
            # Try to send error message to user
            try:
                await self.user_notifier.send_error_message(
                    chat_id=payload.chat_id,
                    user_id=user_id,
                    error_message="There was an error processing your order completion. Please contact support.",
                )
            except Exception as e:
                logger.error(
                    f"Failed to send error notification to user {user_id}: {e}",
                    exc_info=True,
                )

    async def _fetch_order_details(self, order_id: str) -> Optional[dict]:
        """
        Fetch complete order details from backend.

        Args:
            order_id: Order ID to fetch

        Returns:
            Order details dict or None if fetch fails
        """
        try:
            # Use the order completion service's backend client
            import aiohttp

            backend_url = self.order_completion_service.backend_api_url

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{backend_url}/api/orders/{order_id}",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(
                            f"Failed to fetch order {order_id}: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error fetching order details: {e}", exc_info=True)
            return None

    async def _fetch_exchange_rates(self) -> Optional[dict]:
        """
        Fetch current exchange rates from backend.

        Returns:
            Dict with 'buy' and 'sell' rates, or None if fetch fails
        """
        try:
            import aiohttp

            backend_url = self.order_completion_service.backend_api_url

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{backend_url}/api/settings",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {"buy": data.get("buy", 0), "sell": data.get("sell", 0)}
                    else:
                        logger.error(
                            f"Failed to fetch exchange rates: {response.status}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Error fetching exchange rates: {e}", exc_info=True)
            return None

    async def _send_receipt_to_admin(
        self, topic_id: int, receipt_paths: str, caption: str
    ):
        """
        Send user's receipt photo(s) to admin topic.

        Args:
            topic_id: Topic ID to send to
            receipt_paths: Comma-separated receipt file paths
            caption: Caption for the photo(s)
        """
        try:
            import aiohttp
            from telegram import InputMediaPhoto

            backend_url = self.order_completion_service.backend_api_url

            # Parse receipt paths (can be comma-separated)
            paths = [p.strip() for p in receipt_paths.split(",") if p.strip()]

            if not paths:
                logger.warning("No receipt paths to send")
                return

            logger.info(f"📸 Sending {len(paths)} receipt(s) to admin topic")

            # Download and send receipt images
            async with aiohttp.ClientSession() as session:
                if len(paths) == 1:
                    # Single receipt - send as photo with caption
                    receipt_path = paths[0]
                    if not receipt_path.startswith("http"):
                        receipt_url = f"{backend_url}/{receipt_path.lstrip('/')}"
                    else:
                        receipt_url = receipt_path

                    async with session.get(receipt_url) as response:
                        if response.status == 200:
                            receipt_bytes = await response.read()
                            await self.bot.send_photo(
                                chat_id=self.admin_notifier.admin_group_id,
                                message_thread_id=topic_id,
                                photo=receipt_bytes,
                                caption=caption,
                            )
                            logger.info("✅ Receipt photo sent to admin")
                        else:
                            logger.error(
                                f"Failed to download receipt: {response.status}"
                            )
                else:
                    # Multiple receipts - send as media group
                    media = []
                    for idx, receipt_path in enumerate(paths):
                        if not receipt_path.startswith("http"):
                            receipt_url = f"{backend_url}/{receipt_path.lstrip('/')}"
                        else:
                            receipt_url = receipt_path

                        async with session.get(receipt_url) as response:
                            if response.status == 200:
                                receipt_bytes = await response.read()
                                # Add caption only to first photo
                                photo_caption = caption if idx == 0 else None
                                media.append(
                                    InputMediaPhoto(
                                        media=receipt_bytes, caption=photo_caption
                                    )
                                )
                            else:
                                logger.error(
                                    f"Failed to download receipt {idx}: {response.status}"
                                )

                    if media:
                        await self.bot.send_media_group(
                            chat_id=self.admin_notifier.admin_group_id,
                            message_thread_id=topic_id,
                            media=media,
                        )
                        logger.info(f"✅ {len(media)} receipt photos sent to admin")

        except Exception as e:
            logger.error(f"Error sending receipt to admin: {e}", exc_info=True)

    async def _handle_order_rejected(self, payload, user_id: int):
        """
        Handle rejected order - send rejection message to user.

        Args:
            payload: BackendWebhookPayload with order information
            user_id: User's Telegram ID
        """
        try:
            # Send rejection message to user
            await self.user_notifier.send_order_rejected_message(
                chat_id=payload.chat_id,
                user_id=user_id,
                order_id=payload.order_id,
                reason=None,  # Could be added to payload if backend provides it
            )

            logger.info(
                f"Successfully processed rejected order {payload.order_id}",
                extra={"order_id": payload.order_id, "user_id": user_id},
            )

        except Exception as e:
            logger.error(
                f"Error handling rejected order: {e}",
                extra={"order_id": payload.order_id, "user_id": user_id},
                exc_info=True,
            )

    async def handle_admin_replied(self, payload):
        """
        Handle admin reply notifications.

        Forwards admin messages to the user.

        Args:
            payload: BackendWebhookPayload with admin reply information
        """
        logger.info(
            "🔔 Handling admin reply",
            extra={
                "order_id": payload.order_id,
                "chat_id": payload.chat_id,
                "telegram_id": payload.telegram_id,
                "message_content": payload.message_content,
            },
        )

        try:
            # Send admin's message to the user
            if payload.message_content:
                await self.bot.send_message(
                    chat_id=payload.chat_id, text=f"{payload.message_content}"
                )
                logger.info(
                    f"✅ Admin message forwarded to user",
                    extra={"order_id": payload.order_id, "chat_id": payload.chat_id},
                )
            else:
                logger.warning(
                    "No message content in admin reply",
                    extra={"order_id": payload.order_id},
                )

        except Exception as e:
            logger.error(
                f"❌ Error forwarding admin message to user: {e}",
                extra={"order_id": payload.order_id, "chat_id": payload.chat_id},
                exc_info=True,
            )
