"""
Settings synchronization service for fetching and caching exchange rates and bank accounts.

Fetches settings from backend API and maintains cached values with periodic refresh.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from app.logging_config import get_logger
from app.services.backend_client import BackendClient


logger = get_logger(__name__)


class SettingsService:
    """
    Service for fetching and caching settings from backend.

    Maintains cached exchange rates, bank accounts, and system settings
    with periodic refresh mechanism.
    """

    def __init__(
        self, backend_client: BackendClient, refresh_interval_minutes: int = 10
    ):
        """
        Initialize the settings service.

        Args:
            backend_client: Backend API client instance
            refresh_interval_minutes: How often to refresh settings (default: 10 minutes)
        """
        self.backend_client = backend_client
        self.refresh_interval_minutes = refresh_interval_minutes

        # Cached settings with defaults
        self._buy_rate: float = 0.0035
        self._sell_rate: float = 0.0034
        self._maintenance_mode: bool = False
        self._auth_required: bool = False

        # Cached bank accounts (bank_name -> (bank_name, account_number, account_name, qr_image, id, on))
        self._myanmar_banks: Dict[
            str, Tuple[str, str, str, Optional[str], Optional[int], bool]
        ] = {}
        self._thai_banks: Dict[
            str, Tuple[str, str, str, Optional[str], Optional[int], bool]
        ] = {}

        # Last update timestamps
        self._last_settings_update: Optional[datetime] = None
        self._last_banks_update: Optional[datetime] = None

        # Background task handle
        self._refresh_task: Optional[asyncio.Task] = None
        self._running: bool = False

        logger.info(
            f"SettingsService initialized with refresh interval: {refresh_interval_minutes} minutes"
        )

    async def fetch_settings(self) -> bool:
        """
        Fetch exchange rates and system settings from backend.

        Returns:
            True if successful, False otherwise
        """
        try:
            data = await self.backend_client.fetch_settings()

            if data:
                self._buy_rate = data.get("buy", self._buy_rate)
                self._sell_rate = data.get("sell", self._sell_rate)
                self._maintenance_mode = data.get("maintenance_mode", False)
                self._auth_required = data.get("auth_feature", False)
                self._last_settings_update = datetime.now()

                logger.info(
                    "Settings updated successfully",
                    extra={
                        "buy_rate": self._buy_rate,
                        "sell_rate": self._sell_rate,
                        "maintenance_mode": self._maintenance_mode,
                        "auth_required": self._auth_required,
                    },
                )
                return True
            else:
                logger.warning("Failed to fetch settings from backend")
                return False

        except Exception as e:
            logger.error(f"Error fetching settings: {e}", exc_info=True)
            return False

    async def fetch_bank_accounts(self, bank_type: str) -> bool:
        """
        Fetch bank accounts from backend.

        Args:
            bank_type: "myanmar" or "thai"

        Returns:
            True if successful, False otherwise
        """
        try:
            data = await self.backend_client.fetch_bank_accounts(bank_type)

            if data:
                # Store complete bank data including id and on fields
                # Convert list of dicts to dict with bank_name as key for backward compatibility
                banks = {
                    item["bank_name"]: (
                        item["bank_name"],
                        item["account_number"],
                        item["account_name"],
                        item.get("qr_image"),
                        item.get("id"),  # Add id
                        True,  # on is always True since backend filters by on=True
                    )
                    for item in data
                }

                if bank_type == "myanmar":
                    self._myanmar_banks = banks
                    logger.info(f"Updated {len(banks)} Myanmar bank accounts")
                elif bank_type == "thai":
                    self._thai_banks = banks
                    logger.info(f"Updated {len(banks)} Thai bank accounts")

                self._last_banks_update = datetime.now()
                return True
            else:
                logger.warning(f"Failed to fetch {bank_type} bank accounts")
                return False

        except Exception as e:
            logger.error(
                f"Error fetching {bank_type} bank accounts: {e}", exc_info=True
            )
            return False

    async def fetch_all_bank_accounts(self) -> bool:
        """
        Fetch both Myanmar and Thai bank accounts.

        Returns:
            True if both successful, False otherwise
        """
        myanmar_success = await self.fetch_bank_accounts("myanmar")
        thai_success = await self.fetch_bank_accounts("thai")

        return myanmar_success and thai_success

    async def refresh_all(self) -> bool:
        """
        Refresh all settings and bank accounts.

        Returns:
            True if all successful, False otherwise
        """
        logger.debug("Refreshing all settings and bank accounts")

        settings_success = await self.fetch_settings()
        banks_success = await self.fetch_all_bank_accounts()

        if settings_success and banks_success:
            logger.info("All settings and bank accounts refreshed successfully")
            return True
        else:
            logger.warning("Some settings or bank accounts failed to refresh")
            return False

    async def _periodic_refresh_task(self):
        """Background task for periodic settings refresh."""
        logger.info("Starting periodic settings refresh task")

        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval_minutes * 60)

                if self._running:
                    logger.debug("Running periodic settings refresh")
                    await self.refresh_all()

            except asyncio.CancelledError:
                logger.info("Periodic refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic refresh task: {e}", exc_info=True)
                # Continue running despite errors

    def start_periodic_refresh(self):
        """Start the periodic refresh background task."""
        if self._refresh_task is None or self._refresh_task.done():
            self._running = True
            self._refresh_task = asyncio.create_task(self._periodic_refresh_task())
            logger.info("Periodic refresh task started")
        else:
            logger.warning("Periodic refresh task already running")

    def stop_periodic_refresh(self):
        """Stop the periodic refresh background task."""
        if self._refresh_task and not self._refresh_task.done():
            self._running = False
            self._refresh_task.cancel()
            logger.info("Periodic refresh task stopped")

    # Property accessors for cached values

    @property
    def buy_rate(self) -> float:
        """Get cached buy rate (THB to MMK)."""
        return self._buy_rate

    @property
    def sell_rate(self) -> float:
        """Get cached sell rate (MMK to THB)."""
        return self._sell_rate

    @property
    def maintenance_mode(self) -> bool:
        """Check if system is in maintenance mode."""
        return self._maintenance_mode

    @property
    def auth_required(self) -> bool:
        """Check if authentication is required."""
        return self._auth_required

    @property
    def myanmar_banks(self) -> List[Dict[str, Any]]:
        """Get Myanmar banks as list of dictionaries."""
        return self.get_myanmar_bank_list()

    @property
    def thai_banks(self) -> List[Dict[str, Any]]:
        """Get Thai banks as list of dictionaries."""
        return self.get_thai_bank_list()

    def get_myanmar_banks(
        self,
    ) -> Dict[str, Tuple[str, str, str, Optional[str], Optional[int], bool]]:
        """
        Get cached Myanmar bank accounts.

        Returns:
            Dict mapping bank_name to (bank_name, account_number, account_name, qr_image, id, on)
        """
        return self._myanmar_banks.copy()

    def get_thai_banks(
        self,
    ) -> Dict[str, Tuple[str, str, str, Optional[str], Optional[int], bool]]:
        """
        Get cached Thai bank accounts.

        Returns:
            Dict mapping bank_name to (bank_name, account_number, account_name, qr_image, id, on)
        """
        return self._thai_banks.copy()

    def get_myanmar_bank_list(self) -> List[Dict[str, Any]]:
        """
        Get Myanmar banks as list of dictionaries.

        Returns:
            List of bank dictionaries with bank_name, account_number, account_name, qr_image, id, on
        """
        return [
            {
                "bank_name": bank_name,
                "account_number": account_number,
                "account_name": account_name,
                "qr_image": qr_image,
                "id": bank_id,
                "on": on,
            }
            for bank_name, (
                account_number,
                account_name,
                qr_image,
                bank_id,
                on,
            ) in self._myanmar_banks.items()
        ]

    def get_thai_bank_list(self) -> List[Dict[str, Any]]:
        """
        Get Thai banks as list of dictionaries.

        Returns:
            List of bank dictionaries with bank_name, account_number, account_name, qr_image, id, on
        """
        return [
            {
                "bank_name": bank_name,
                "account_number": account_number,
                "account_name": account_name,
                "qr_image": qr_image,
                "id": bank_id,
                "on": on,
            }
            for bank_name, (
                account_number,
                account_name,
                qr_image,
                bank_id,
                on,
            ) in self._thai_banks.items()
        ]

    def get_bank_by_name(
        self, bank_name: str, bank_type: str = "myanmar"
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific bank account by name.

        Args:
            bank_name: Name of the bank
            bank_type: "myanmar" or "thai"

        Returns:
            Bank dictionary or None if not found
        """
        banks = self._myanmar_banks if bank_type == "myanmar" else self._thai_banks

        if bank_name in banks:
            account_number, account_name, qr_image, bank_id, on = banks[bank_name]
            return {
                "bank_name": bank_name,
                "account_number": account_number,
                "account_name": account_name,
                "qr_image": qr_image,
                "id": bank_id,
                "on": on,
            }

        return None

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of settings service.

        Returns:
            Dictionary with status information
        """
        return {
            "buy_rate": self._buy_rate,
            "sell_rate": self._sell_rate,
            "maintenance_mode": self._maintenance_mode,
            "auth_required": self._auth_required,
            "myanmar_banks_count": len(self._myanmar_banks),
            "thai_banks_count": len(self._thai_banks),
            "last_settings_update": (
                self._last_settings_update.isoformat()
                if self._last_settings_update
                else None
            ),
            "last_banks_update": (
                self._last_banks_update.isoformat() if self._last_banks_update else None
            ),
            "refresh_task_running": self._running,
        }
