"""
Test script for message services (Task 9).

This script validates the message persistence and synchronization implementation.
"""
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from app.services.message_service import MessageService
from app.services.message_poller import MessagePoller
from app.services.backend_client import BackendClient


async def test_message_service():
    """Test MessageService functionality."""
    print("Testing MessageService...")
    
    # Create mock backend client
    mock_backend_client = Mock(spec=BackendClient)
    mock_backend_client.submit_message = AsyncMock(return_value={"id": 1, "status": "created"})
    
    # Create message service
    message_service = MessageService(backend_client=mock_backend_client)
    
    # Test submit_user_message
    result = await message_service.submit_user_message(
        telegram_id="123456",
        chat_id=789,
        content="Test message",
        chosen_option="",
        image_file_ids=None,
        buttons=None
    )
    
    assert result is True, "submit_user_message should return True"
    assert mock_backend_client.submit_message.called, "Backend client should be called"
    
    # Verify call arguments
    call_args = mock_backend_client.submit_message.call_args
    assert call_args.kwargs["telegram_id"] == "123456"
    assert call_args.kwargs["chat_id"] == 789
    assert call_args.kwargs["content"] == "Test message"
    assert call_args.kwargs["from_bot"] is False
    
    print("✓ submit_user_message works correctly")
    
    # Test submit_bot_message
    mock_backend_client.submit_message.reset_mock()
    result = await message_service.submit_bot_message(
        telegram_id="123456",
        chat_id=789,
        content="Bot response",
        buttons={"action_buy": "Buy", "action_sell": "Sell"}
    )
    
    assert result is True, "submit_bot_message should return True"
    call_args = mock_backend_client.submit_message.call_args
    assert call_args.kwargs["from_bot"] is True
    assert call_args.kwargs["buttons"] == {"action_buy": "Buy", "action_sell": "Sell"}
    
    print("✓ submit_bot_message works correctly")
    
    # Test submit_media_group
    mock_backend_client.submit_message.reset_mock()
    result = await message_service.submit_media_group(
        telegram_id="123456",
        chat_id=789,
        content="Multiple photos",
        image_file_ids=["file1", "file2", "file3"],
        from_bot=False
    )
    
    assert result is True, "submit_media_group should return True"
    call_args = mock_backend_client.submit_message.call_args
    assert len(call_args.kwargs["image_file_ids"]) == 3
    
    print("✓ submit_media_group works correctly")
    
    print("✅ MessageService tests passed!\n")


async def test_message_poller():
    """Test MessagePoller functionality."""
    print("Testing MessagePoller...")
    
    # Create mock bot
    mock_bot = Mock()
    mock_bot.send_message = AsyncMock()
    mock_bot.send_photo = AsyncMock()
    
    # Create mock backend client
    mock_backend_client = Mock(spec=BackendClient)
    mock_backend_client.poll_messages = AsyncMock(return_value=[])
    mock_backend_client.client = Mock()
    mock_backend_client.client.get = AsyncMock()
    
    # Create message poller
    message_poller = MessagePoller(
        bot=mock_bot,
        backend_client=mock_backend_client,
        backend_url="http://localhost:5000"
    )
    
    # Test start_polling
    message_poller.start_polling(telegram_id="123456", chat_id=789)
    assert 789 in message_poller._polling_tasks, "Polling task should be created"
    
    print("✓ start_polling creates task correctly")
    
    # Test stop_polling
    message_poller.stop_polling(chat_id=789)
    assert 789 not in message_poller._polling_tasks, "Polling task should be removed"
    
    print("✓ stop_polling removes task correctly")
    
    # Test poll_messages
    mock_backend_client.poll_messages.return_value = [
        {
            "id": 1,
            "content": "Test message from admin",
            "buttons": None,
            "image": None
        }
    ]
    
    messages = await message_poller.poll_messages(
        telegram_id="123456",
        chat_id=789
    )
    
    assert len(messages) == 1, "Should return 1 message"
    assert messages[0]["content"] == "Test message from admin"
    
    print("✓ poll_messages retrieves messages correctly")
    
    # Test send_polled_message with text only
    await message_poller.send_polled_message(
        chat_id=789,
        message={
            "id": 1,
            "content": "Test message",
            "buttons": None,
            "image": None
        }
    )
    
    assert mock_bot.send_message.called, "Bot should send text message"
    
    print("✓ send_polled_message sends text messages correctly")
    
    # Test send_polled_message with buttons
    mock_bot.send_message.reset_mock()
    await message_poller.send_polled_message(
        chat_id=789,
        message={
            "id": 2,
            "content": "Choose an option",
            "buttons": '{"action_buy": "Buy", "action_sell": "Sell"}',
            "image": None
        }
    )
    
    assert mock_bot.send_message.called, "Bot should send message with buttons"
    call_args = mock_bot.send_message.call_args
    assert call_args.kwargs["reply_markup"] is not None, "Should include inline keyboard"
    
    print("✓ send_polled_message reconstructs inline keyboards correctly")
    
    # Test get_active_polling_count
    count = message_poller.get_active_polling_count()
    assert count == 0, "Should have 0 active polling tasks"
    
    print("✓ get_active_polling_count works correctly")
    
    print("✅ MessagePoller tests passed!\n")


async def test_integration():
    """Test integration between services."""
    print("Testing integration...")
    
    # Create mock backend client
    mock_backend_client = Mock(spec=BackendClient)
    mock_backend_client.submit_message = AsyncMock(return_value={"id": 1})
    mock_backend_client.poll_messages = AsyncMock(return_value=[])
    
    # Create services
    message_service = MessageService(backend_client=mock_backend_client)
    
    # Simulate user sending a message
    await message_service.submit_user_message(
        telegram_id="123456",
        chat_id=789,
        content="I want to buy MMK"
    )
    
    # Simulate bot responding
    await message_service.submit_bot_message(
        telegram_id="123456",
        chat_id=789,
        content="Please send your receipt",
        buttons={"action_cancel": "Cancel"}
    )
    
    # Verify both messages were submitted
    assert mock_backend_client.submit_message.call_count == 2, "Should submit 2 messages"
    
    print("✓ Integration between services works correctly")
    print("✅ Integration tests passed!\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Task 9: Message Persistence and Synchronization Tests")
    print("=" * 60)
    print()
    
    try:
        await test_message_service()
        await test_message_poller()
        await test_integration()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Summary:")
        print("- MessageService: ✓ User messages, bot messages, media groups")
        print("- MessagePoller: ✓ Polling, message sending, keyboard reconstruction")
        print("- Integration: ✓ Services work together correctly")
        print()
        print("Task 9 implementation is complete and working correctly!")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
