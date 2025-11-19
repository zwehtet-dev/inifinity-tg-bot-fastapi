"""
Admin message handler for processing staff receipt replies in admin group.
"""

import re
from typing import Optional
from telegram import Bot, Update, Message
from telegram.ext import ContextTypes

from app.logging_config import get_logger
from app.services.ocr_service import OCRService
from app.services.order_completion import OrderCompletionService
from app.services.admin_notifier import AdminNotifier
from app.services.user_notifier import UserNotifier


logger = get_logger(__name__)


class AdminMessageHandler:
    """
    Handles messages in the admin group, specifically staff receipt replies.

    When staff replies to an order notification with a receipt photo,
    this handler verifies the receipt amount and processes the order completion.
    """

    def __init__(
        self,
        bot: Bot,
        admin_group_id: int,
        buy_topic_id: int,
        sell_topic_id: int,
        ocr_service: OCRService,
        order_completion_service: OrderCompletionService,
        admin_notifier: AdminNotifier,
        user_notifier: UserNotifier,
        backend_api_url: str,
        backend_webhook_secret: str,
        settings_service=None,
    ):
        """
        Initialize the admin message handler.

        Args:
            bot: Telegram Bot instance
            admin_group_id: Admin group chat ID
            buy_topic_id: Buy topic ID
            sell_topic_id: Sell topic ID
            ocr_service: OCR service for receipt extraction
            order_completion_service: Service for completing orders
            admin_notifier: Service for sending admin notifications
            user_notifier: Service for sending user notifications
            backend_api_url: Backend API URL for fetching order details
            backend_webhook_secret: Backend webhook secret for API authentication
            settings_service: Settings service for accessing bank data (optional)
        """
        self.bot = bot
        self.admin_group_id = admin_group_id
        self.buy_topic_id = buy_topic_id
        self.sell_topic_id = sell_topic_id
        self.ocr_service = ocr_service
        self.order_completion_service = order_completion_service
        self.admin_notifier = admin_notifier
        self.user_notifier = user_notifier
        self.backend_api_url = backend_api_url.rstrip("/")
        self.backend_webhook_secret = backend_webhook_secret
        self.settings_service = settings_service
        logger.info("AdminMessageHandler initialized")

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle messages in admin group.

        Checks if message is a reply to bot's order notification with a receipt photo.
        If so, processes the staff receipt verification.

        Args:
            update: Telegram update object
            context: Telegram context
        """
        message = update.message

        # Check if message is in admin group
        if message.chat_id != self.admin_group_id:
            return

        # Check if message is in buy or sell topic
        if message.message_thread_id not in [self.buy_topic_id, self.sell_topic_id]:
            logger.debug(f"Message not in buy/sell topic: {message.message_thread_id}")
            return

        # Check if message is a reply
        if not message.reply_to_message:
            logger.debug("Message is not a reply")
            return

        # Check if reply is to bot's message
        # Get bot info to compare
        try:
            bot_user = await self.bot.get_me()
            if message.reply_to_message.from_user.id != bot_user.id:
                logger.debug("Reply is not to bot's message")
                return
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return

        # Check if message contains a photo (receipt)
        if message.photo:
            logger.info(
                "📸 Staff receipt detected in admin group",
                extra={
                    "message_id": message.message_id,
                    "topic_id": message.message_thread_id,
                    "from_user": message.from_user.username or message.from_user.id,
                },
            )

            # Process the staff receipt (no order ID needed)
            await self._process_staff_receipt(
                message=message, topic_id=message.message_thread_id
            )
            return

        # Check if message contains text (Reject or Complain)
        if message.text:
            text = message.text.strip()
            
            # Check for Reject: prefix
            if text.startswith("Reject:") or text.startswith("reject:"):
                logger.info(
                    "❌ Staff rejection detected in admin group",
                    extra={
                        "message_id": message.message_id,
                        "topic_id": message.message_thread_id,
                        "from_user": message.from_user.username or message.from_user.id,
                    },
                )
                await self._process_staff_rejection(message=message)
                return
            
            # Check for Complain: prefix
            if text.startswith("Complain:") or text.startswith("complain:"):
                logger.info(
                    "⚠️ Staff complaint detected in admin group",
                    extra={
                        "message_id": message.message_id,
                        "topic_id": message.message_thread_id,
                        "from_user": message.from_user.username or message.from_user.id,
                    },
                )
                await self._process_staff_complaint(message=message)
                return
            
            logger.debug("Message text does not match Reject: or Complain: pattern")
            return

        logger.debug("Message does not contain photo or text")
        return

    async def _process_staff_receipt(self, message: Message, topic_id: int) -> None:
        """
        Process staff receipt: extract amount and verify.

        Args:
            message: Staff's message with receipt photo
            topic_id: Topic ID where message was sent
        """
        try:
            # Work silently in background - no acknowledgment message
            
            # Extract order ID from original message (for reference only)
            order_id = self._extract_order_id_from_message(message.reply_to_message)
            if order_id:
                logger.info(f"Found order ID: {order_id}")

            # Extract bank display name from admin's message caption/text
            admin_message_text = message.caption or message.text or ""
            admin_bank_display_name = self._extract_bank_display_name(admin_message_text)
            
            # Track if we need to request display name confirmation
            needs_display_name_confirmation = False
            
            if admin_bank_display_name:
                logger.info(f"Admin specified bank: {admin_bank_display_name}")
            else:
                logger.warning("Admin did not specify bank display name in message")
                needs_display_name_confirmation = True

            # Get the original message text/caption to extract expected amount
            original_text = (
                message.reply_to_message.text or message.reply_to_message.caption or ""
            )

            # Parse expected amount from original message
            # Format: "Buy 1000 x 125.78 = 125780" or "Sell 125000 ÷ 125.78 = 993.80"
            expected_info = self._parse_expected_amount(original_text)

            if not expected_info:
                await message.reply_text(
                    "❌ Could not parse expected amount from original message.\n"
                    "Please ensure you're replying to an order notification."
                )
                return

            expected_amount = expected_info["expected_amount"]
            expected_currency = expected_info["currency"]
            order_type = expected_info["order_type"]
            user_sent_amount = expected_info["user_amount"]

            # Set tolerance based on currency
            if expected_currency == "MMK":
                tolerance = 1000  # ±1000 MMK
            else:
                tolerance = 35  # ±35 THB

            logger.info(
                f"Expected staff to send: {expected_amount:.2f} {expected_currency} "
                f"(tolerance: ±{tolerance})"
            )

            # Download and process receipt image
            photo = message.photo[-1]  # Get largest photo
            file = await self.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()

            # Extract amount from receipt using simplified OCR for staff receipts
            receipt_data = await self._extract_amount_from_staff_receipt(
                bytes(image_bytes)
            )

            if not receipt_data or not receipt_data.amount:
                logger.error("OCR failed to extract amount from staff receipt")
                await message.reply_text(
                    "❌ Could not read amount from receipt.\n"
                    "Please ensure the receipt is clear and try again."
                )
                return

            staff_sent_amount = receipt_data.amount

            logger.info(
                f"Staff receipt amount: {staff_sent_amount:.2f} {expected_currency}"
            )

            # Verify amount matches (within tolerance)
            amount_diff = abs(staff_sent_amount - expected_amount)

            if amount_diff <= tolerance:
                # Amount matches - proceed with completion silently
                logger.info(
                    f"✅ Amount verified: {staff_sent_amount:.2f} ≈ {expected_amount:.2f} "
                    f"(diff: {amount_diff:.2f}, tolerance: {tolerance})"
                )

                # No message to admin - work silently in background
                
                # If we have order ID, we can update balances and notify user
                if order_id:
                    # Fetch full order details for bank IDs
                    order_details = await self._fetch_order_details(order_id)

                    if order_details:
                        thai_bank_id = order_details.get("thai_bank_account_id")
                        myanmar_bank_id = order_details.get("myanmar_bank_account_id")
                        chat_id = order_details.get("telegram", {}).get("chat_id")
                        exchange_rate = order_details.get("price", 0)
                        
                        # Log the bank IDs from order
                        logger.info(
                            f"📋 Bank IDs from order {order_id}:",
                            extra={
                                "order_id": order_id,
                                "thai_bank_id": thai_bank_id,
                                "myanmar_bank_id": myanmar_bank_id,
                                "order_type": order_type
                            }
                        )
                        
                        # Validate bank IDs
                        if order_type == "buy" and not thai_bank_id:
                            logger.error(f"❌ BUY order {order_id} missing thai_bank_id!")
                            await message.reply_text(
                                f"⚠️ Order {order_id} is missing Thai bank ID.\n"
                                "Cannot update balances. Please update manually."
                            )
                            return
                        
                        if order_type == "sell" and not myanmar_bank_id:
                            logger.error(f"❌ SELL order {order_id} missing myanmar_bank_id!")
                            await message.reply_text(
                                f"⚠️ Order {order_id} is missing Myanmar bank ID.\n"
                                "Cannot update balances. Please update manually."
                            )
                            return

                        # Validate and process admin-specified bank display name
                        # For BUY: admin specifies which Myanmar bank to send MMK from
                        # For SELL: admin specifies which Thai bank to send THB from
                        
                        # Determine which bank list to validate against
                        if order_type == "buy":
                            # BUY: admin sends MMK, so validate against Myanmar banks
                            validation_currency = "MMK"
                            validation_bank_list = "Myanmar"
                        else:
                            # SELL: admin sends THB, so validate against Thai banks
                            validation_currency = "THB"
                            validation_bank_list = "Thai"
                        
                        # If admin provided display name, validate it
                        if admin_bank_display_name and not needs_display_name_confirmation:
                            admin_bank_id = await self._find_bank_id_by_display_name(
                                admin_bank_display_name, order_type, validation_currency
                            )
                            
                            if admin_bank_id:
                                # Valid bank found
                                if order_type == "buy":
                                    # BUY: admin sends MMK from this Myanmar bank
                                    myanmar_bank_id = admin_bank_id
                                    logger.info(f"✅ Using admin-specified Myanmar bank ID: {admin_bank_id} ({admin_bank_display_name})")
                                else:
                                    # SELL: admin sends THB from this Thai bank
                                    thai_bank_id = admin_bank_id
                                    logger.info(f"✅ Using admin-specified Thai bank ID: {admin_bank_id} ({admin_bank_display_name})")
                            else:
                                # Display name not found in bank list - request confirmation
                                logger.warning(f"❌ Display name '{admin_bank_display_name}' not found in {validation_bank_list} banks")
                                needs_display_name_confirmation = True
                        
                        # If we need display name confirmation, request it from admin
                        if needs_display_name_confirmation:
                            await self._request_display_name_confirmation(
                                message=message,
                                order_id=order_id,
                                order_type=order_type,
                                provided_name=admin_bank_display_name,
                                expected_currency=validation_currency,
                                expected_bank_list=validation_bank_list
                            )
                            return  # Stop processing until admin confirms

                        # Determine which bank to reduce (admin sends from) and which to increase (user sent to)
                        # For BUY: User sent THB to thai_bank_id (from order), Admin sends MMK from myanmar_bank_id (admin specified)
                        # For SELL: User sent MMK to myanmar_bank_id (from order), Admin sends THB from thai_bank_id (admin specified)
                        
                        if order_type == "buy":
                            # BUY: Increase Thai bank (user sent THB), Decrease Myanmar bank (admin sends MMK)
                            bank_to_increase_id = thai_bank_id  # Thai bank from order (user sent THB here)
                            bank_to_increase_amount = user_sent_amount
                            bank_to_increase_currency = "THB"
                            
                            bank_to_decrease_id = myanmar_bank_id  # Myanmar bank admin specified (admin sends MMK from here)
                            bank_to_decrease_amount = staff_sent_amount
                            bank_to_decrease_currency = "MMK"
                        else:
                            # SELL: Increase Myanmar bank (user sent MMK), Decrease Thai bank (admin sends THB)
                            bank_to_increase_id = myanmar_bank_id  # Myanmar bank from order (user sent MMK here)
                            bank_to_increase_amount = user_sent_amount
                            bank_to_increase_currency = "MMK"
                            
                            bank_to_decrease_id = thai_bank_id  # Thai bank admin specified (admin sends THB from here)
                            bank_to_decrease_amount = staff_sent_amount
                            bank_to_decrease_currency = "THB"
                        
                        logger.info(
                            f"💰 Balance adjustment for {order_type.upper()} order {order_id}:",
                            extra={
                                "order_id": order_id,
                                "order_type": order_type,
                                "increase_bank_id": bank_to_increase_id,
                                "increase_amount": bank_to_increase_amount,
                                "increase_currency": bank_to_increase_currency,
                                "decrease_bank_id": bank_to_decrease_id,
                                "decrease_amount": bank_to_decrease_amount,
                                "decrease_currency": bank_to_decrease_currency
                            }
                        )
                        
                        # Update bank balances
                        success = await self._update_bank_balances(
                            order_id=order_id,
                            order_type=order_type,
                            user_sent_amount=user_sent_amount,
                            staff_sent_amount=staff_sent_amount,
                            thai_bank_id=thai_bank_id,
                            myanmar_bank_id=myanmar_bank_id,
                        )

                        if not success:
                            await message.reply_text(
                                "⚠️ Receipt verified but failed to update bank balances. "
                                "Please check logs and update manually."
                            )
                            return

                        # Update order status to "approved"
                        status_updated = await self._update_order_status(
                            order_id, "approved"
                        )
                        if not status_updated:
                            logger.warning(
                                f"⚠️ Failed to update order status to approved for {order_id}"
                            )
                            await message.reply_text(
                                "⚠️ Balances updated but failed to update order status. "
                                "Please update order status to 'approved' manually."
                            )

                        # Send balance notification with update details
                        myanmar_banks, thai_banks, balances = (
                            await self.order_completion_service.fetch_all_banks_with_balances()
                        )
                        
                        # Build balance update message
                        balance_update_msg = (
                            f"💰 Balance Updated - Order {order_id}\n\n"
                            f"Type: {order_type.upper()}\n"
                        )
                        
                        if order_type == "buy":
                            # BUY: User sent THB, Admin sent MMK
                            balance_update_msg += (
                                f"✅ Thai Bank +{user_sent_amount:,.2f} THB (user payment received)\n"
                                f"➖ Myanmar Bank -{staff_sent_amount:,.2f} MMK (sent to user)\n"
                            )
                        else:
                            # SELL: User sent MMK, Admin sent THB
                            balance_update_msg += (
                                f"✅ Myanmar Bank +{user_sent_amount:,.2f} MMK (user payment received)\n"
                                f"➖ Thai Bank -{staff_sent_amount:,.2f} THB (sent to user)\n"
                            )
                        
                        balance_update_msg += "\n📊 Current Balances:\n"
                        
                        # Send balance update notification to admin group
                        await self.bot.send_message(
                            chat_id=self.admin_group_id,
                            text=balance_update_msg,
                            message_thread_id=message.message_thread_id
                        )
                        
                        # Send full balance notification
                        await self.admin_notifier.send_balance_notification(
                            myanmar_banks=myanmar_banks,
                            thai_banks=thai_banks,
                            balances=balances,
                        )

                        # Upload admin confirmation receipt to backend
                        logger.info(
                            f"📤 Uploading admin confirmation receipt for order {order_id}"
                        )
                        receipt_uploaded = await self._upload_confirm_receipt(
                            order_id, photo.file_id
                        )

                        if not receipt_uploaded:
                            logger.warning(
                                f"⚠️ Failed to upload confirmation receipt for order {order_id}"
                            )

                        # Notify user of completion
                        if chat_id:
                            logger.info(
                                f"📤 Sending success notification to user (chat_id={chat_id})"
                            )
                            try:
                                await self.user_notifier.send_success_message(
                                    chat_id=int(chat_id),
                                    user_id=int(chat_id),
                                    order_id=order_id,
                                    order_type=order_type,
                                    sent_amount=user_sent_amount,
                                    sent_currency=(
                                        "THB" if order_type == "buy" else "MMK"
                                    ),
                                    received_amount=staff_sent_amount,
                                    received_currency=expected_currency,
                                    exchange_rate=exchange_rate,
                                    admin_receipt_file_id=photo.file_id,
                                )
                                logger.info(
                                    f"✅ User notification sent successfully to chat_id={chat_id}"
                                )
                            except Exception as notify_error:
                                logger.error(
                                    f"❌ Failed to send user notification: {notify_error}",
                                    exc_info=True,
                                )
                                await message.reply_text(
                                    f"⚠️ Order completed but failed to notify user.\n"
                                    f"Error: {str(notify_error)}\n"
                                    f"Please notify user manually."
                                )
                                return
                        else:
                            logger.warning(
                                f"⚠️ No chat_id found for order {order_id}, cannot notify user"
                            )

                        # Don't send success message in admin group to reduce noise
                        logger.info(
                            f"✅ Order {order_id} completed successfully! "
                            f"Bank balances updated and user notified."
                        )
                    else:
                        await message.reply_text(
                            "✅ Amount verified but could not fetch order details.\n"
                            "Please update balances manually."
                        )
                else:
                    await message.reply_text(
                        "✅ Amount verified!\n"
                        "Note: Could not find order ID, please update balances manually."
                    )

            else:
                # Amount mismatch - only show simple error
                logger.warning(
                    f"❌ Amount mismatch: {staff_sent_amount:.2f} vs {expected_amount:.2f} "
                    f"(diff: {amount_diff:.2f}, tolerance: {tolerance})"
                )

                await message.reply_text("❌ Amount not match")

        except Exception as e:
            logger.error(f"Error processing staff receipt: {e}", exc_info=True)
            await message.reply_text(
                f"❌ Error processing receipt: {str(e)}\n"
                f"Please contact admin for manual processing."
            )

    def _extract_order_id_from_message(self, message: Message) -> Optional[str]:
        """
        Extract order ID from message text/caption.

        Looks for patterns:
        - "251225A0001B" on first line (new simplified format)
        - "Order: 251225A0001B" (old format)
        - "251225A0001B" anywhere in text (fallback)

        Args:
            message: Message to extract from

        Returns:
            Order ID or None
        """
        if not message:
            return None

        text = message.text or message.caption or ""
        
        if not text:
            return None

        # Try to find order ID on first line (new simplified format)
        # Pattern: DDMMYYA####B/S (e.g., 251225A0001B)
        lines = text.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            pattern = r"^(\d{6}A\d{4}[BS])$"
            match = re.match(pattern, first_line)
            if match:
                logger.info(f"Found order ID on first line: {match.group(1)}")
                return match.group(1)

        # Try to find "Order: XXXXXX" format (old format)
        order_pattern = r"Order:\s*(\d{6}A\d{4}[BS])"
        order_match = re.search(order_pattern, text, re.IGNORECASE)
        if order_match:
            logger.info(f"Found order ID with 'Order:' prefix: {order_match.group(1)}")
            return order_match.group(1)

        # Fallback: find order ID pattern anywhere in text
        pattern = r"\d{6}A\d{4}[BS]"
        match = re.search(pattern, text)
        if match:
            logger.info(f"Found order ID in text: {match.group(0)}")
            return match.group(0)

        logger.warning(f"Could not extract order ID from message: {text[:100]}")
        return None

    async def _extract_amount_from_staff_receipt(
        self, image_bytes: bytes
    ) -> Optional[any]:
        """
        Extract amount from staff receipt using simplified OCR.

        This uses a custom prompt optimized for staff receipts that only extracts
        the transfer amount without bank validation.

        Args:
            image_bytes: Receipt image bytes

        Returns:
            ReceiptData-like object with amount, or None if extraction fails
        """
        try:
            import base64
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage
            from app.config import get_settings

            settings = get_settings()

            # Encode image
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{image_base64}"

            # Simplified prompt for staff receipts - only extract amount
            prompt = """You are analyzing a bank transfer receipt from staff to a customer.

