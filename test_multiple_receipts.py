"""
Test script for multiple receipt flow implementation.
"""
import asyncio
from app.services.receipt_manager import ReceiptManager
from app.models.receipt import ReceiptData
from app.models.order import OrderData


def test_receipt_manager():
    """Test ReceiptManager utility functions."""
    print("=" * 80)
    print("Testing ReceiptManager")
    print("=" * 80)
    
    manager = ReceiptManager()
    
    # Test 1: Bank match verification
    print("\n1. Testing bank match verification...")
    
    admin_banks = [
        {"id": 1, "bank_name": "KBank", "account_number": "123-4-56789-0", "account_name": "Admin"},
        {"id": 2, "bank_name": "Bangkok Bank", "account_number": "987-6-54321-0", "account_name": "Admin"}
    ]
    
    receipt1 = ReceiptData(
        amount=5000.0,
        bank_name="KBank",
        account_number="123-4-56789-0",
        account_name="Admin",
        confidence_score=0.95,
        matched_bank_id=1
    )
    
    # First receipt - should match (no expected bank yet)
    is_match, error = manager.verify_bank_match(receipt1, None, admin_banks)
    print(f"   First receipt (no expected bank): {is_match} ✓" if is_match else f"   First receipt: {is_match} ✗")
    
    # Second receipt - same bank
    is_match, error = manager.verify_bank_match(receipt1, 1, admin_banks)
    print(f"   Second receipt (same bank): {is_match} ✓" if is_match else f"   Second receipt: {is_match} ✗")
    
    # Third receipt - different bank
    receipt2 = ReceiptData(
        amount=3000.0,
        bank_name="Bangkok Bank",
        account_number="987-6-54321-0",
        account_name="Admin",
        confidence_score=0.90,
        matched_bank_id=2
    )
    
    is_match, error = manager.verify_bank_match(receipt2, 1, admin_banks)
    print(f"   Third receipt (different bank): {not is_match} ✓" if not is_match else f"   Third receipt: {is_match} ✗")
    if error:
        print(f"   Error message: {error[:50]}...")
    
    # Test 2: Get bank details
    print("\n2. Testing get bank details...")
    bank_name, account_number = manager.get_bank_details(1, admin_banks)
    print(f"   Bank ID 1: {bank_name} - {account_number}")
    assert bank_name == "KBank", "Bank name mismatch"
    assert account_number == "123-4-56789-0", "Account number mismatch"
    print("   ✓ Bank details correct")
    
    # Test 3: Calculate total
    print("\n3. Testing calculate total...")
    amounts = [5000.0, 3000.0, 2000.0]
    total = manager.calculate_total(amounts)
    print(f"   Amounts: {amounts}")
    print(f"   Total: {total}")
    assert total == 10000.0, "Total calculation incorrect"
    print("   ✓ Total calculation correct")
    
    # Test 4: Receipt limit validation
    print("\n4. Testing receipt limit validation...")
    is_valid, error = manager.validate_receipt_limit(5, max_receipts=10)
    print(f"   5 receipts (limit 10): {is_valid} ✓" if is_valid else f"   5 receipts: {is_valid} ✗")
    
    is_valid, error = manager.validate_receipt_limit(10, max_receipts=10)
    print(f"   10 receipts (limit 10): {not is_valid} ✓" if not is_valid else f"   10 receipts: {is_valid} ✗")
    if error:
        print(f"   Error message: {error[:50]}...")
    
    # Test 5: Format messages
    print("\n5. Testing message formatting...")
    
    # First receipt message
    message = manager.format_receipt_verified_message(
        receipt_number=1,
        amount=5000.0,
        currency="THB",
        total_amount=5000.0,
        bank_name="KBank",
        account_number="123-4-56789-0",
        is_first=True
    )
    print("   First receipt message:")
    print("   " + message.replace("\n", "\n   ")[:200] + "...")
    assert "Receipt 1" in message, "Receipt number missing"
    assert "5,000" in message, "Amount formatting incorrect"
    assert "KBank" in message, "Bank name missing"
    print("   ✓ First receipt message correct")
    
    # Additional receipt message
    message = manager.format_receipt_verified_message(
        receipt_number=2,
        amount=3000.0,
        currency="THB",
        total_amount=8000.0,
        is_first=False
    )
    print("\n   Additional receipt message:")
    print("   " + message.replace("\n", "\n   ")[:200] + "...")
    assert "Receipt 2" in message, "Receipt number missing"
    assert "8,000" in message, "Total formatting incorrect"
    print("   ✓ Additional receipt message correct")
    
    # Order summary
    summary = manager.format_order_summary(
        order_type="buy",
        receipt_count=3,
        total_amount=10000.0,
        currency="THB",
        bank_name="KBank",
        account_number="123-4-56789-0"
    )
    print("\n   Order summary:")
    print("   " + summary.replace("\n", "\n   ")[:200] + "...")
    assert "3" in summary, "Receipt count missing"
    assert "10,000" in summary, "Total missing"
    print("   ✓ Order summary correct")
    
    print("\n" + "=" * 80)
    print("✅ All ReceiptManager tests passed!")
    print("=" * 80)


