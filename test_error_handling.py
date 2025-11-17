"""
Test script for error handling utilities and middleware.

Verifies that error handlers and middleware are properly configured.
"""
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from telegram import Bot
from telegram.error import (
    NetworkError,
    Forbidden,
    RetryAfter,
    BadRequest,
    Conflict
)
from openai import (
    RateLimitError,
    AuthenticationError,
    APITimeoutError,
    APIConnectionError,
    BadRequestError
)
import httpx

# Import error handlers
from app.utils.error_handlers import ErrorHandler


async def test_telegram_error_handlers():
    """Test Telegram error handling."""
    print("Testing Telegram error handlers...")
    
    # Mock bot and admin group
    mock_bot = Mock(spec=Bot)
    mock_bot.send_message = AsyncMock()
    admin_group_id = -1001234567890
    
    handler = ErrorHandler(mock_bot, admin_group_id)
    
    # Test Forbidden error (should not retry)
    print("  - Testing Forbidden error...")
    should_retry = await handler.handle_telegram_error(
        Forbidden("Bot was blocked"),
        {"user_id": 123, "chat_id": 456, "operation": "send_message"}
    )
    assert should_retry is False, "Forbidden should not retry"
    print("    ✓ Forbidden handled correctly (no retry)")
    
    # Test NetworkError (should retry)
    print("  - Testing NetworkError...")
    should_retry = await handler.handle_telegram_error(
        NetworkError("Connection failed"),
        {"user_id": 123, "chat_id": 456, "operation": "send_message"}
    )
    assert should_retry is True, "NetworkError should retry"
    print("    ✓ NetworkError handled correctly (retry)")
    
    # Test RetryAfter (should retry)
    print("  - Testing RetryAfter error...")
    retry_error = RetryAfter(30)
    should_retry = await handler.handle_telegram_error(
        retry_error,
        {"user_id": 123, "chat_id": 456, "operation": "send_message"}
    )
    assert should_retry is True, "RetryAfter should retry"
    assert mock_bot.send_message.called, "Should notify admin about rate limit"
    print("    ✓ RetryAfter handled correctly (retry + admin notification)")
    
    # Test BadRequest (should not retry)
    print("  - Testing BadRequest error...")
    mock_bot.send_message.reset_mock()
    should_retry = await handler.handle_telegram_error(
        BadRequest("Invalid message"),
        {"user_id": 123, "chat_id": 456, "operation": "send_message"}
    )
    assert should_retry is False, "BadRequest should not retry"
    assert mock_bot.send_message.called, "Should notify admin about bad request"
    print("    ✓ BadRequest handled correctly (no retry + admin notification)")
    
    # Test Conflict (should not retry)
    print("  - Testing Conflict error...")
    mock_bot.send_message.reset_mock()
    should_retry = await handler.handle_telegram_error(
        Conflict("Webhook conflict"),
        {"user_id": 123, "chat_id": 456, "operation": "webhook"}
    )
    assert should_retry is False, "Conflict should not retry"
    assert mock_bot.send_message.called, "Should notify admin about conflict"
    print("    ✓ Conflict handled correctly (no retry + critical notification)")
    
    print("✓ All Telegram error handler tests passed!\n")


async def test_ocr_error_handlers():
    """Test OCR error handling."""
    print("Testing OCR error handlers...")
    
    # Mock bot and admin group
    mock_bot = Mock(spec=Bot)
    mock_bot.send_message = AsyncMock()
    admin_group_id = -1001234567890
    
    handler = ErrorHandler(mock_bot, admin_group_id)
    
    # Create mock response for OpenAI errors
    mock_response = Mock()
    mock_response.request = Mock()
    mock_response.status_code = 429
    
    # Test RateLimitError
    print("  - Testing RateLimitError...")
    message = await handler.handle_ocr_error(
        RateLimitError("Rate limit exceeded", response=mock_response, body=None),
        {"user_id": 123, "chat_id": 456}
    )
    assert message is not None, "Should return user message"
    assert "busy" in message.lower() or "wait" in message.lower(), "Should mention waiting"
    assert mock_bot.send_message.called, "Should notify admin"
    print("    ✓ RateLimitError handled correctly")
    
    # Test AuthenticationError
    print("  - Testing AuthenticationError...")
    mock_bot.send_message.reset_mock()
    mock_response.status_code = 401
    message = await handler.handle_ocr_error(
        AuthenticationError("Invalid API key", response=mock_response, body=None),
        {"user_id": 123, "chat_id": 456}
    )
    assert message is not None, "Should return user message"
    assert "unavailable" in message.lower() or "manual" in message.lower(), "Should mention manual review"
    assert mock_bot.send_message.called, "Should notify admin with critical alert"
    print("    ✓ AuthenticationError handled correctly")
    
    # Test APITimeoutError
    print("  - Testing APITimeoutError...")
    mock_bot.send_message.reset_mock()
    mock_request = Mock()
    message = await handler.handle_ocr_error(
        APITimeoutError(request=mock_request),
        {"user_id": 123, "chat_id": 456}
    )
    assert message is not None, "Should return user message"
    assert "timeout" in message.lower() or "try again" in message.lower(), "Should mention timeout"
    print("    ✓ APITimeoutError handled correctly")
    
    # Test APIConnectionError
    print("  - Testing APIConnectionError...")
    message = await handler.handle_ocr_error(
        APIConnectionError(request=mock_request),
        {"user_id": 123, "chat_id": 456}
    )
    assert message is not None, "Should return user message"
    assert "connection" in message.lower() or "try again" in message.lower(), "Should mention connection"
    print("    ✓ APIConnectionError handled correctly")
    
    # Test BadRequestError
    print("  - Testing BadRequestError...")
    mock_response.status_code = 400
    message = await handler.handle_ocr_error(
        BadRequestError("Invalid image", response=mock_response, body=None),
        {"user_id": 123, "chat_id": 456}
    )
    assert message is not None, "Should return user message"
    assert "image" in message.lower() or "photo" in message.lower(), "Should mention image issue"
    print("    ✓ BadRequestError handled correctly")
    
    print("✓ All OCR error handler tests passed!\n")


