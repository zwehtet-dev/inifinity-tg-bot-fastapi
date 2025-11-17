"""Simple test for ReceiptManager without full app dependencies."""
import sys
sys.path.insert(0, '.')

# Mock the logger
class MockLogger:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass

# Patch logging before import
import app.services.receipt_manager as rm_module
rm_module.logger = MockLogger()

from app.services.receipt_manager import ReceiptManager

def test_basic_functions():
    """Test basic ReceiptManager functions."""
    print("Testing ReceiptManager...")
    
    manager = ReceiptManager()
    
    # Test calculate_total
    amounts = [5000.0, 3000.0, 2000.0]
    total = manager.calculate_total(amounts)
    assert total == 10000.0, f"Expected 10000.0, got {total}"
    print(f"✓ Calculate total: {amounts} = {total}")
    
    # Test validate_receipt_limit
    is_valid, error = manager.validate_receipt_limit(5, max_receipts=10)
    assert is_valid, "5 receipts should be valid"
    print(f"✓ Receipt limit (5/10): Valid")
    
    is_valid, error = manager.validate_receipt_limit(10, max_receipts=10)
    assert not is_valid, "10 receipts should hit limit"
    print(f"✓ Receipt limit (10/10): Invalid (as expected)")
    
    # Test get_bank_details
    admin_banks = [
        {"id": 1, "bank_name": "KBank", "account_number": "123-456"},
        {"id": 2, "bank_name": "Bangkok Bank", "account_number": "789-012"}
    ]
    
    bank_name, account_number = manager.get_bank_details(1, admin_banks)
    assert bank_name == "KBank", f"Expected KBank, got {bank_name}"
    assert account_number == "123-456", f"Expected 123-456, got {account_number}"
    print(f"✓ Get bank details: ID 1 = {bank_name} - {account_number}")
    
    print("\n✅ All basic tests passed!")

if __name__ == "__main__":
    test_basic_functions()