def test_order_data_model():
    """Test OrderData model with multiple receipt fields."""
    print("\n" + "=" * 80)
    print("Testing OrderData Model")
    print("=" * 80)
    
    # Create order data
    order = OrderData(
        order_type="buy",
        receipt_file_ids=["file1", "file2", "file3"],
        receipt_amounts=[5000.0, 3000.0, 2000.0],
        receipt_bank_ids=[1, 1, 1],
        expected_bank_id=1,
        expected_bank_name="KBank",
        expected_account_number="123-4-56789-0",
        total_amount=10000.0,
        receipt_count=3,
        thb_amount=10000.0,
        exchange_rate=125.0
    )
    
    print(f"\nOrder Type: {order.order_type}")
    print(f"Receipt Count: {order.receipt_count}")
    print(f"Receipt File IDs: {order.receipt_file_ids}")
    print(f"Receipt Amounts: {order.receipt_amounts}")
    print(f"Receipt Bank IDs: {order.receipt_bank_ids}")
    print(f"Expected Bank ID: {order.expected_bank_id}")
    print(f"Expected Bank Name: {order.expected_bank_name}")
    print(f"Expected Account: {order.expected_account_number}")
    print(f"Total Amount: {order.total_amount}")
    print(f"THB Amount: {order.thb_amount}")
    
    # Validate
    assert len(order.receipt_file_ids) == 3, "Receipt file IDs count mismatch"
    assert len(order.receipt_amounts) == 3, "Receipt amounts count mismatch"
    assert len(order.receipt_bank_ids) == 3, "Receipt bank IDs count mismatch"
    assert order.total_amount == 10000.0, "Total amount incorrect"
    assert order.receipt_count == 3, "Receipt count incorrect"
    
    print("\n✅ OrderData model test passed!")
    print("=" * 80)


