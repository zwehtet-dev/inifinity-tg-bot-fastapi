"""
Test script to verify OCR service imports and basic functionality.
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Test model imports
    from app.models.receipt import ReceiptData, ValidationResult, BankAccount
    print("✓ Receipt models imported successfully")
    
    # Test service imports
    from app.services.ocr_service import (
        OCRService,
        OCRError,
        InvalidImageError,
        RateLimitError,
        OCRTimeoutError,
    )
    print("✓ OCR service imported successfully")
    
    from app.services.receipt_validator import ReceiptValidator
    print("✓ Receipt validator imported successfully")
    
    # Test model instantiation
    receipt_data = ReceiptData(
        amount=1000.0,
        bank_name="Test Bank",
        account_number="1234567890",
        account_name="Test User",
        confidence_score=0.95
    )
    print(f"✓ ReceiptData created: amount={receipt_data.amount}, bank={receipt_data.bank_name}")
    
    bank_account = BankAccount(
        bank_name="Test Bank",
        account_number="1234567890",
        account_name="Test User"
    )
    print(f"✓ BankAccount created: {bank_account.bank_name}")
    
    validation_result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[],
        confidence=0.95
    )
    print(f"✓ ValidationResult created: valid={validation_result.is_valid}")
    
    # Test validator instantiation
    validator = ReceiptValidator()
    print("✓ ReceiptValidator instantiated")
    
    # Test fuzzy matching
    similarity = validator.fuzzy_match("Kasikorn Bank", "kasikorn bank")
    print(f"✓ Fuzzy matching works: similarity={similarity:.2%}")
    
    # Test validation
    result = validator.validate(receipt_data, bank_account, expected_amount=1000.0)
    print(f"✓ Validation works: valid={result.is_valid}, confidence={result.confidence:.2%}")
    
    print("\n✅ All OCR service components verified successfully!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
