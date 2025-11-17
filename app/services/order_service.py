"""
Order submission service for handling order data persistence.

This service wraps the BackendClient order methods and provides
a clean interface for submitting orders and checking pending orders.
"""

from typing import Optional, List

from app.services.backend_client import BackendClient
from app.logging_config import get_logger


logger = get_logger(__name__)


class OrderService:
    """
    Service for managing order submissions and queries.

    This service provides methods for:
    - Submitting completed orders to the backend
    - Checking for pending orders
    - Handling order-related errors
    """

    def __init__(self, backend_client: BackendClient):
        """
        Initialize the order service.

        Args:
            backend_client: BackendClient instance for API communication
        """
        self.backend_client = backend_client
        logger.info("OrderService initialized")

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

        This method handles:
        - Multiple receipt images
        - QR code image upload
        - Error handling and logging

        Args:
            order_type: "buy" or "sell"
            amount: Order amount in the source currency
            price: Exchange rate
            receipt_file_ids: List of Telegram file IDs for receipt images
            user_bank: User's bank account information
            chat_id: Telegram chat ID
            qr_file_id: Optional Telegram file ID for QR code image
            myanmar_bank: Optional Myanmar bank account name

        Returns:
            Order ID if successful, None otherwise

        Requirements:
            - 13.1: Submit order data to backend
            - 13.2: Handle multiple receipt images
            - 13.3: Handle QR code upload
            - 13.5: Return order_id from backend
        """
        logger.info(
            f"Submitting order: type={order_type}, amount={amount}, price={price}, chat_id={chat_id}",
            extra={
                "order_type": order_type,
                "amount": amount,
                "price": price,
                "chat_id": chat_id,
                "receipt_count": len(receipt_file_ids),
                "has_qr": qr_file_id is not None,
            },
        )

        # Validate amount before submission
        if amount == 0.0 or amount is None:
            logger.error(
                f"⚠️ CRITICAL: Amount is {amount}! This should not be 0.0 or None",
                extra={"order_type": order_type, "chat_id": chat_id},
            )

        try:
            # Call backend client to submit order
            order_id = await self.backend_client.submit_order(
                order_type=order_type,
                amount=amount,
                price=price,
                receipt_file_ids=receipt_file_ids,
                user_bank=user_bank,
                chat_id=chat_id,
                qr_file_id=qr_file_id,
                myanmar_bank=myanmar_bank,
                thai_bank_id=thai_bank_id,
                myanmar_bank_id=myanmar_bank_id,
            )

            if order_id:
                logger.info(
                    "Order submitted successfully",
                    extra={
                        "order_id": order_id,
                        "order_type": order_type,
                        "chat_id": chat_id,
                    },
                )
                return order_id
            else:
                logger.error(
                    "Failed to submit order - no order_id returned",
                    extra={"chat_id": chat_id},
                )
                return None

        except Exception as e:
            logger.error(
                "Error submitting order",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            return None

    async def check_pending_order(self, chat_id: int) -> bool:
        """
        Check if user has a pending order.

        This method queries the backend to determine if the user
        has an existing pending order that must be completed before
        starting a new transaction.

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if user has a pending order, False otherwise

        Requirements:
            - 13.4: Check for pending orders before allowing new orders
        """
        logger.debug("Checking for pending order", extra={"chat_id": chat_id})

        try:
            has_pending = await self.backend_client.check_pending_order(chat_id)

            logger.debug(
                "Pending order check complete",
                extra={"chat_id": chat_id, "has_pending": has_pending},
            )

            return has_pending

        except Exception as e:
            logger.error(
                "Error checking pending order",
                extra={"chat_id": chat_id, "error": str(e)},
                exc_info=True,
            )
            # Return False to allow user to proceed in case of error
            # This prevents blocking users due to backend issues
            return False
