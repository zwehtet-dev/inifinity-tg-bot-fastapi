#!/usr/bin/env python3
"""
Script to delete Telegram webhook (for rollback).

Usage:
    python scripts/delete_webhook.py
    
Environment variables required:
    TELEGRAM_BOT_TOKEN: Bot token from BotFather
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
    """Delete webhook from Telegram."""
    # Get configuration from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Validate required environment variables
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    logger.info("Starting webhook deletion...")
    
    # Initialize bot and webhook manager
    bot = Bot(token=bot_token)
    webhook_manager = WebhookManager(
        bot=bot,
        webhook_url="",  # Not needed for deletion
        webhook_secret=""  # Not needed for deletion
    )
    
    # Get current webhook info before deletion
    logger.info("Current webhook status:")
    webhook_info = await webhook_manager.get_webhook_info()
    if webhook_info and webhook_info.url:
        print(f"\nCurrent webhook URL: {webhook_info.url}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
    else:
        print("\nNo webhook is currently set")
    
    # Confirm deletion
    print("\n" + "="*60)
    response = input("Are you sure you want to delete the webhook? (yes/no): ")
    print("="*60)
    
    if response.lower() not in ['yes', 'y']:
        logger.info("Webhook deletion cancelled")
        sys.exit(0)
    
    # Delete webhook
    success = await webhook_manager.delete_webhook()
    
    if success:
        logger.info("✓ Webhook deleted successfully!")
        logger.info("Bot will now need to use polling or register a new webhook")
        sys.exit(0)
    else:
        logger.error("✗ Failed to delete webhook")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
