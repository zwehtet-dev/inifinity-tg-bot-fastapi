"""
Order completion service for handling order status updates and bank balance management.
"""

import logging
from typing import Optional, Dict, Any, List
import httpx

from app.models.order import OrderData
from app.models.receipt import BankAccount

logger = logging.getLogger(__name__)


class OrderCompletionError(Exception):
    """Base exception for order completion errors."""

    pass


class OrderCompletionService:
    """
    Service for completing orders and updating bank balances.
    Handles communication with backend API for order status updates and balance management.
    """

    def __init__(self, backend_api_url: str, backend_secret: str):
        """
        Initialize order completion service.

        Args:
            backend_api_url: Base URL for backend API
            backend_secret: Shared secret for backend authentication
        """
        self.backend_api_url = backend_api_url.rstrip("/")
        self.backend_secret = backend_secret
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("OrderCompletionService initialized")

    async def complete_order(
        self,
        order_id: str,
        admin_receipt_file_id: Optional[str] = None,
        status: str = "completed",
    ) -> bool:
        """
        Complete an order by updating its status in the backend.

        Args:
            order_id: Unique order identifier
            admin_receipt_file_id: Optional Telegram file ID of admin confirmation receipt
            status: Order status to set (default: "completed")

        Returns:
            True if order was successfully completed, False otherwise

        Raises:
            OrderCompletionError: If order completion fails
        """
        try:
            url = f"{self.backend_api_url}/api/orders/{order_id}/status"

            headers = {
                "X-Backend-Secret": self.backend_secret,
                "Content-Type": "application/json",
            }

            payload = {"status": status, "admin_receipt_file_id": admin_receipt_file_id}

            logger.info(
                f"Updating order status to {status}", extra={"order_id": order_id}
            )

            response = await self.client.patch(url, json=payload, headers=headers)

            if response.status_code == 200:
                logger.info(
                    f"Order {order_id} successfully updated to {status}",
                    extra={"order_id": order_id, "status": status},
                )
                return True
            else:
                logger.error(
                    f"Failed to update order status: {response.status_code} - {response.text}",
                    extra={"order_id": order_id, "status_code": response.status_code},
                )
                return False

        except httpx.TimeoutException as e:
            logger.error(f"Timeout updating order {order_id}: {e}")
            raise OrderCompletionError(f"Timeout updating order: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error updating order {order_id}: {e}")
            raise OrderCompletionError(f"Request error: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error updating order {order_id}: {e}", exc_info=True
            )
            raise OrderCompletionError(f"Unexpected error: {e}")

    async def update_bank_balances(
        self,
        order: OrderData,
        increase_thai: bool = True,
        decrease_myanmar: bool = True,
    ) -> bool:
        """
        Update bank balances after order completion.

        For buy orders: Increase Thai bank balance (user sent THB), decrease Myanmar bank balance (admin sent MMK)
        For sell orders: Increase Myanmar bank balance (user sent MMK), decrease Thai bank balance (admin sent THB)

        Args:
            order: OrderData containing order details
            increase_thai: Whether to increase Thai bank balance (default: True)
            decrease_myanmar: Whether to decrease Myanmar bank balance (default: True)

        Returns:
            True if balances were successfully updated, False otherwise

        Raises:
            OrderCompletionError: If balance update fails
        """
        try:
            url = f"{self.backend_api_url}/api/banks/update-balances"

            headers = {
                "X-Backend-Secret": self.backend_secret,
                "Content-Type": "application/json",
            }

            # Determine which balances to update based on order type
            if order.order_type == "buy":
                # Buy order: user sends THB, receives MMK
                # Increase Thai bank (received from user)
                # Decrease Myanmar bank (sent to user)
                thai_change = order.thb_amount if increase_thai else 0
                myanmar_change = -order.mmk_amount if decrease_myanmar else 0
            else:
                # Sell order: user sends MMK, receives THB
                # Increase Myanmar bank (received from user)
                # Decrease Thai bank (sent to user)
                thai_change = -order.thb_amount if decrease_myanmar else 0
                myanmar_change = order.mmk_amount if increase_thai else 0

            payload = {
                "order_id": order.order_id,
                "order_type": order.order_type,
                "thai_bank_change": thai_change,
                "myanmar_bank_change": myanmar_change,
                "myanmar_bank_account": order.myanmar_bank_account,
            }

            logger.info(
                f"Updating bank balances for order {order.order_id}",
                extra={
                    "order_id": order.order_id,
                    "order_type": order.order_type,
                    "thai_change": thai_change,
                    "myanmar_change": myanmar_change,
                },
            )

            response = await self.client.post(url, json=payload, headers=headers)

            if response.status_code in [200, 201]:
                logger.info(
                    f"Bank balances updated successfully for order {order.order_id}",
                    extra={"order_id": order.order_id},
                )
                return True
            else:
                logger.error(
                    f"Failed to update bank balances: {response.status_code} - {response.text}",
                    extra={
                        "order_id": order.order_id,
                        "status_code": response.status_code,
                    },
                )
                return False

        except httpx.TimeoutException as e:
            logger.error(
                f"Timeout updating bank balances for order {order.order_id}: {e}"
            )
            raise OrderCompletionError(f"Timeout updating balances: {e}")
        except httpx.RequestError as e:
            logger.error(
                f"Request error updating bank balances for order {order.order_id}: {e}"
            )
            raise OrderCompletionError(f"Request error: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error updating bank balances for order {order.order_id}: {e}",
                exc_info=True,
            )
            raise OrderCompletionError(f"Unexpected error: {e}")

    async def get_bank_balances(self) -> Optional[Dict[str, float]]:
        """
        Fetch current bank balances from backend.

        Returns:
            Dictionary mapping bank names to current balances, or None if fetch fails

        Raises:
            OrderCompletionError: If balance fetch fails
        """
        try:
            url = f"{self.backend_api_url}/api/banks/balances"

            headers = {"X-Backend-Secret": self.backend_secret}

            logger.debug("Fetching bank balances from backend")

            response = await self.client.get(url, headers=headers)

            if response.status_code == 200:
                balances = response.json()
                logger.info(
                    "Successfully fetched bank balances",
                    extra={"balance_count": len(balances)},
                )
                return balances
            else:
                logger.error(
                    f"Failed to fetch bank balances: {response.status_code} - {response.text}",
                    extra={"status_code": response.status_code},
                )
                return None

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching bank balances: {e}")
            raise OrderCompletionError(f"Timeout fetching balances: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching bank balances: {e}")
            raise OrderCompletionError(f"Request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching bank balances: {e}", exc_info=True)
            raise OrderCompletionError(f"Unexpected error: {e}")

    async def get_bank_accounts(self, bank_type: str) -> List[BankAccount]:
        """
        Fetch bank accounts from backend.

        Args:
            bank_type: Type of bank accounts to fetch ("myanmar" or "thai")

        Returns:
            List of BankAccount objects

        Raises:
            OrderCompletionError: If fetch fails
        """
        try:
            url = f"{self.backend_api_url}/api/banks/{bank_type}"

            headers = {"X-Backend-Secret": self.backend_secret}

            logger.debug(f"Fetching {bank_type} bank accounts from backend")

            response = await self.client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                bank_accounts = [BankAccount(**item) for item in data]
                logger.info(
                    f"Successfully fetched {len(bank_accounts)} {bank_type} bank accounts",
                    extra={"bank_type": bank_type, "count": len(bank_accounts)},
                )
                return bank_accounts
            else:
                logger.error(
                    f"Failed to fetch {bank_type} bank accounts: {response.status_code} - {response.text}",
                    extra={"bank_type": bank_type, "status_code": response.status_code},
                )
                return []

        except httpx.TimeoutException as e:
            logger.error(f"Timeout fetching {bank_type} bank accounts: {e}")
            raise OrderCompletionError(f"Timeout fetching bank accounts: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching {bank_type} bank accounts: {e}")
            raise OrderCompletionError(f"Request error: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error fetching {bank_type} bank accounts: {e}",
                exc_info=True,
            )
            raise OrderCompletionError(f"Unexpected error: {e}")

    async def fetch_all_banks_with_balances(
        self,
    ) -> tuple[List[BankAccount], List[BankAccount], Dict[str, float]]:
        """
        Fetch all bank accounts (Myanmar and Thai) with current balances.

        Returns:
            Tuple of (myanmar_banks, thai_banks, balances_dict)

        Raises:
            OrderCompletionError: If fetch fails
        """
        try:
            # Fetch Myanmar banks
            myanmar_banks = await self.get_bank_accounts("myanmar")

            # Fetch Thai banks
            thai_banks = await self.get_bank_accounts("thai")

            # Fetch current balances
            balances = await self.get_bank_balances()
            if balances is None:
                balances = {}

            logger.info(
                "Successfully fetched all banks with balances",
                extra={
                    "myanmar_count": len(myanmar_banks),
                    "thai_count": len(thai_banks),
                    "balance_count": len(balances),
                },
            )

            return myanmar_banks, thai_banks, balances

        except Exception as e:
            logger.error(f"Error fetching banks with balances: {e}", exc_info=True)
            raise OrderCompletionError(f"Failed to fetch banks with balances: {e}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("OrderCompletionService client closed")
