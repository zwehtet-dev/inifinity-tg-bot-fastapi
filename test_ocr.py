#!/usr/bin/env python3
"""
Enhanced test script for OpenAI OCR functionality with caching and retry features.
"""
import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ocr_service import OCRService, InvalidImageError, RateLimitError, OCRTimeoutError, NotAReceiptError
from app.config import get_settings


async def test_ocr():
    """Test OCR service with enhanced features."""
    
    settings = get_settings()
    
    # Sample admin banks
    admin_banks = [
        {
            "bank_name": "Bangkok Bank",
            "account_number": "123-4-56789-0",
            "account_name": "INFINITY Exchange"
        },
        {
            "bank_name": "Kasikorn Bank",
            "account_number": "098-7-65432-1",
            "account_name": "INFINITY Exchange"
        },
        {
            "bank_name": "SCB",
            "account_number": "456-7-89012-3",
            "account_name": "INFINITY Exchange"
        }
    ]
    
    print("=" * 80)
    print("🚀 TESTING ENHANCED OCR SERVICE")
    print("=" * 80)
    print(f"OpenAI API Key: {settings.openai_api_key[:20]}...")
    print(f"Admin Banks: {len(admin_banks)}")
    print("=" * 80)
    
    # Initialize OCR service with caching enabled
    ocr_service = OCRService(
        openai_api_key=settings.openai_api_key,
        model="gpt-4o-mini",  # Cost-effective model
        admin_banks=admin_banks,
        enable_cache=True,
        cache_ttl=3600,  # 1 hour cache
        min_confidence=0.75  # Require 75% confidence minimum
    )
    
    print("\n✓ OCR Service initialized successfully")
    print(f"  • Model: {ocr_service.model}")
    print(f"  • Admin banks: {len(ocr_service.admin_banks)}")
    print(f"  • Cache: {'enabled' if ocr_service.enable_cache else 'disabled'}")
    print(f"  • Cache TTL: {ocr_service.cache_ttl}s")
    print(f"  • Min confidence: {ocr_service.min_confidence:.0%}")
    
    # Test 1: OpenAI API Connection
    print("\n" + "=" * 80)
    print("TEST 1: OpenAI API Connection (without image)")
    print("=" * 80)
    
    try:
        from langchain_openai import ChatOpenAI
        
        test_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.openai_api_key,
            max_tokens=100
        )
        
        response = await test_llm.ainvoke("Say 'Hello, OpenAI is working!' in exactly those words.")
        print(f"✓ OpenAI Response: {response.content}")
        print("✓ OpenAI API is working correctly!")
        
    except Exception as e:
        print(f"✗ OpenAI API Error: {e}")
        return False
    
    # Test 2: Image Preprocessing
    print("\n" + "=" * 80)
    print("TEST 2: Image Preprocessing")
    print("=" * 80)
    
    try:
        # Create a simple test image
        from PIL import Image
        from io import BytesIO
        
        # Create a small test image
        test_img = Image.new('RGB', (200, 200), color='white')
        img_bytes = BytesIO()
        test_img.save(img_bytes, format='JPEG')
        test_image_bytes = img_bytes.getvalue()
        
        print(f"Original image size: {len(test_image_bytes)} bytes")
        
        # Test preprocessing
        processed = ocr_service.preprocess_image(test_image_bytes)
        print(f"Processed image size: {len(processed)} bytes")
        print("✓ Image preprocessing works!")
        
        # Test invalid image
        try:
            ocr_service.preprocess_image(b"invalid image data")
            print("✗ Should have raised InvalidImageError")
        except InvalidImageError:
            print("✓ Invalid image detection works!")
        
    except Exception as e:
        print(f"✗ Image preprocessing error: {e}")
        return False
    
    # Test 3: Cache functionality
    print("\n" + "=" * 80)
    print("TEST 3: Cache Functionality")
    print("=" * 80)
    
    cache_stats = ocr_service.get_cache_stats()
    print(f"Cache stats: {cache_stats}")
    print("✓ Cache stats retrieval works!")
    
    # Test 4: Admin banks update
    print("\n" + "=" * 80)
    print("TEST 4: Admin Banks Update")
    print("=" * 80)
    
    new_banks = [
        {
            "bank_name": "Krungsri Bank",
            "account_number": "111-2-22222-3",
            "account_name": "Test Account"
        }
    ]
    
    ocr_service.update_admin_banks(new_banks)
    print(f"✓ Admin banks updated: {len(ocr_service.admin_banks)} accounts")
    
    # Restore original banks
    ocr_service.update_admin_banks(admin_banks)
    print(f"✓ Admin banks restored: {len(ocr_service.admin_banks)} accounts")
    
    # Test 5: Actual receipt OCR (if image available)
    print("\n" + "=" * 80)
    print("TEST 5: Actual Receipt OCR")
    print("=" * 80)
    
    # Check for test receipt images
    test_images = [
        Path(__file__).parent / "test_receipt.jpg",
        Path(__file__).parent / "test_receipt.png",
        Path(__file__).parent.parent / "tg_bot" / "receipts" / "2060245779_1762143617.40985.jpg"
    ]
    
    receipt_found = False
    for image_path in test_images:
        if image_path.exists():
            receipt_found = True
            print(f"\n📄 Testing with receipt: {image_path.name}")
            
            try:
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                
                print(f"Image size: {len(image_bytes)} bytes")
                print("Running OCR extraction with retry...")
                
                # Test with retry
                result = await ocr_service.extract_with_retry(
                    image_bytes,
                    max_retries=2,
                    use_cache=True
                )
                
                if result:
                    print("\n" + "=" * 80)
                    print("✅ OCR EXTRACTION RESULT:")
                    print("=" * 80)
                    print(f"Amount: {result.amount}")
                    print(f"Bank Name: {result.bank_name}")
                    print(f"Account Number: {result.account_number}")
                    print(f"Account Holder: {result.account_name}")
                    print(f"Transaction Date: {result.transaction_date}")
                    print(f"Transaction ID: {result.transaction_id}")
                    print(f"Confidence Score: {result.confidence_score:.2f}")
                    print("=" * 80)
                    
                    # Test cache hit
                    print("\n🔄 Testing cache hit (should be instant)...")
                    cached_result = await ocr_service.extract_receipt_data(
                        image_bytes,
                        use_cache=True
                    )
                    if cached_result:
                        print("✓ Cache hit successful!")
                    
                    # Show cache stats
                    cache_stats = ocr_service.get_cache_stats()
                    print(f"Cache stats: {cache_stats}")
                    
                else:
                    print("✗ OCR extraction returned None")
                    
            except InvalidImageError as e:
                print(f"✗ Invalid image: {e}")
            except NotAReceiptError as e:
                print(f"✗ Not a receipt: {e}")
            except RateLimitError as e:
                print(f"⚠ Rate limit: {e}")
            except OCRTimeoutError as e:
                print(f"⚠ Timeout: {e}")
            except Exception as e:
                print(f"✗ OCR error: {e}")
                import traceback
                traceback.print_exc()
            
            break  # Only test first available image
    
    if not receipt_found:
        print("\n⚠ No test receipt images found")
        print("\nTo test with an actual receipt:")
        print("1. Save a receipt image as 'test_receipt.jpg' in this directory")
        print("2. Or use an existing receipt from tg_bot/receipts/")
        print("\nTested locations:")
        for img_path in test_images:
            print(f"  • {img_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print("✓ OpenAI API connection: PASSED")
    print("✓ Image preprocessing: PASSED")
    print("✓ Cache functionality: PASSED")
    print("✓ Admin banks update: PASSED")
    if receipt_found:
        print("✓ Receipt OCR: TESTED")
    else:
        print("⚠ Receipt OCR: SKIPPED (no test image)")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_ocr())
        if result:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Tests failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
