"""Services module for bot engine."""

from app.services.state_manager import StateManager, get_state_manager
from app.services.ocr_service import (
    OCRService,
    OCRError,
    InvalidImageError,
    RateLimitError,
    OCRTimeoutError,
)
from app.services.receipt_validator import ReceiptValidator
from app.services.admin_notifier import AdminNotifier, AdminNotificationError
from app.services.admin_receipt_validator import (
    AdminReceiptValidator,
    AdminReceiptValidationError,
)
from app.services.order_completion import OrderCompletionService, OrderCompletionError
from app.services.user_notifier import UserNotifier, UserNotificationError
from app.services.backend_client import BackendClient
from app.services.message_service import MessageService
from app.services.message_poller import MessagePoller
from app.services.order_service import OrderService


__all__ = [
    "StateManager",
    "get_state_manager",
    "OCRService",
    "OCRError",
    "InvalidImageError",
    "RateLimitError",
    "OCRTimeoutError",
    "ReceiptValidator",
    "AdminNotifier",
    "AdminNotificationError",
    "AdminReceiptValidator",
    "AdminReceiptValidationError",
    "OrderCompletionService",
    "OrderCompletionError",
    "UserNotifier",
    "UserNotificationError",
    "BackendClient",
    "MessageService",
    "MessagePoller",
    "OrderService",
]
