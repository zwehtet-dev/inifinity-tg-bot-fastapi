"""
Test webhook manager functionality.
"""
import pytest
from app.utils.webhook_manager import WebhookManager
from unittest.mock import Mock, AsyncMock


def test_validate_webhook_url_valid_https():
    """Test validation of valid HTTPS webhook URL."""
    bot = Mock()
    manager = WebhookManager(bot, "https://example.com/webhook", "secret")
    
    is_valid, error = manager.validate_webhook_url("https://example.com/webhook/telegram")
    assert is_valid is True
    assert error == ""


def test_validate_webhook_url_valid_localhost():
    """Test validation of localhost HTTP URL (allowed for testing)."""
    bot = Mock()
    manager = WebhookManager(bot, "http://localhost:8443/webhook", "secret")
    
    is_valid, error = manager.validate_webhook_url("http://localhost:8443/webhook")
    assert is_valid is True
    assert error == ""


def test_validate_webhook_url_invalid_http():
    """Test validation rejects HTTP for non-localhost."""
    bot = Mock()
    manager = WebhookManager(bot, "http://example.com/webhook", "secret")
    
    is_valid, error = manager.validate_webhook_url("http://example.com/webhook")
    assert is_valid is False
    assert "HTTPS" in error


def test_validate_webhook_url_with_query_params():
    """Test validation rejects URLs with query parameters."""
    bot = Mock()
    manager = WebhookManager(bot, "https://example.com/webhook?token=123", "secret")
    
    is_valid, error = manager.validate_webhook_url("https://example.com/webhook?token=123")
    assert is_valid is False
    assert "query parameters" in error


def test_validate_webhook_url_invalid_port():
    """Test validation rejects invalid ports."""
    bot = Mock()
    manager = WebhookManager(bot, "https://example.com:9000/webhook", "secret")
    
    is_valid, error = manager.validate_webhook_url("https://example.com:9000/webhook")
    assert is_valid is False
    assert "port" in error.lower()


def test_validate_webhook_url_valid_ports():
    """Test validation accepts valid ports."""
    bot = Mock()
    manager = WebhookManager(bot, "https://example.com/webhook", "secret")
    
    valid_ports = [443, 80, 88, 8443]
    for port in valid_ports:
        url = f"https://example.com:{port}/webhook"
        is_valid, error = manager.validate_webhook_url(url)
        assert is_valid is True, f"Port {port} should be valid"


def test_validate_webhook_url_empty():
    """Test validation rejects empty URL."""
    bot = Mock()
    manager = WebhookManager(bot, "", "secret")
    
    is_valid, error = manager.validate_webhook_url("")
    assert is_valid is False
    assert "empty" in error.lower()


def test_validate_webhook_url_no_hostname():
    """Test validation rejects URL without hostname."""
    bot = Mock()
    manager = WebhookManager(bot, "https:///webhook", "secret")
    
    is_valid, error = manager.validate_webhook_url("https:///webhook")
    assert is_valid is False
    assert "hostname" in error.lower()


@pytest.mark.asyncio
async def test_register_webhook_validates_url():
    """Test that register_webhook validates URL before registration."""
    bot = Mock()
    bot.set_webhook = AsyncMock(return_value=True)
    bot.get_webhook_info = AsyncMock()
    
    # Invalid URL (HTTP for non-localhost)
    manager = WebhookManager(bot, "http://example.com/webhook", "secret")
    
    success = await manager.register_webhook()
    
    assert success is False
    bot.set_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_register_webhook_success():
    """Test successful webhook registration."""
    bot = Mock()
    bot.set_webhook = AsyncMock(return_value=True)
    
    webhook_info = Mock()
    webhook_info.url = "https://example.com/webhook"
    webhook_info.pending_update_count = 0
    webhook_info.has_custom_certificate = False
    bot.get_webhook_info = AsyncMock(return_value=webhook_info)
    
    manager = WebhookManager(bot, "https://example.com/webhook", "secret")
    
    success = await manager.register_webhook()
    
    assert success is True
    bot.set_webhook.assert_called_once()


@pytest.mark.asyncio
async def test_delete_webhook_success():
    """Test successful webhook deletion."""
    bot = Mock()
    bot.delete_webhook = AsyncMock(return_value=True)
    
    manager = WebhookManager(bot, "https://example.com/webhook", "secret")
    
    success = await manager.delete_webhook()
    
    assert success is True
    bot.delete_webhook.assert_called_once()


@pytest.mark.asyncio
async def test_get_webhook_info_success():
    """Test getting webhook info."""
    bot = Mock()
    
    webhook_info = Mock()
    webhook_info.url = "https://example.com/webhook"
    webhook_info.pending_update_count = 5
    webhook_info.last_error_date = None
    webhook_info.last_error_message = None
    bot.get_webhook_info = AsyncMock(return_value=webhook_info)
    
    manager = WebhookManager(bot, "https://example.com/webhook", "secret")
    
    info = await manager.get_webhook_info()
    
    assert info is not None
    assert info.url == "https://example.com/webhook"
    assert info.pending_update_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
