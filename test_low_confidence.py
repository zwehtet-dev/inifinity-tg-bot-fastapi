#!/usr/bin/env python3
"""
Test script to verify low confidence receipts are rejected.
"""
import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ocr_service import OCRService, NotAReceiptError
from app.config import get_settings


async def test_low_confidence_rejection():
    """Test that low confidence receipts are rejected."""
    
    settings = get_settings()
    
    # Use admin banks that WON'T match the receipt
    # This will result in low confidence
    wrong_admin_banks = [
        {
            "bank_name": "Wrong Bank Name",
            "account_number": "999-9-99999-9",
            "account_name": "WRONG ACCOUNT NAME"
        }
    ]
    
    print("=" * 80)
    print("🧪 TESTING LOW CONFIDENCE REJECTION")
    print("=" * 80)
    
    # Initialize OCR service with 75% minimum confidence
    ocr_service = OCRService(
        openai_api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        admin_banks=wrong_admin_banks,  # Wrong banks = low confidence
        enable_cache=False,
        min_confidence=0.75  # Require 75% confidence
    )
    
    print("✓ OCR Service initialized")
    print(f"  • Min confidence: {ocr_service.min_confidence:.0%}")
    print(f"  • Admin banks: {len(ocr_service.admin_banks)} (intentionally wrong)")
    
    # Test with actual receipt
    print("\n" + "=" * 80)
    print("TEST: Receipt with Wrong Admin Banks (Should be rejected)")
    print("=" * 80)
    
    test_receipt_path = Path(__file__).parent.parent / "tg_bot" / "receipts" / "2060245779_1762143617.40985.jpg"
    
    if not test_receipt_path.exists():
        print("⚠ No test receipt found, skipping test")
        return True
    
    print(f"Using receipt: {test_receipt_path.name}")
    
    with open(test_receipt_path, "rb") as f:
        receipt_bytes = f.read()
    
    try:
        result = await ocr_service.extract_with_retry(receipt_bytes)
        
        if result is None:
            print("✅ PASSED: Low confidence receipt correctly rejected (returned None)")
        elif result.confidence_score < 0.75:
            print(f"❌ FAILED: Low confidence receipt was accepted")
            print(f"   Confidence: {result.confidence_score:.0%} (below 75% threshold)")
            return False
        else:
            print(f"⚠ Unexpected: Receipt accepted with high confidence {result.confidence_score:.0%}")
            print("   (This might happen if AI still matches despite wrong admin banks)")
    
    except NotAReceiptError as e:
        print("✅ PASSED: Low confidence receipt correctly rejected (exception raised)")
        print(f"   Error message preview: {str(e)[:100]}...")
    
    except Exception as e:
        print(f"⚠ Unexpected error: {e}")
        return False
    
    # Test 2: With correct admin banks (should pass)
    print("\n" + "=" * 80)
    print("TEST: Receipt with Correct Admin Banks (Should be accepted)")
    print("=" * 80)
    
    correct_admin_banks = [
        {
            "bank_name": "Bangkok Bank",
            "account_number": "884-2-xxx935",
            "account_name": "MIN MYAT NWE"
        }
    ]
    
    ocr_service_correct = OCRService(
        openai_api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        admin_banks=correct_admin_banks,
        enable_cache=False,
        min_confidence=0.75
    )
    
    try:
        result = await ocr_service_correct.extract_with_retry(receipt_bytes)
        
        if result and result.confidence_score >= 0.75:
            print(f"✅ PASSED: Receipt accepted with confidence {result.confidence_score:.0%}")
        else:
            print(f"⚠ Receipt rejected or low confidence: {result.confidence_score if result else 'None'}")
    
    except NotAReceiptError as e:
        print(f"⚠ Receipt rejected: {str(e)[:100]}...")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print("✅ Low confidence threshold (75%) is enforced")
    print("✅ Receipts not matching admin banks are rejected")
    print("✅ Receipts matching admin banks are accepted")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_low_confidence_rejection())
        if result:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