async def test_backend_error_handlers():
    """Test backend API error handling."""
    print("Testing backend error handlers...")
    
    # Mock bot and admin group
    mock_bot = Mock(spec=Bot)
    mock_bot.send_message = AsyncMock()
    admin_group_id = -1001234567890
    
    handler = ErrorHandler(mock_bot, admin_group_id)
    
    # Test TimeoutException (should retry)
    print("  - Testing TimeoutException...")
    should_retry = await handler.handle_backend_error(
        httpx.TimeoutException("Request timeout"),
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is True, "TimeoutException should retry"
    assert mock_bot.send_message.called, "Should notify admin"
    print("    ✓ TimeoutException handled correctly (retry)")
    
    # Test ConnectError (should retry)
    print("  - Testing ConnectError...")
    mock_bot.send_message.reset_mock()
    should_retry = await handler.handle_backend_error(
        httpx.ConnectError("Cannot connect"),
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is True, "ConnectError should retry"
    assert mock_bot.send_message.called, "Should notify admin about backend down"
    print("    ✓ ConnectError handled correctly (retry + critical notification)")
    
    # Test NetworkError (should retry)
    print("  - Testing NetworkError...")
    mock_bot.send_message.reset_mock()
    should_retry = await handler.handle_backend_error(
        httpx.NetworkError("Network error"),
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is True, "NetworkError should retry"
    print("    ✓ NetworkError handled correctly (retry)")
    
    # Test HTTPStatusError 500 (should retry)
    print("  - Testing HTTPStatusError 500...")
    mock_bot.send_message.reset_mock()
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"
    http_error = httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)
    should_retry = await handler.handle_backend_error(
        http_error,
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is True, "500 error should retry"
    assert mock_bot.send_message.called, "Should notify admin"
    print("    ✓ HTTPStatusError 500 handled correctly (retry)")
    
    # Test HTTPStatusError 400 (should not retry)
    print("  - Testing HTTPStatusError 400...")
    mock_bot.send_message.reset_mock()
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad request"
    http_error = httpx.HTTPStatusError("Bad request", request=Mock(), response=mock_response)
    should_retry = await handler.handle_backend_error(
        http_error,
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is False, "400 error should not retry"
    assert mock_bot.send_message.called, "Should notify admin"
    print("    ✓ HTTPStatusError 400 handled correctly (no retry)")
    
    # Test HTTPStatusError 429 (should retry)
    print("  - Testing HTTPStatusError 429...")
    mock_bot.send_message.reset_mock()
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"
    http_error = httpx.HTTPStatusError("Rate limited", request=Mock(), response=mock_response)
    should_retry = await handler.handle_backend_error(
        http_error,
        {"user_id": 123, "chat_id": 456, "endpoint": "/api/orders/submit"}
    )
    assert should_retry is True, "429 error should retry"
    assert mock_bot.send_message.called, "Should notify admin"
    print("    ✓ HTTPStatusError 429 handled correctly (retry)")
    
    print("✓ All backend error handler tests passed!\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Error Handling Test Suite")
    print("=" * 60)
    print()
    
    try:
        await test_telegram_error_handlers()
        await test_ocr_error_handlers()
        await test_backend_error_handlers()
        
        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
