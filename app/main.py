"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
from telegram import Bot
from telegram.request import HTTPXRequest

from app.config import get_settings
from app.logging_config import setup_logging, get_logger
from app.routes.webhooks import router as webhook_router
from app.handlers.backend_webhook import BackendWebhookHandler
from app.handlers.telegram_handler import TelegramHandler
from app.utils.webhook_manager import WebhookManager
from app.services.state_manager import StateManager
from app.services.backend_client import BackendClient
from app.services.message_service import MessageService
from app.services.message_poller import MessagePoller
from app.services.order_service import OrderService
from app.services.settings_service import SettingsService
from app.middleware.error_middleware import (
    ErrorHandlingMiddleware,
    RequestLoggingMiddleware,
)
from app.middleware.exception_handlers import register_exception_handlers


# Initialize logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    settings = get_settings()
    logger.info(
        "Starting FastAPI bot engine",
        extra={
            "environment": settings.environment,
            "log_level": settings.log_level,
            "version": "1.0.0",
        },
    )

    # Initialize Telegram Bot with custom timeout settings
    # Increase timeouts for file downloads and API calls (receipts can be large, network can be slow)
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,  # Increased from 10s to 30s for slow TLS connections
        read_timeout=60.0,  # Increased from 30s to 60s for large file downloads
        write_timeout=30.0,  # Increased from 10s to 30s for large file uploads
        pool_timeout=10.0,  # Increased from 5s to 10s for connection pool
    )
    bot = Bot(token=settings.telegram_bot_token, request=request)
    app.state.bot = bot
    logger.info(
        "Telegram Bot initialized with extended timeout settings (connect=30s, read=60s, write=30s)"
    )

    # Initialize state manager
    state_manager = StateManager(state_timeout_minutes=30)
    app.state.state_manager = state_manager
    logger.info("StateManager initialized")

    # Start state cleanup background task
    state_manager.start_cleanup_task()
    logger.info("State cleanup task started")

    # Initialize backend client
    backend_client = BackendClient(
        backend_url=settings.backend_api_url,
        backend_secret=settings.backend_webhook_secret,
        bot_token=settings.telegram_bot_token,
    )
    app.state.backend_client = backend_client
    logger.info("BackendClient initialized")

    # Initialize message service
    message_service = MessageService(backend_client=backend_client)
    app.state.message_service = message_service
    logger.info("MessageService initialized")

    # Message poller disabled - using webhook-based notifications instead
    # Admin messages are now sent via backend webhook
    message_poller = None
    app.state.message_poller = message_poller
    logger.info("MessagePoller disabled (using webhooks)")

    # Initialize order service
    order_service = OrderService(backend_client=backend_client)
    app.state.order_service = order_service
    logger.info("OrderService initialized")

    # Initialize settings service
    settings_service = SettingsService(
        backend_client=backend_client, refresh_interval_minutes=10
    )
    app.state.settings_service = settings_service
    logger.info("SettingsService initialized")

    # Fetch initial settings and bank accounts
    logger.info("Fetching initial settings and bank accounts...")
    await settings_service.refresh_all()

    # Start periodic refresh background task
    settings_service.start_periodic_refresh()
    logger.info("Settings periodic refresh started")

    # Initialize webhook manager
    webhook_manager = WebhookManager(
        bot=bot,
        webhook_url=settings.telegram_webhook_url,
        webhook_secret=settings.telegram_webhook_secret,
    )
    app.state.webhook_manager = webhook_manager

    # Register webhook with Telegram
    webhook_registered = await webhook_manager.register_webhook()
    if not webhook_registered:
        logger.error("Failed to register webhook - bot may not receive updates")

    # Initialize user notifier
    from app.services.user_notifier import UserNotifier

    user_notifier = UserNotifier(bot=bot, state_manager=state_manager)
    app.state.user_notifier = user_notifier
    logger.info("UserNotifier initialized")

    # Initialize admin notifier
    from app.services.admin_notifier import AdminNotifier

    admin_notifier = AdminNotifier(
        bot=bot,
        admin_group_id=settings.admin_group_id,
        buy_topic_id=settings.buy_topic_id,
        sell_topic_id=settings.sell_topic_id,
        balance_topic_id=settings.balance_topic_id,
    )
    app.state.admin_notifier = admin_notifier
    logger.info("AdminNotifier initialized")

    # Initialize order completion service
    from app.services.order_completion import OrderCompletionService

    order_completion_service = OrderCompletionService(
        backend_api_url=settings.backend_api_url,
        backend_secret=settings.backend_webhook_secret,
    )
    app.state.order_completion_service = order_completion_service
    logger.info("OrderCompletionService initialized")

    # Initialize OCR service for admin message handler
    from app.services.ocr_service import OCRService

    ocr_service = OCRService(
        openai_api_key=settings.openai_api_key,
        admin_banks=[],  # Admin message handler doesn't need bank matching
        min_confidence=0.0,  # No confidence threshold for staff receipts - just extract amount
    )
    app.state.ocr_service = ocr_service
    logger.info("OCRService initialized for admin message handler (no bank validation)")

    # Initialize admin message handler
    from app.handlers.admin_message_handler import AdminMessageHandler

    admin_message_handler = AdminMessageHandler(
        bot=bot,
        admin_group_id=settings.admin_group_id,
        buy_topic_id=settings.buy_topic_id,
        sell_topic_id=settings.sell_topic_id,
        ocr_service=ocr_service,
        order_completion_service=order_completion_service,
        admin_notifier=admin_notifier,
        user_notifier=user_notifier,
        backend_api_url=settings.backend_api_url,
    )
    app.state.admin_message_handler = admin_message_handler
    logger.info("AdminMessageHandler initialized")

    # Initialize handlers
    app.state.telegram_handler = TelegramHandler(
        bot=bot,
        state_manager=state_manager,
        message_service=message_service,
        message_poller=message_poller,
        order_service=order_service,
        settings_service=settings_service,
        admin_message_handler=admin_message_handler,
    )
    app.state.backend_webhook_handler = BackendWebhookHandler(
        bot=bot,
        user_notifier=user_notifier,
        admin_notifier=admin_notifier,
        order_completion_service=order_completion_service,
        state_manager=state_manager,
    )

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI bot engine")

    # Stop settings periodic refresh
    if hasattr(app.state, "settings_service"):
        app.state.settings_service.stop_periodic_refresh()
        logger.info("Settings periodic refresh stopped")

    # Stop message polling (if enabled)
    if hasattr(app.state, "message_poller") and app.state.message_poller:
        await app.state.message_poller.stop_all_polling()
        logger.info("Message polling stopped")

    # Stop state cleanup task
    if hasattr(app.state, "state_manager"):
        app.state.state_manager.stop_cleanup_task()
        logger.info("State cleanup task stopped")

    # Close order completion service
    if hasattr(app.state, "order_completion_service"):
        await app.state.order_completion_service.close()
        logger.info("Order completion service closed")

    # Close backend client
    if hasattr(app.state, "backend_client"):
        await app.state.backend_client.close()
        logger.info("Backend client closed")

    # Delete webhook on shutdown
    if hasattr(app.state, "webhook_manager"):
        await app.state.webhook_manager.delete_webhook()
        logger.info("Webhook deleted")

    # Close bot session
    if hasattr(app.state, "bot"):
        await app.state.bot.shutdown()
        logger.info("Bot session closed")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Load settings
    settings = get_settings()

    # Setup logging
    use_json = settings.environment == "production"
    setup_logging(log_level=settings.log_level, use_json=use_json)

    # Create FastAPI app
    app = FastAPI(
        title="Telegram Bot Engine",
        description="FastAPI-based Telegram bot with webhook support",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add middleware (order matters - last added is executed first)
    # Request logging middleware (innermost)
    app.add_middleware(RequestLoggingMiddleware)

    # Error handling middleware (outermost)
    app.add_middleware(ErrorHandlingMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Include webhook routes
    app.include_router(webhook_router)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "environment": settings.environment,
        }

    logger.info("FastAPI application created successfully")

    return app


# Create app instance
app = create_app()
