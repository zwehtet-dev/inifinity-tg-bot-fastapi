"""
Backend API client for communicating with the Flask backend system.

Provides methods for all backend endpoints with error handling and retry logic.
"""

import asyncio
import json
from typing import Optional, List, Dict, Any
import httpx
from io import BytesIO

from app.logging_config import get_logger


logger = get_logger(__name__)


class BackendClient:
    """
    HTTP client for communicating with the Flask backend API.

    Handles authentication, error handling, and retry logic with exponential backoff.
    """

    def __init__(self, backend_url: str, backend_secret: str, bot_token: str = None):
        """
        Initialize the backend client.

        Args:
            backend_url: Base URL of the backend API
            backend_secret: Shared secret for authentication
            bot_token: Telegram bot token for downloading files
        """
        self.backend_url = backend_url.rstrip("/")
        self.backend_secret = backend_secret
        self.bot_token = bot_token
        self.client = httpx.AsyncClient(timeout=30.0)
        self._telegram_client = None

        logger.info(f"BackendClient initialized with URL: {self.backend_url}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        if self._telegram_client:
            await self._telegram_client.aclose()

    async def _get_telegram_client(self) -> httpx.AsyncClient:
        """Get or create Telegram API client."""
        if self._telegram_client is None:
            self._telegram_client = httpx.AsyncClient(timeout=30.0)
        return self._telegram_client

    async def _retry_with_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
    ):
        """
        Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            backoff_factor: Multiplier for delay on each retry

        Returns:
            Result of the function call

        Raises:
            Last exception if all retries fail
        """
        delay = initial_delay
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func()
            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.ConnectError,
            ) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s",
                        extra={"error": str(e)},
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(
                        f"Request failed after {max_retries} attempts",
                        extra={"error": str(e)},
                    )
            except Exception as e:
                # Don't retry on non-transient errors
                logger.error(f"Non-retryable error: {e}", exc_info=True)
                raise

        raise last_exception

    # Message endpoints

    async def submit_message(
        self,
        telegram_id: str,
        chat_id: int,
        content: str = "",
        chosen_option: str = "",
        image_file_ids: Optional[List[str]] = None,
        from_bot: bool = False,
        from_backend: bool = False,
        buttons: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Submit a message to backend /api/message/submit endpoint.

        Args:
            telegram_id: User's Telegram ID
            chat_id: Chat ID
            content: Message content
            chosen_option: Selected option from buttons
            image_file_ids: List of Telegram file IDs for images
            from_bot: Whether message is from bot
            from_backend: Whether message is from backend
            buttons: Button data as dict

        Returns:
            Response data if successful, None otherwise
        """
        url = f"{self.backend_url}/api/message/submit"

        data = {
            "telegram_id": telegram_id,
            "chat_id": str(chat_id),
            "content": content,
            "chosen_option": chosen_option,
            "from_bot": str(from_bot).lower(),
            "from_backend": str(from_backend).lower(),
        }

        if buttons:
            data["buttons"] = json.dumps(buttons)

        files = []

        # Download and prepare image files if provided
        if image_file_ids and self.bot_token:
            telegram_client = await self._get_telegram_client()
            for idx, file_id in enumerate(image_file_ids):
                try:
                    # Get file info from Telegram
                    file_info_url = (
                        f"https://api.telegram.org/bot{self.bot_token}/getFile"
                    )
                    file_info_response = await telegram_client.post(
                        file_info_url, json={"file_id": file_id}
                    )

                    if file_info_response.status_code == 200:
                        file_data = file_info_response.json()
                        if file_data.get("ok"):
                            file_path = file_data["result"]["file_path"]

                            # Download file
                            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                            download_response = await telegram_client.get(download_url)

                            if download_response.status_code == 200:
                                file_bytes = download_response.content
                                files.append(
                                    (
                                        "image",
                                        (
                                            f"image{idx}.jpg",
                                            BytesIO(file_bytes),
                                            "image/jpeg",
                                        ),
                                    )
                                )
                            else:
                                logger.error(
                                    f"Failed to download file: {download_response.status_code}"
                                )
                    else:
                        logger.error(
                            f"Failed to get file info: {file_info_response.status_code}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error downloading image {file_id}: {e}", exc_info=True
                    )

        async def _submit():
            if files:
                response = await self.client.post(url, data=data, files=files)
            else:
                response = await self.client.post(url, data=data)

            if response.status_code == 201:
                logger.debug(f"Message submitted successfully for chat_id={chat_id}")
                return response.json()
            else:
                logger.error(
                    f"Failed to submit message: {response.status_code}",
                    extra={"response": response.text},
                )
                return None

        try:
            return await self._retry_with_backoff(_submit)
        except Exception as e:
            logger.error(f"Error submitting message: {e}", exc_info=True)
            return None

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
        url = f"{self.backend_url}/api/message/poll"
        params = {"telegram_id": telegram_id, "chat_id": str(chat_id)}

        async def _poll():
            response = await self.client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                logger.debug(f"Polled {len(messages)} messages for chat_id={chat_id}")
                return messages
            else:
                logger.error(
                    f"Failed to poll messages: {response.status_code}",
                    extra={"response": response.text},
                )
                return []

        try:
            return await self._retry_with_backoff(_poll)
        except Exception as e:
            logger.error(f"Error polling messages: {e}", exc_info=True)
            return []

    # Order endpoints

    async def submit_order(
        self,
        order_type: str,
        amount: float,
        price: float,
        receipt_file_ids: List[str],
        user_bank: str,
        chat_id: int,
        qr_file_id: Optional[str] = None,
        myanmar_bank: Optional[str] = None,
        thai_bank_id: Optional[int] = None,
        myanmar_bank_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Submit order to backend /api/orders/submit endpoint.

        Args:
            order_type: "buy" or "sell"
            amount: Order amount
            price: Exchange rate
            receipt_file_ids: List of receipt file IDs
            user_bank: User's bank information
            chat_id: Chat ID
            qr_file_id: Optional QR code file ID
            myanmar_bank: Optional Myanmar bank account

        Returns:
            Order ID if successful, None otherwise
        """
        url = f"{self.backend_url}/api/orders/submit"

        # Log the order details before submission
        logger.info(
            f"Preparing order submission: type={order_type}, amount={amount}, "
            f"price={price}, chat_id={chat_id}"
        )

        data = {
            "order_type": order_type,
            "amount": str(amount),
            "price": str(price),
            "myanmar_bank_account": myanmar_bank or "",
            "user_bank": user_bank,
            "chat_id": str(chat_id),
        }

        # Add bank IDs if provided
        if thai_bank_id is not None:
            data["thai_bank_account_id"] = str(thai_bank_id)
        if myanmar_bank_id is not None:
            data["myanmar_bank_account_id"] = str(myanmar_bank_id)

        logger.debug(f"Order data being sent: {data}")

        files = []

        # Download and prepare receipt files
        if receipt_file_ids and self.bot_token:
            telegram_client = await self._get_telegram_client()
            for idx, file_id in enumerate(receipt_file_ids):
                try:
                    # Get file info from Telegram
                    file_info_url = (
                        f"https://api.telegram.org/bot{self.bot_token}/getFile"
                    )
                    file_info_response = await telegram_client.post(
                        file_info_url, json={"file_id": file_id}
                    )

                    if file_info_response.status_code == 200:
                        file_data = file_info_response.json()
                        if file_data.get("ok"):
                            file_path = file_data["result"]["file_path"]

                            # Download file
                            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                            download_response = await telegram_client.get(download_url)

                            if download_response.status_code == 200:
                                file_bytes = download_response.content
                                field_name = (
                                    "receipt"
                                    if len(receipt_file_ids) == 1
                                    else f"receipt{idx+1}"
                                )
                                files.append(
                                    (
                                        field_name,
                                        (
                                            f"receipt{idx}.jpg",
                                            BytesIO(file_bytes),
                                            "image/jpeg",
                                        ),
                                    )
                                )
                except Exception as e:
                    logger.error(
                        f"Error downloading receipt {file_id}: {e}", exc_info=True
                    )

        # Download QR if provided
        if qr_file_id and self.bot_token:
            telegram_client = await self._get_telegram_client()
            try:
                # Get file info from Telegram
                file_info_url = f"https://api.telegram.org/bot{self.bot_token}/getFile"
                file_info_response = await telegram_client.post(
                    file_info_url, json={"file_id": qr_file_id}
                )

                if file_info_response.status_code == 200:
                    file_data = file_info_response.json()
                    if file_data.get("ok"):
                        file_path = file_data["result"]["file_path"]

                        # Download file
                        download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                        download_response = await telegram_client.get(download_url)

                        if download_response.status_code == 200:
                            file_bytes = download_response.content
                            files.append(
                                ("qr", ("qr.jpg", BytesIO(file_bytes), "image/jpeg"))
                            )
            except Exception as e:
                logger.error(f"Error downloading QR {qr_file_id}: {e}", exc_info=True)

        async def _submit():
            # Log the exact request details for debugging
            logger.info(f"📤 Sending POST to {url}")
            logger.info(f"📋 Form data: {data}")
            logger.info(
                f"💰 Amount in data: '{data.get('amount')}' (type: {type(data.get('amount')).__name__})"
            )
            logger.info(f"📁 Files count: {len(files)}")

            if files:
                response = await self.client.post(url, data=data, files=files)
            else:
                response = await self.client.post(url, data=data)

            logger.info(f"📥 Response status: {response.status_code}")

            if response.status_code == 201:
                order_data = response.json()
                order_id = order_data.get("order_id")

                # Check if amount in response is 0.0
                response_amount = order_data.get("order", {}).get("amount", "N/A")
                if response_amount == 0.0:
                    logger.error(
                        f"⚠️ CRITICAL: Backend saved amount as 0.0! "
                        f"Sent: {data.get('amount')}, Received back: {response_amount}"
                    )

                logger.info(
                    f"Order submitted successfully: order_id={order_id}, "
                    f"response_data={order_data}"
                )
                return order_id
            else:
                logger.error(
                    f"Failed to submit order: {response.status_code}",
                    extra={"response": response.text, "sent_data": data},
                )
                return None

        try:
            return await self._retry_with_backoff(_submit)
        except Exception as e:
            logger.error(f"Error submitting order: {e}", exc_info=True)
            return None

    async def check_pending_order(self, chat_id: int) -> bool:
        """
        Check if user has a pending order.

        Args:
            chat_id: Chat ID

        Returns:
            True if user has pending order, False otherwise
        """
        url = f"{self.backend_url}/api/orders/latest-pending"
        params = {"chat_id": str(chat_id)}

        async def _check():
            response = await self.client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                has_pending = data.get("has_pending", False)
                logger.debug(
                    f"Pending order check for chat_id={chat_id}: {has_pending}"
                )
                return has_pending
            else:
                logger.error(
                    f"Failed to check pending order: {response.status_code}",
                    extra={"response": response.text},
                )
                return False

        try:
            return await self._retry_with_backoff(_check)
        except Exception as e:
            logger.error(f"Error checking pending order: {e}", exc_info=True)
            return False

    # Settings endpoints

    async def fetch_settings(self) -> Optional[Dict[str, Any]]:
        """
        Fetch exchange rates and system settings.

        Returns:
            Settings dictionary with buy, sell, maintenance_mode, auth_feature
        """
        url = f"{self.backend_url}/api/settings/"

        async def _fetch():
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                logger.debug("Settings fetched successfully")
                return data
            else:
                logger.error(
                    f"Failed to fetch settings: {response.status_code}",
                    extra={"response": response.text},
                )
                return None

        try:
            return await self._retry_with_backoff(_fetch)
        except Exception as e:
            logger.error(f"Error fetching settings: {e}", exc_info=True)
            return None

    # Bank endpoints

    async def fetch_bank_accounts(self, bank_type: str) -> List[Dict[str, Any]]:
        """
        Fetch bank accounts from backend.

        Args:
            bank_type: "myanmar" or "thai"

        Returns:
            List of bank account dictionaries
        """
        url = f"{self.backend_url}/api/banks/{bank_type}"

        async def _fetch():
            response = await self.client.get(url)

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Fetched {len(data)} {bank_type} bank accounts")
                return data
            else:
                logger.error(
                    f"Failed to fetch {bank_type} banks: {response.status_code}",
                    extra={"response": response.text},
                )
                return []

        try:
            return await self._retry_with_backoff(_fetch)
        except Exception as e:
            logger.error(f"Error fetching {bank_type} banks: {e}", exc_info=True)
            return []
