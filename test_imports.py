"""
Test script to verify all imports work correctly.
"""
import sys
import os

# Set dummy environment variables to allow imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy_token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "dummy_secret")
os.environ.setdefault("TELEGRAM_WEBHOOK_URL", "https://example.com/webhook/telegram")
os.environ.setdefault("BACKEND_API_URL", "https://example.com")
os.environ.setdefault("BACKEND_WEBHOOK_SECRET", "dummy_secret")
os.environ.setdefault("OPENAI_API_KEY", "dummy_key")
os.environ.setdefault("ADMIN_GROUP_ID", "-1001234567890")
os.environ.setdefault("BUY_TOPIC_ID", "123")
os.environ.setdefault("SELL_TOPIC_ID", "456")
os.environ.setdefault("BALANCE_TOPIC_ID", "789")

try:
    print("Testing imports...")
    
    # Test config
    from app.config import get_settings
    print("✓ Config module imports successfully")
    
    # Test logging
    from app.logging_config import setup_logging, get_logger
    print("✓ Logging module imports successfully")
    
    # Test webhook routes
    from app.routes.webhooks import router
    print("✓ Webhook routes import successfully")
    
    # Test handlers
    from app.handlers.telegram_handler import TelegramHandler
    print("✓ Telegram handler imports successfully")
    
    from app.handlers.backend_webhook import BackendWebhookHandler
    print("✓ Backend webhook handler imports successfully")
    
    # Test utils
    from app.utils.webhook_manager import WebhookManager
    print("✓ Webhook manager imports successfully")
    
    # Test main app (without running it)
    from app.main import create_app
    print("✓ Main app imports successfully")
    
    print("\n✅ All imports successful!")
    print("\nNote: The app cannot be fully started without valid environment variables.")
    print("Please configure .env file before running the application.")
    
except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
