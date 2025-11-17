"""
Test script for OrderService functionality.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.order_service import OrderService
from app.services.backend_client import BackendClient


async def test_order_service():
    """Test OrderService methods."""
    print("Testing OrderService...")
    
    # Create mock backend client
    mock_backend_client = MagicMock(spec=BackendClient)
    
    # Mock submit_order method
    mock_backend_client.submit_order = AsyncMock(return_value="ORD-TEST-001")
    
    # Mock check_pending_order method
    mock_backend_client.check_pending_order = AsyncMock(return_value=False)
    
    # Create OrderService instance
    order_service = OrderService(backend_client=mock_backend_client)
    
    # Test submit_order
    print("\n1. Testing submit_order...")
    order_id = await order_service.submit_order(
        order_type="buy",
        amount=1000.0,
        price=0.0035,
        receipt_file_ids=["file_id_1", "file_id_2"],
        user_bank="KBZ Bank - 1234567890 - John Doe",
        chat_id=123456789,
        qr_file_id="qr_file_id",
        myanmar_bank="KBZ"
    )
    
    assert order_id == "ORD-TEST-001", f"Expected 'ORD-TEST-001', got '{order_id}'"
    print(f"✓ submit_order returned order_id: {order_id}")
    
    # Verify backend client was called with correct parameters
    mock_backend_client.submit_order.assert_called_once()
    call_args = mock_backend_client.submit_order.call_args
    assert call_args.kwargs["order_type"] == "buy"
    assert call_args.kwargs["amount"] == 1000.0
    assert call_args.kwargs["price"] == 0.0035
    assert len(call_args.kwargs["receipt_file_ids"]) == 2
    print("✓ Backend client called with correct parameters")
    
    # Test check_pending_order
    print("\n2. Testing check_pending_order...")
    has_pending = await order_service.check_pending_order(chat_id=123456789)
    
    assert has_pending is False, f"Expected False, got {has_pending}"
    print(f"✓ check_pending_order returned: {has_pending}")
    
    # Verify backend client was called
    mock_backend_client.check_pending_order.assert_called_once_with(123456789)
    print("✓ Backend client called with correct chat_id")
    
    # Test error handling - submit_order returns None
    print("\n3. Testing error handling (submit_order returns None)...")
    mock_backend_client.submit_order = AsyncMock(return_value=None)
    order_id = await order_service.submit_order(
        order_type="sell",
        amount=500.0,
        price=0.0034,
        receipt_file_ids=["file_id_3"],
        user_bank="Bangkok Bank - 123-4-56789-0 - Jane Doe",
        chat_id=987654321
    )
    
    assert order_id is None, f"Expected None, got '{order_id}'"
    print("✓ submit_order correctly returned None on failure")
    
    # Test error handling - check_pending_order raises exception
    print("\n4. Testing error handling (check_pending_order raises exception)...")
    mock_backend_client.check_pending_order = AsyncMock(side_effect=Exception("Network error"))
    has_pending = await order_service.check_pending_order(chat_id=123456789)
    
    assert has_pending is False, f"Expected False on error, got {has_pending}"
    print("✓ check_pending_order correctly returned False on exception")
    
    print("\n✅ All OrderService tests passed!")


if __name__ == "__main__":
    asyncio.run(test_order_service())
