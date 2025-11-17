"""
Test script for BackendClient functionality.

This script tests the backend client's ability to communicate with the Flask backend.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.backend_client import BackendClient


async def test_backend_client():
    """Test basic backend client functionality."""
    
    print("=" * 60)
    print("Testing BackendClient")
    print("=" * 60)
    
    # Initialize client with test values
    backend_url = os.getenv("BACKEND_API_URL", "http://localhost:5000")
    backend_secret = os.getenv("BACKEND_WEBHOOK_SECRET", "test-secret")
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    print(f"\nBackend URL: {backend_url}")
    print(f"Backend Secret: {'*' * len(backend_secret)}")
    print(f"Bot Token: {'*' * 10 if bot_token else 'Not set'}")
    
    client = BackendClient(
        backend_url=backend_url,
        backend_secret=backend_secret,
        bot_token=bot_token
    )
    
    try:
        # Test 1: Fetch settings
        print("\n" + "-" * 60)
        print("Test 1: Fetch Settings")
        print("-" * 60)
        
        settings = await client.fetch_settings()
        if settings:
            print("✅ Settings fetched successfully:")
            print(f"   Buy Rate: {settings.get('buy', 'N/A')}")
            print(f"   Sell Rate: {settings.get('sell', 'N/A')}")
            print(f"   Maintenance Mode: {settings.get('maintenance_mode', 'N/A')}")
            print(f"   Auth Required: {settings.get('auth_feature', 'N/A')}")
        else:
            print("❌ Failed to fetch settings")
        
        # Test 2: Fetch Myanmar banks
        print("\n" + "-" * 60)
        print("Test 2: Fetch Myanmar Banks")
        print("-" * 60)
        
        myanmar_banks = await client.fetch_bank_accounts("myanmar")
        if myanmar_banks:
            print(f"✅ Fetched {len(myanmar_banks)} Myanmar banks:")
            for bank in myanmar_banks[:3]:  # Show first 3
                print(f"   - {bank.get('bank_name', 'N/A')}: {bank.get('account_number', 'N/A')}")
            if len(myanmar_banks) > 3:
                print(f"   ... and {len(myanmar_banks) - 3} more")
        else:
            print("❌ Failed to fetch Myanmar banks or no banks found")
        
        # Test 3: Fetch Thai banks
        print("\n" + "-" * 60)
        print("Test 3: Fetch Thai Banks")
        print("-" * 60)
        
        thai_banks = await client.fetch_bank_accounts("thai")
        if thai_banks:
            print(f"✅ Fetched {len(thai_banks)} Thai banks:")
            for bank in thai_banks[:3]:  # Show first 3
                print(f"   - {bank.get('bank_name', 'N/A')}: {bank.get('account_number', 'N/A')}")
            if len(thai_banks) > 3:
                print(f"   ... and {len(thai_banks) - 3} more")
        else:
            print("❌ Failed to fetch Thai banks or no banks found")
        
        # Test 4: Check pending order (with test chat_id)
        print("\n" + "-" * 60)
        print("Test 4: Check Pending Order")
        print("-" * 60)
        
        test_chat_id = 123456789
        has_pending = await client.check_pending_order(test_chat_id)
        print(f"✅ Pending order check completed for chat_id {test_chat_id}")
        print(f"   Has pending order: {has_pending}")
        
        # Test 5: Poll messages (with test values)
        print("\n" + "-" * 60)
        print("Test 5: Poll Messages")
        print("-" * 60)
        
        test_telegram_id = "123456789"
        messages = await client.poll_messages(test_telegram_id, test_chat_id)
        print(f"✅ Message polling completed for telegram_id {test_telegram_id}")
        print(f"   Retrieved {len(messages)} messages")
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        await client.close()
        print("\n✅ Client closed")


if __name__ == "__main__":
    print("\n🚀 Starting BackendClient tests...\n")
    
    # Check if required environment variables are set
    if not os.getenv("BACKEND_API_URL"):
        print("⚠️  Warning: BACKEND_API_URL not set, using default http://localhost:5000")
    
    if not os.getenv("BACKEND_WEBHOOK_SECRET"):
        print("⚠️  Warning: BACKEND_WEBHOOK_SECRET not set, using test value")
    
    print()
    
    # Run tests
    asyncio.run(test_backend_client())
