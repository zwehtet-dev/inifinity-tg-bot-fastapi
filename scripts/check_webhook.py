#!/usr/bin/env python3
"""
Script to check Telegram webhook registration status.

Usage:
    python scripts/check_webhook.py
    
Environment variables required:
    TELEGRAM_BOT_TOKEN: Bot token from BotFather
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from app.utils.webhook_manager import WebhookManager
from app.logging_config import get_logger


logger = get_logger(__name__)


async def main():
    """Check webhook registration status."""
    # Get configuration from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Validate required environment variables
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required")
        sys.exit(1)
    
    logger.info("Checking webhook status...")
    
    # Initialize bot and webhook manager
    bot = Bot(token=bot_token)
    webhook_manager = WebhookManager(
        bot=bot,
        webhook_url="",  # Not needed for checking
        webhook_secret=""  # Not needed for checking
    )
    
    # Get webhook info
    webhook_info = await webhook_manager.get_webhook_info()
    
    if not webhook_info:
        logger.error("✗ Failed to retrieve webhook information")
        sys.exit(1)
    
    # Display webhook information
    print("\n" + "="*60)
    print("TELEGRAM WEBHOOK STATUS")
    print("="*60)
    
    if webhook_info.url:
        print(f"Status: ✓ ACTIVE")
        print(f"URL: {webhook_info.url}")
        print(f"Has custom certificate: {webhook_info.has_custom_certificate}")
        print(f"Pending update count: {webhook_info.pending_update_count}")
        print(f"Max connections: {webhook_info.max_connections}")
        
        if webhook_info.allowed_updates:
            print(f"Allowed updates: {', '.join(webhook_info.allowed_updates)}")
        else:
            print("Allowed updates: All")
        
        if webhook_info.last_error_date:
            error_date = datetime.fromtimestamp(webhook_info.last_error_date)
            print(f"\n⚠ Last error:")
            print(f"  Date: {error_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Message: {webhook_info.last_error_message}")
        else:
            print("\n✓ No errors reported")
        
        if webhook_info.last_synchronization_error_date:
            sync_error_date = datetime.fromtimestamp(webhook_info.last_synchronization_error_date)
            print(f"\n⚠ Last synchronization error:")
            print(f"  Date: {sync_error_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if webhook_info.ip_address:
            print(f"\nIP Address: {webhook_info.ip_address}")
    else:
        print("Status: ✗ NOT SET")
        print("\nNo webhook is currently registered.")
        print("The bot is either using polling or not running.")
    
    print("="*60 + "\n")
    
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
