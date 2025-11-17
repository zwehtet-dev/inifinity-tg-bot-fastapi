#!/usr/bin/env python3
"""
Test script to verify configuration and logging modules work correctly.
"""
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    
    try:
        from app import config
        print("  ✓ app.config imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import app.config: {e}")
        return False
    
    try:
        from app import logging_config
        print("  ✓ app.logging_config imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import app.logging_config: {e}")
        return False
    
    try:
        from app import main
        print("  ✓ app.main imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import app.main: {e}")
        return False
    
    return True


def test_logging_setup():
    """Test logging configuration."""
    print("\nTesting logging setup...")
    
    try:
        from app.logging_config import setup_logging, get_logger
        
        # Setup logging in development mode
        setup_logging(log_level="INFO", use_json=False)
        print("  ✓ Logging setup successful (development mode)")
        
        # Get a logger
        logger = get_logger(__name__)
        logger.info("Test log message")
        print("  ✓ Logger created and test message logged")
        
        return True
    except Exception as e:
        print(f"  ✗ Logging test failed: {e}")
        return False


def test_config_structure():
    """Test configuration structure."""
    print("\nTesting configuration structure...")
    
    try:
        from app.config import Settings
        
        # Check that Settings class exists and has required fields
        required_fields = [
            'telegram_bot_token',
            'telegram_webhook_secret',
            'backend_api_url',
            'openai_api_key',
            'admin_group_id',
        ]
        
        for field in required_fields:
            if hasattr(Settings, 'model_fields') and field in Settings.model_fields:
                print(f"  ✓ Settings has field: {field}")
            else:
                print(f"  ✗ Settings missing field: {field}")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Configuration and Logging Module Tests")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Logging Setup", test_logging_setup),
        ("Configuration Structure", test_config_structure),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests passed!")
        print("\nThe configuration and logging modules are working correctly.")
        return 0
    else:
        print("\n✗ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
