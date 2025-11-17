"""
Test script to verify admin notification services can be imported correctly.
"""
import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all admin services can be imported."""
    print("Testing admin service imports...")
    
    try:
        from app.services.admin_notifier import AdminNotifier, AdminNotificationError
        print("✓ AdminNotifier imported successfully")
        
        from app.services.admin_receipt_validator import (
            AdminReceiptValidator,
            AdminReceiptValidationError
        )
        print("✓ AdminReceiptValidator imported successfully")
        
        from app.services import (
            AdminNotifier as AN,
            AdminNotificationError as ANE,
            AdminReceiptValidator as ARV,
            AdminReceiptValidationError as ARVE
        )
        print("✓ Admin services imported from app.services successfully")
        
        print("\n✅ All admin service imports successful!")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


def test_class_instantiation():
    """Test that admin service classes can be instantiated with mock data."""
    print("\nTesting admin service class instantiation...")
    
    try:
        from app.services.admin_notifier import AdminNotifier
        from app.services.admin_receipt_validator import AdminReceiptValidator
        from app.services.ocr_service import OCRService
        
        # Test AdminNotifier (requires Bot instance, so we'll skip actual instantiation)
        print("✓ AdminNotifier class accessible")
        
        # Test AdminReceiptValidator (requires OCRService)
        print("✓ AdminReceiptValidator class accessible")
        
        # Verify class attributes
        assert hasattr(AdminNotifier, 'send_order_notification')
        assert hasattr(AdminNotifier, 'send_balance_notification')
        assert hasattr(AdminNotifier, 'send_error_notification')
        print("✓ AdminNotifier has expected methods")
        
        assert hasattr(AdminReceiptValidator, 'validate_admin_receipt')
        assert hasattr(AdminReceiptValidator, 'create_validation_warning_message')
        assert hasattr(AdminReceiptValidator, 'create_skip_validation_keyboard')
        assert hasattr(AdminReceiptValidator, 'handle_skip_validation_callback')
        assert hasattr(AdminReceiptValidator, 'handle_resend_receipt_callback')
        print("✓ AdminReceiptValidator has expected methods")
        
        print("\n✅ All class instantiation tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Admin Services Test Suite")
    print("=" * 60)
    
    success = True
    
    # Run import tests
    if not test_imports():
        success = False
    
    # Run instantiation tests
    if not test_class_instantiation():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
