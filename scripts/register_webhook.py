#!/usr/bin/env python3
"""
Script to register Telegram webhook.

Usage:
    python scripts/register_webhook.py
    
Environment variables required:
    TELEGRAM_BOT_TOKEN: Bot token from BotFather
    WEBHOOK_URL: Public URL for webhook endpoint (e.g., https://example.com/webhook/telegram)
    TELEGRAM_WEBHOOK_SECRET: Secret token for webhook validation
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from app.utils.webhook_manager import WebhookManager
from app.logging_config import get_logger


logger = get_logger(__name__)


async def main():
    """Register webhook with Telegram."""
    # Get configuration from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    
    # Validate required environment variables
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    if not webhook_url:
        logger.error("WEBHOOK_URL environment variable is required")
        sys.exit(1)
    
    if not webhook_secret:
        logger.error("TELEGRAM_WEBHOOK_SECRET environment variable is required")
        sys.exit(1)
    
    logger.info("Starting webhook registration...")
    logger.info(f"Webhook URL: {webhook_url}")
    
    # Initialize bot and webhook manager
    bot = Bot(token=bot_token)
    webhook_manager = WebhookManager(
        bot=bot,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret
    )
    
    # Register webhook
    success = await webhook_manager.register_webhook()
    
    if success:
        logger.info("✓ Webhook registered successfully!")
        
        # Get and display webhook info
        webhook_info = await webhook_manager.get_webhook_info()
        if webhook_info:
            print("\n" + "="*60)
            print("Webhook Information:")
            print("="*60)
            print(f"URL: {webhook_info.url}")
            print(f"Has custom certificate: {webhook_info.has_custom_certificate}")
            print(f"Pending update count: {webhook_info.pending_update_count}")
            print(f"Max connections: {webhook_info.max_connections}")
            print(f"Allowed updates: {webhook_info.allowed_updates}")
            if webhook_info.last_error_date:
                print(f"Last error date: {webhook_info.last_error_date}")
                print(f"Last error message: {webhook_info.last_error_message}")
            print("="*60)
        
        sys.exit(0)
    else:
        logger.error("✗ Failed to register webhook")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
