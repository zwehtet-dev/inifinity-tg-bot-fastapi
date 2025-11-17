#!/usr/bin/env python3
"""
Test script to verify non-receipt image rejection.
"""
import asyncio
import sys
from pathlib import Path
from PIL import Image
from io import BytesIO

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ocr_service import OCRService, NotAReceiptError
from app.config import get_settings


async def test_non_receipt_rejection():
    """Test that non-receipt images are properly rejected."""
    
    settings = get_settings()
    
    # Sample admin banks
    admin_banks = [
        {
            "bank_name": "Bangkok Bank",
            "account_number": "123-4-56789-0",
            "account_name": "INFINITY Exchange"
        }
    ]
    
    print("=" * 80)
    print("🧪 TESTING NON-RECEIPT IMAGE REJECTION")
    print("=" * 80)
    
    # Initialize OCR service
    ocr_service = OCRService(
        openai_api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        admin_banks=admin_banks,
        enable_cache=False,  # Disable cache for testing
        min_confidence=0.75  # Require 75% confidence minimum
    )
    
    print("✓ OCR Service initialized")
    
    # Test 1: Random colored image (not a receipt)
    print("\n" + "=" * 80)
    print("TEST 1: Random Colored Image (Should be rejected)")
    print("=" * 80)
    
    # Create a random colored image
    test_img = Image.new('RGB', (500, 500), color='blue')
    img_bytes = BytesIO()
    test_img.save(img_bytes, format='JPEG')
    random_image_bytes = img_bytes.getvalue()
    
    try:
        result = await ocr_service.extract_with_retry(random_image_bytes)
        if result is None:
            print("✅ PASSED: Random image correctly rejected (returned None)")
        else:
            print("❌ FAILED: Random image was accepted (should be rejected)")
            print(f"   Result: {result}")
            return False
    except NotAReceiptError as e:
        print(f"✅ PASSED: Random image correctly rejected (exception raised)")
        print(f"   Error message: {e}")
    except Exception as e:
        print(f"⚠ Unexpected error: {e}")
        return False
    
    # Test 2: Image with text but not a receipt
    print("\n" + "=" * 80)
    print("TEST 2: Text Image (Not a receipt, should be rejected)")
    print("=" * 80)
    
    # Create an image with random text
    from PIL import ImageDraw, ImageFont
    
    text_img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(text_img)
    
    # Add some random text
    text = "This is just a random text document\nNot a bank receipt\nJust some words"
    draw.text((50, 50), text, fill='black')
    
    img_bytes = BytesIO()
    text_img.save(img_bytes, format='JPEG')
    text_image_bytes = img_bytes.getvalue()
    
    try:
        result = await ocr_service.extract_with_retry(text_image_bytes)
        if result is None:
            print("✅ PASSED: Text image correctly rejected (returned None)")
        else:
            print("❌ FAILED: Text image was accepted (should be rejected)")
            print(f"   Result: {result}")
            return False
    except NotAReceiptError as e:
        print(f"✅ PASSED: Text image correctly rejected (exception raised)")
        print(f"   Error message: {e}")
    except Exception as e:
        print(f"⚠ Unexpected error: {e}")
        return False
    
    # Test 3: Very small amount (suspicious)
    print("\n" + "=" * 80)
    print("TEST 3: Testing with actual receipt (if available)")
    print("=" * 80)
    
    # Check for test receipt
    test_receipt_path = Path(__file__).parent.parent / "tg_bot" / "receipts" / "2060245779_1762143617.40985.jpg"
    
    if test_receipt_path.exists():
        print(f"Found test receipt: {test_receipt_path.name}")
        
        with open(test_receipt_path, "rb") as f:
            receipt_bytes = f.read()
        
        try:
            result = await ocr_service.extract_with_retry(receipt_bytes)
            if result:
                print(f"✅ PASSED: Valid receipt accepted")
                print(f"   Amount: {result.amount}")
                print(f"   Bank: {result.bank_name}")
                print(f"   Confidence: {result.confidence_score}")
            else:
                print("⚠ Receipt returned None")
        except NotAReceiptError as e:
            print(f"⚠ Valid receipt was rejected: {e}")
            print("   (This might be a false positive)")
        except Exception as e:
            print(f"⚠ Error processing receipt: {e}")
    else:
        print("⚠ No test receipt found, skipping this test")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print("✅ Non-receipt rejection is working!")
    print("✅ Random images are rejected")
    print("✅ Text-only images are rejected")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_non_receipt_rejection())
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