**Your task: Extract ONLY the transfer amount from this receipt.**

Look for:
- The main transfer/payment amount (usually the largest number)
- Keywords: "Amount", "จำนวนเงิน", "Total", "ยอดโอน", "Transfer Amount"
- Ignore: fees, balance, previous transactions

**CRITICAL RULES:**
1. Extract ONLY the numeric value (no currency symbols, no commas)
2. This should be the amount SENT/TRANSFERRED (not balance, not fee)
3. If you cannot find a clear transfer amount, return 0
4. Common formats: "200,000", "200000", "200,000.00"

**Examples:**
- Receipt shows "จำนวนเงิน 200,000 บาท" → Return: 200000
- Receipt shows "Transfer Amount: 125,780 MMK" → Return: 125780
- Receipt shows "Amount: 1,500.00" → Return: 1500

Return the data in this exact JSON format:
{
    "amount": <numeric_value>,
    "bank_name": "STAFF_RECEIPT",
    "account_number": "N/A",
    "account_name": "N/A",
    "confidence_score": 1.0
}

If you cannot find a transfer amount, return:
{
    "amount": 0,
    "bank_name": "UNCLEAR",
    "account_number": "N/A",
    "account_name": "N/A",
    "confidence_score": 0.0
}"""

            # Initialize LLM with structured output
            from app.models.receipt import ReceiptData

            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                openai_api_key=settings.openai_api_key,
                max_tokens=500,
            ).with_structured_output(ReceiptData)

            # Create message
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url, "detail": "high"},
                    },
                ]
            )

            logger.info(
                "🔍 Extracting amount from staff receipt with simplified OCR..."
            )

            # Invoke with timeout
            import asyncio

            result = await asyncio.wait_for(llm.ainvoke([message]), timeout=30)

            if result and result.amount > 0:
                logger.info(f"✅ Extracted amount from staff receipt: {result.amount}")
                return result
            else:
                logger.warning("❌ Could not extract valid amount from staff receipt")
                return None

        except Exception as e:
            logger.error(
                f"Error extracting amount from staff receipt: {e}", exc_info=True
            )
            return None

    def _parse_expected_amount(self, text: str) -> Optional[dict]:
        """
        Parse expected amount from order notification message.

        Formats:
        - "Buy 1000 x 125.78 = 125780" (user sends THB, staff sends MMK)
        - "Sell 125000 ÷ 125.78 = 993.80" (user sends MMK, staff sends THB)

        Args:
            text: Message text to parse

        Returns:
            Dict with order_type, user_amount, expected_amount, currency
        """
        try:
            # Try Buy format: "Buy {amount} x {rate} = {result}"
            buy_pattern = r"Buy\s+([\d,]+(?:\.\d+)?)\s*[x×]\s*([\d,]+(?:\.\d+)?)\s*=\s*([\d,]+(?:\.\d+)?)"
            buy_match = re.search(buy_pattern, text, re.IGNORECASE)

            if buy_match:
                user_amount = float(buy_match.group(1).replace(",", ""))
                expected_amount = float(buy_match.group(3).replace(",", ""))
                return {
                    "order_type": "buy",
                    "user_amount": user_amount,
                    "expected_amount": expected_amount,
                    "currency": "MMK",
                }

            # Try Sell format: "Sell {amount} ÷ {rate} = {result}"
            sell_pattern = r"Sell\s+([\d,]+(?:\.\d+)?)\s*[÷/]\s*([\d,]+(?:\.\d+)?)\s*=\s*([\d,]+(?:\.\d+)?)"
            sell_match = re.search(sell_pattern, text, re.IGNORECASE)

            if sell_match:
                user_amount = float(sell_match.group(1).replace(",", ""))
                expected_amount = float(sell_match.group(3).replace(",", ""))
                return {
                    "order_type": "sell",
                    "user_amount": user_amount,
                    "expected_amount": expected_amount,
                    "currency": "THB",
                }

            logger.warning(f"Could not parse expected amount from: {text[:100]}")
            return None

        except Exception as e:
            logger.error(f"Error parsing expected amount: {e}")
            return None

    async def _fetch_order_details(self, order_id: str) -> Optional[dict]:
        """
        Fetch order details from backend.

        Args:
            order_id: Order ID to fetch

        Returns:
            Order details dict or None if fetch fails
        """
        try:
            import aiohttp

            headers = {"X-Backend-Secret": self.backend_webhook_secret}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.backend_api_url}/api/orders/{order_id}",
                    headers=headers,
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

    async def _upload_confirm_receipt(self, order_id: str, photo_file_id: str) -> bool:
        """
        Upload admin confirmation receipt to backend.

        Args:
            order_id: Order ID
            photo_file_id: Telegram file ID of admin's receipt photo

        Returns:
            True if successful, False otherwise
        """
        try:
            import aiohttp
            from aiohttp import FormData

            # Download photo from Telegram
            file = await self.bot.get_file(photo_file_id)
            photo_bytes = await file.download_as_bytearray()

            # Prepare multipart form data
            data = FormData()
            data.add_field(
                "receipt",
                bytes(photo_bytes),
                filename=f"{order_id}_confirm.jpg",
                content_type="image/jpeg",
            )

            headers = {"X-Backend-Secret": self.backend_webhook_secret}

            # Upload to backend
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.backend_api_url}/api/orders/{order_id}/confirm-receipt",
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        logger.info(
                            f"✅ Confirmation receipt uploaded for order {order_id}"
                        )
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to upload confirmation receipt: {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Error uploading confirmation receipt: {e}", exc_info=True)
            return False

    async def _update_bank_balances(
        self,
        order_id: str,
        order_type: str,
        user_sent_amount: float,
        staff_sent_amount: float,
        thai_bank_id: Optional[int],
        myanmar_bank_id: Optional[int],
    ) -> bool:
        """
        Update bank balances after staff receipt verification.

        For BUY orders:
        - Increase Thai bank (user sent THB)
        - Decrease Myanmar bank (staff sent MMK)

        For SELL orders:
        - Increase Myanmar bank (user sent MMK)
        - Decrease Thai bank (staff sent THB)

        Args:
            order_id: Order ID
            order_type: "buy" or "sell"
            user_sent_amount: Amount user sent
            staff_sent_amount: Amount staff sent
            thai_bank_id: Thai bank account ID
            myanmar_bank_id: Myanmar bank account ID

        Returns:
            True if successful, False otherwise
        """
        try:
            import aiohttp

            if order_type == "buy":
                # Buy: user sent THB, staff sent MMK
                thai_change = user_sent_amount  # Increase (received from user)
                myanmar_change = -staff_sent_amount  # Decrease (sent to user)
            else:
                # Sell: user sent MMK, staff sent THB
                thai_change = -staff_sent_amount  # Decrease (sent to user)
                myanmar_change = user_sent_amount  # Increase (received from user)

            payload = {
                "order_id": order_id,
                "order_type": order_type,
                "thai_bank_id": thai_bank_id,
                "thai_amount_change": thai_change,
                "myanmar_bank_id": myanmar_bank_id,
                "myanmar_amount_change": myanmar_change,
            }

            logger.info(f"💰 Updating bank balances for {order_type.upper()} order:")
            logger.info(
                f"   User sent: {user_sent_amount:,.2f} {'THB' if order_type == 'buy' else 'MMK'}"
            )
            logger.info(
                f"   Staff sent: {staff_sent_amount:,.2f} {'MMK' if order_type == 'buy' else 'THB'}"
            )
            logger.info(f"   Thai bank change: {thai_change:+,.2f}")
            logger.info(f"   Myanmar bank change: {myanmar_change:+,.2f}")
            logger.info(f"   Thai bank ID: {thai_bank_id}")
            logger.info(f"   Myanmar bank ID: {myanmar_bank_id}")
            logger.info(f"   Payload: {payload}")
            logger.info(f"   API URL: {self.backend_api_url}/api/banks/update-balance")

            headers = {
                "X-Backend-Secret": self.backend_webhook_secret,
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.backend_api_url}/api/banks/update-balance",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status in [200, 201]:
                        response_data = await response.json()
                        logger.info(f"✅ Bank balances updated for order {order_id}")
                        logger.info(f"   Backend response: {response_data}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"❌ Failed to update bank balances: {response.status} - {error_text}",
                            extra={
                                "order_id": order_id,
                                "status_code": response.status,
                                "payload": payload,
                                "error": error_text
                            }
                        )
                        return False

        except Exception as e:
            logger.error(f"Error updating bank balances: {e}", exc_info=True)
            return False

    async def _update_order_status(self, order_id: str, status: str) -> bool:
        """
        Update order status in backend.

        Args:
            order_id: Order ID
            status: New status (e.g., "approved", "declined")

        Returns:
            True if successful, False otherwise
        """
        try:
            import aiohttp

            payload = {"status": status}
            
            headers = {
                "X-Backend-Secret": self.backend_webhook_secret,
                "Content-Type": "application/json",
            }

            logger.info(f"📝 Updating order {order_id} status to: {status}")

            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    f"{self.backend_api_url}/api/orders/{order_id}/status",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status in [200, 201]:
                        logger.info(f"✅ Order {order_id} status updated to {status}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Failed to update order status: {response.status} - {error_text}"
                        )
                        return False

        except Exception as e:
            logger.error(f"Error updating order status: {e}", exc_info=True)
            return False

    async def _process_staff_rejection(self, message: Message) -> None:
        """
        Process staff rejection: extract order ID, update status, notify user.

        Args:
            message: Staff's message with rejection text
        """
        try:
            # Extract order ID from original message
            order_id = self._extract_order_id_from_message(message.reply_to_message)
            if not order_id:
                await message.reply_text(
                    "❌ Could not find order ID in the original message.\n"
                    "Please ensure you're replying to an order notification."
                )
                return

            # Extract rejection reason (text after "Reject:")
            text = message.text.strip()
            if text.lower().startswith("reject:"):
                rejection_reason = text[7:].strip()  # Remove "Reject:" prefix
            else:
                rejection_reason = text[7:].strip()  # Remove "reject:" prefix

            if not rejection_reason:
                rejection_reason = "No reason provided"

            logger.info(
                f"Processing rejection for order {order_id}: {rejection_reason}"
            )

            # Fetch order details to get chat_id
            order_details = await self._fetch_order_details(order_id)
            if not order_details:
                await message.reply_text(
                    f"❌ Could not fetch order details for {order_id}.\n"
                    "Please update status manually."
                )
                return

            chat_id = order_details.get("telegram", {}).get("chat_id")
            order_type = order_details.get("order_type", "unknown")

            # Update order status to "rejected"
            status_updated = await self._update_order_status(order_id, "rejected")
            if not status_updated:
                await message.reply_text(
                    f"⚠️ Failed to update order status to rejected for {order_id}.\n"
                    "Please update manually."
                )
                return

            # Notify user
            if chat_id:
                try:
                    user_message = (
                        f"❌ Order Rejected\n\n"
                        f"Order ID: {order_id}\n"
                        f"Type: {order_type.upper()}\n\n"
                        f"Reason: {rejection_reason}\n\n"
                        f"Please contact support if you have any questions.\n"
                        f"Use /start to create a new order."
                    )
                    
                    await self.bot.send_message(
                        chat_id=int(chat_id),
                        text=user_message
                    )
                    
                    logger.info(
                        f"✅ User notified of rejection for order {order_id}"
                    )
                    
                    # Don't send success message in admin group to reduce noise
                    logger.info(f"✅ Order {order_id} rejected and user notified.")
                except Exception as notify_error:
                    logger.error(
                        f"❌ Failed to send rejection notification: {notify_error}",
                        exc_info=True,
                    )
                    await message.reply_text(
                        f"⚠️ Order rejected but failed to notify user.\n"
                        f"Please notify user manually."
                    )
            else:
                logger.warning(
                    f"⚠️ No chat_id found for order {order_id}, cannot notify user"
                )
                await message.reply_text(
                    f"✅ Order {order_id} rejected but no chat_id found.\n"
                    "Please notify user manually."
                )

        except Exception as e:
            logger.error(f"Error processing staff rejection: {e}", exc_info=True)
            await message.reply_text(
                f"❌ Error processing rejection: {str(e)}\n"
                f"Please update status manually."
            )

    async def _process_staff_complaint(self, message: Message) -> None:
        """
        Process staff complaint: extract order ID, update status, notify user.

        Args:
            message: Staff's message with complaint text
        """
        try:
            # Extract order ID from original message
            order_id = self._extract_order_id_from_message(message.reply_to_message)
            if not order_id:
                await message.reply_text(
                    "❌ Could not find order ID in the original message.\n"
                    "Please ensure you're replying to an order notification."
                )
                return

            # Extract complaint message (text after "Complain:")
            text = message.text.strip()
            if text.lower().startswith("complain:"):
                complaint_message = text[9:].strip()  # Remove "Complain:" prefix
            else:
                complaint_message = text[9:].strip()  # Remove "complain:" prefix

            if not complaint_message:
                complaint_message = "No message provided"

            logger.info(
                f"Processing complaint for order {order_id}: {complaint_message}"
            )

            # Fetch order details to get chat_id
            order_details = await self._fetch_order_details(order_id)
            if not order_details:
                await message.reply_text(
                    f"❌ Could not fetch order details for {order_id}.\n"
                    "Please update status manually."
                )
                return

            chat_id = order_details.get("telegram", {}).get("chat_id")
            order_type = order_details.get("order_type", "unknown")

            # Update order status to "complain"
            status_updated = await self._update_order_status(order_id, "complain")
            if not status_updated:
                await message.reply_text(
                    f"⚠️ Failed to update order status to complain for {order_id}.\n"
                    "Please update manually."
                )
                return

            # Notify user
            if chat_id:
                try:
                    user_message = (
                        f"⚠️ Order Issue\n\n"
                        f"Order ID: {order_id}\n"
                        f"Type: {order_type.upper()}\n\n"
                        f"Message from admin:\n{complaint_message}\n\n"
                        f"Please contact support for assistance.\n"
                        f"Use /start to create a new order."
                    )
                    
                    await self.bot.send_message(
                        chat_id=int(chat_id),
                        text=user_message
                    )
                    
                    logger.info(
                        f"✅ User notified of complaint for order {order_id}"
                    )
                    
                    # Don't send success message in admin group to reduce noise
                    logger.info(f"✅ Order {order_id} marked as complaint and user notified.")
                except Exception as notify_error:
                    logger.error(
                        f"❌ Failed to send complaint notification: {notify_error}",
                        exc_info=True,
                    )
                    await message.reply_text(
                        f"⚠️ Order marked as complaint but failed to notify user.\n"
                        f"Please notify user manually."
                    )
            else:
                logger.warning(
                    f"⚠️ No chat_id found for order {order_id}, cannot notify user"
                )
                await message.reply_text(
                    f"✅ Order {order_id} marked as complaint but no chat_id found.\n"
                    "Please notify user manually."
                )

        except Exception as e:
            logger.error(f"Error processing staff complaint: {e}", exc_info=True)
            await message.reply_text(
                f"❌ Error processing complaint: {str(e)}\n"
                f"Please update status manually."
            )

    def _extract_bank_display_name(self, text: str) -> Optional[str]:
        """
        Extract bank display name from admin's message.
        
        Admin should include bank name in their message, e.g.:
        - "SCB" 
        - "KBZ Special"
        - "Yoma"
        
        Args:
            text: Message text or caption
            
        Returns:
            Bank display name or None
        """
        if not text or not text.strip():
            return None
        
        # Common bank display names to look for
        # These should match the display_name field in your bank accounts
        bank_patterns = [
            "SCB", "Bangkok Bank", "Kasikorn", "Krungsri", "TMB",  # Thai banks
            "KBZ Special", "KBZ", "AYA Special", "AYA", "Yoma", "CB Special", "CB", "KBZpay",  # Myanmar banks
        ]
        
        text_upper = text.upper().strip()
        
        # Try exact match first
        for pattern in bank_patterns:
            if pattern.upper() == text_upper:
                logger.info(f"Found exact bank match: {pattern}")
                return pattern
        
        # Try partial match
        for pattern in bank_patterns:
            if pattern.upper() in text_upper:
                logger.info(f"Found partial bank match: {pattern}")
                return pattern
        
        # If no match, return the text as-is (admin might use custom name)
        logger.info(f"No standard bank match, using text as-is: {text.strip()}")
        return text.strip()
    
    async def _find_bank_id_by_display_name(
        self, display_name: str, order_type: str, currency: str
    ) -> Optional[int]:
        """
        Find bank ID by display name from settings service.
        
        Args:
            display_name: Bank display name (e.g., "SCB", "KBZ Special")
            order_type: "buy" or "sell" to determine which bank list to search
            currency: "THB" or "MMK" to determine which bank list to search
            
        Returns:
            Bank ID or None if not found
        """
        try:
            # Check if settings_service is available
            if not self.settings_service:
                logger.warning("Settings service not available, cannot find bank ID")
                return None
            
            # Determine which bank list to search
            if currency == "THB":
                banks = self.settings_service.thai_banks
            else:  # MMK
                banks = self.settings_service.myanmar_banks
            
            # Search for bank by display_name or bank_name
            display_name_upper = display_name.upper()
            
            for bank in banks:
                bank_display = bank.get("display_name", "").upper()
                bank_name = bank.get("bank_name", "").upper()
                
                # Try exact match first
                if bank_display == display_name_upper or bank_name == display_name_upper:
                    bank_id = bank.get("id")
                    logger.info(f"Found bank ID {bank_id} for '{display_name}' (exact match)")
                    return bank_id
            
            # Try partial match
            for bank in banks:
                bank_display = bank.get("display_name", "").upper()
                bank_name = bank.get("bank_name", "").upper()
                
                if display_name_upper in bank_display or display_name_upper in bank_name:
                    bank_id = bank.get("id")
                    logger.info(f"Found bank ID {bank_id} for '{display_name}' (partial match)")
                    return bank_id
            
            logger.warning(f"Could not find bank ID for display name: {display_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding bank ID by display name: {e}", exc_info=True)
            return None
    
    async def _request_display_name_confirmation(
        self,
        message: Message,
        order_id: str,
        order_type: str,
        provided_name: Optional[str],
        expected_currency: str,
        expected_bank_list: str
    ) -> None:
        """
        Request admin to confirm which bank display name to use.
        
        Args:
            message: Admin's message
            order_id: Order ID
            order_type: "buy" or "sell"
            provided_name: Display name provided by admin (if any)
            expected_currency: Expected currency (THB or MMK)
            expected_bank_list: Expected bank list name (Thai or Myanmar)
        """
        try:
            # Get available banks
            if expected_currency == "THB":
                banks = self.settings_service.thai_banks if self.settings_service else []
            else:
                banks = self.settings_service.myanmar_banks if self.settings_service else []
            
            # Build message
            if provided_name:
                error_msg = (
                    f"❌ Display Name Not Found\n\n"
                    f"Order: {order_id}\n"
                    f"You sent: '{provided_name}'\n\n"
                    f"This display name is not found in {expected_bank_list} banks.\n\n"
                )
            else:
                error_msg = (
                    f"❌ Display Name Required\n\n"
                    f"Order: {order_id}\n\n"
                    f"Please specify which {expected_bank_list} bank you used to send {expected_currency}.\n\n"
                )
            
            # Add available banks (show display_name, not bank_name)
            error_msg += f"Available {expected_bank_list} banks:\n"
            for bank in banks:
                # Prioritize display_name, only use bank_name if display_name is empty
                display_name = bank.get("display_name", "").strip()
                if not display_name:
                    display_name = bank.get("bank_name", "Unknown")
                error_msg += f"• {display_name}\n"
            
            error_msg += (
                f"\n📝 Please reply to this message with the correct display name.\n"
                f"Example: Reply with 'SCB' or 'KBZ Special'"
            )
            
            await message.reply_text(error_msg)
            
            logger.info(
                f"Requested display name confirmation for order {order_id}",
                extra={
                    "order_id": order_id,
                    "provided_name": provided_name,
                    "expected_currency": expected_currency
                }
            )
            
        except Exception as e:
            logger.error(f"Error requesting display name confirmation: {e}", exc_info=True)
            await message.reply_text(
                f"❌ Error: Could not process receipt.\n"
                f"Please include bank display name in your message and try again."
            )
