"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def test_env():
    """Set up test environment variables."""
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token_12345678901234567890123456789012")
    os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test_secret")
    os.environ.setdefault("TELEGRAM_WEBHOOK_URL", "https://test.com/webhook")
    os.environ.setdefault("BACKEND_API_URL", "https://test-backend.com")
    os.environ.setdefault("BACKEND_WEBHOOK_SECRET", "test_backend_secret")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test_openai_key_1234567890")
    os.environ.setdefault("ADMIN_GROUP_ID", "-1001234567890")
    os.environ.setdefault("BUY_TOPIC_ID", "1")
    os.environ.setdefault("SELL_TOPIC_ID", "2")
    os.environ.setdefault("BALANCE_TOPIC_ID", "3")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("ENVIRONMENT", "test")
    
    yield
    
    # Cleanup if needed
    pass


@pytest.fixture
def mock_telegram_bot():
    """Mock Telegram bot for testing."""
    from unittest.mock import AsyncMock, MagicMock
    
    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    
    return bot


@pytest.fixture
def mock_backend_client():
    """Mock backend client for testing."""
    from unittest.mock import AsyncMock, MagicMock
    
    client = MagicMock()
    client.get_banks = AsyncMock(return_value=[])
    client.create_order = AsyncMock(return_value={"id": 1, "order_number": "TEST001"})
    client.get_settings = AsyncMock(return_value={})
    
    return client
