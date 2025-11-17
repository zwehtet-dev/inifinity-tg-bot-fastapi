#!/usr/bin/env python3
"""
Validation script to verify project structure and configuration.
This script checks that all necessary files and directories exist.
"""
import os
import sys
from pathlib import Path


def check_directory_structure():
    """Check that all required directories exist."""
    required_dirs = [
        "app",
        "app/handlers",
        "app/services",
        "app/models",
        "app/utils",
    ]
    
    print("Checking directory structure...")
    all_exist = True
    for dir_path in required_dirs:
        full_path = Path(dir_path)
        if full_path.exists() and full_path.is_dir():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path} - MISSING")
            all_exist = False
    
    return all_exist


def check_required_files():
    """Check that all required files exist."""
    required_files = [
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/logging_config.py",
        "app/handlers/__init__.py",
        "app/services/__init__.py",
        "app/models/__init__.py",
        "app/utils/__init__.py",
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "README.md",
    ]
    
    print("\nChecking required files...")
    all_exist = True
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists() and full_path.is_file():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} - MISSING")
            all_exist = False
    
    return all_exist


def check_requirements():
    """Check that requirements.txt has all necessary dependencies."""
    required_packages = [
        "fastapi",
        "uvicorn",
        "python-telegram-bot",
        "langchain",
        "openai",
        "pydantic",
        "httpx",
        "pillow",
        "python-multipart",
        "python-json-logger",
    ]
    
    print("\nChecking requirements.txt...")
    with open("requirements.txt", "r") as f:
        content = f.read().lower()
    
    all_present = True
    for package in required_packages:
        if package.lower() in content:
            print(f"  ✓ {package}")
        else:
            print(f"  ✗ {package} - MISSING")
            all_present = False
    
    return all_present


def check_env_example():
    """Check that .env.example has all required variables."""
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "TELEGRAM_WEBHOOK_URL",
        "BACKEND_API_URL",
        "BACKEND_WEBHOOK_SECRET",
        "OPENAI_API_KEY",
        "ADMIN_GROUP_ID",
        "BUY_TOPIC_ID",
        "SELL_TOPIC_ID",
        "BALANCE_TOPIC_ID",
        "LOG_LEVEL",
        "ENVIRONMENT",
    ]
    
    print("\nChecking .env.example...")
    with open(".env.example", "r") as f:
        content = f.read()
    
    all_present = True
    for var in required_vars:
        if var in content:
            print(f"  ✓ {var}")
        else:
            print(f"  ✗ {var} - MISSING")
            all_present = False
    
    return all_present


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("FastAPI Bot Engine - Project Structure Validation")
    print("=" * 60)
    
    checks = [
        ("Directory Structure", check_directory_structure),
        ("Required Files", check_required_files),
        ("Requirements", check_requirements),
        ("Environment Variables", check_env_example),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error checking {name}: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All validation checks passed!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Copy .env.example to .env and configure")
        print("3. Run the application: uvicorn app.main:app --reload")
        return 0
    else:
        print("\n✗ Some validation checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