def test_flow_simulation():
    """Simulate the multiple receipt flow."""
    print("\n" + "=" * 80)
    print("Simulating Multiple Receipt Flow")
    print("=" * 80)
    
    manager = ReceiptManager()
    
    # Simulate admin banks
    admin_banks = [
        {"id": 1, "bank_name": "KBank", "account_number": "123-4-56789-0", "account_name": "Admin"},
        {"id": 2, "bank_name": "Bangkok Bank", "account_number": "987-6-54321-0", "account_name": "Admin"}
    ]
    
    # Initialize order
    order = OrderData(
        order_type="buy",
        exchange_rate=125.0
    )
    
    print("\n📋 User starts BUY order (Send THB, Receive MMK)")
    print(f"   Exchange Rate: 1 THB = {order.exchange_rate} MMK")
    
    # Receipt 1
    print("\n📸 User sends FIRST receipt...")
    receipt1 = ReceiptData(
        amount=5000.0,
        bank_name="KBank",
        account_number="123-4-56789-0",
        account_name="Admin",
        confidence_score=0.95,
        matched_bank_id=1
    )
    
    is_match, error = manager.verify_bank_match(receipt1, order.expected_bank_id, admin_banks)
    if is_match:
        order.receipt_file_ids.append("file1")
        order.receipt_amounts.append(receipt1.amount)
        order.receipt_bank_ids.append(receipt1.matched_bank_id)
        order.receipt_count += 1
        order.expected_bank_id = receipt1.matched_bank_id
        order.expected_bank_name, order.expected_account_number = manager.get_bank_details(
            receipt1.matched_bank_id, admin_banks
        )
        order.total_amount = manager.calculate_total(order.receipt_amounts)
        order.thb_amount = order.total_amount
        
        print(f"   ✅ Receipt 1 verified!")
        print(f"   Amount: {receipt1.amount:,.2f} THB")
        print(f"   Bank: {order.expected_bank_name}")
        print(f"   Total: {order.total_amount:,.2f} THB")
    
    # Receipt 2
    print("\n📸 User sends SECOND receipt (same bank)...")
    receipt2 = ReceiptData(
        amount=3000.0,
        bank_name="KBank",
        account_number="123-4-56789-0",
        account_name="Admin",
        confidence_score=0.92,
        matched_bank_id=1
    )
    
    is_match, error = manager.verify_bank_match(receipt2, order.expected_bank_id, admin_banks)
    if is_match:
        order.receipt_file_ids.append("file2")
        order.receipt_amounts.append(receipt2.amount)
        order.receipt_bank_ids.append(receipt2.matched_bank_id)
        order.receipt_count += 1
        order.total_amount = manager.calculate_total(order.receipt_amounts)
        order.thb_amount = order.total_amount
        
        print(f"   ✅ Receipt 2 verified!")
        print(f"   Amount: {receipt2.amount:,.2f} THB")
        print(f"   Total: {order.total_amount:,.2f} THB")
    
    # Receipt 3 - Wrong bank
    print("\n📸 User sends THIRD receipt (WRONG bank)...")
    receipt3 = ReceiptData(
        amount=2000.0,
        bank_name="Bangkok Bank",
        account_number="987-6-54321-0",
        account_name="Admin",
        confidence_score=0.90,
        matched_bank_id=2
    )
    
    is_match, error = manager.verify_bank_match(receipt3, order.expected_bank_id, admin_banks)
    if not is_match:
        print(f"   ❌ Receipt 3 REJECTED!")
        print(f"   Reason: Bank mismatch")
        print(f"   Expected: {order.expected_bank_name}")
        print(f"   Received: Bangkok Bank")
    
    # User retries with correct bank
    print("\n📸 User retries with CORRECT bank...")
    receipt3_retry = ReceiptData(
        amount=2000.0,
        bank_name="KBank",
        account_number="123-4-56789-0",
        account_name="Admin",
        confidence_score=0.93,
        matched_bank_id=1
    )
    
    is_match, error = manager.verify_bank_match(receipt3_retry, order.expected_bank_id, admin_banks)
    if is_match:
        order.receipt_file_ids.append("file3")
        order.receipt_amounts.append(receipt3_retry.amount)
        order.receipt_bank_ids.append(receipt3_retry.matched_bank_id)
        order.receipt_count += 1
        order.total_amount = manager.calculate_total(order.receipt_amounts)
        order.thb_amount = order.total_amount
        
        print(f"   ✅ Receipt 3 verified!")
        print(f"   Amount: {receipt3_retry.amount:,.2f} THB")
        print(f"   Total: {order.total_amount:,.2f} THB")
    
    # Final summary
    print("\n" + "=" * 80)
    print("📋 FINAL ORDER SUMMARY")
    print("=" * 80)
    print(f"Order Type: Buy MMK (Send THB)")
    print(f"Receipts: {order.receipt_count}")
    print(f"Individual Amounts: {[f'{a:,.2f}' for a in order.receipt_amounts]}")
    print(f"Total Amount: {order.total_amount:,.2f} THB")
    print(f"Bank: {order.expected_bank_name}")
    print(f"Account: {order.expected_account_number}")
    print(f"Expected MMK: {order.total_amount * order.exchange_rate:,.2f} MMK")
    print("=" * 80)
    
    # Validate final state
    assert order.receipt_count == 3, "Receipt count incorrect"
    assert order.total_amount == 10000.0, "Total amount incorrect"
    assert len(order.receipt_file_ids) == 3, "File IDs count incorrect"
    assert all(bid == 1 for bid in order.receipt_bank_ids), "Bank IDs should all be 1"
    
    print("\n✅ Flow simulation passed!")
    print("=" * 80)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("MULTIPLE RECEIPT FLOW - TEST SUITE")
    print("=" * 80)
    
    try:
        test_receipt_manager()
        test_order_data_model()
        test_flow_simulation()
        
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\nThe multiple receipt flow implementation is working correctly!")
        print("Ready for integration testing with the bot.")
        print("=" * 80 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
