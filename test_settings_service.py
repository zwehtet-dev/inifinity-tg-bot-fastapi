"""
Test script for SettingsService functionality.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.settings_service import SettingsService
from app.services.backend_client import BackendClient


async def test_settings_service():
    """Test SettingsService basic functionality."""
    print("Testing SettingsService...")
    
    # Create mock backend client
    mock_backend_client = MagicMock(spec=BackendClient)
    
    # Mock fetch_settings response
    mock_backend_client.fetch_settings = AsyncMock(return_value={
        "buy": 0.0036,
        "sell": 0.0035,
        "maintenance_mode": False,
        "auth_feature": False
    })
    
    # Mock fetch_bank_accounts response
    mock_backend_client.fetch_bank_accounts = AsyncMock(return_value=[
        {
            "bank_name": "KBZ Bank",
            "account_number": "1234567890",
            "account_name": "Test Account",
            "qr_image": "path/to/qr.jpg"
        },
        {
            "bank_name": "CB Bank",
            "account_number": "0987654321",
            "account_name": "Another Account",
            "qr_image": None
        }
    ])
    
    # Create settings service
    settings_service = SettingsService(
        backend_client=mock_backend_client,
        refresh_interval_minutes=1
    )
    
    print("✓ SettingsService created")
    
    # Test fetch_settings
    success = await settings_service.fetch_settings()
    assert success, "fetch_settings should return True"
    assert settings_service.buy_rate == 0.0036, f"Expected buy_rate 0.0036, got {settings_service.buy_rate}"
    assert settings_service.sell_rate == 0.0035, f"Expected sell_rate 0.0035, got {settings_service.sell_rate}"
    assert not settings_service.maintenance_mode, "maintenance_mode should be False"
    assert not settings_service.auth_required, "auth_required should be False"
    print("✓ fetch_settings works correctly")
    
    # Test fetch_bank_accounts
    success = await settings_service.fetch_bank_accounts("myanmar")
    assert success, "fetch_bank_accounts should return True"
    myanmar_banks = settings_service.get_myanmar_banks()
    assert len(myanmar_banks) == 2, f"Expected 2 Myanmar banks, got {len(myanmar_banks)}"
    assert "KBZ Bank" in myanmar_banks, "KBZ Bank should be in Myanmar banks"
    assert "CB Bank" in myanmar_banks, "CB Bank should be in Myanmar banks"
    print("✓ fetch_bank_accounts works correctly")
    
    # Test get_myanmar_bank_list
    bank_list = settings_service.get_myanmar_bank_list()
    assert len(bank_list) == 2, f"Expected 2 banks in list, got {len(bank_list)}"
    assert bank_list[0]["bank_name"] in ["KBZ Bank", "CB Bank"], "Bank name should be KBZ Bank or CB Bank"
    print("✓ get_myanmar_bank_list works correctly")
    
    # Test get_bank_by_name
    kbz_bank = settings_service.get_bank_by_name("KBZ Bank", "myanmar")
    assert kbz_bank is not None, "KBZ Bank should be found"
    assert kbz_bank["account_number"] == "1234567890", "Account number should match"
    print("✓ get_bank_by_name works correctly")
    
    # Test refresh_all
    success = await settings_service.refresh_all()
    assert success, "refresh_all should return True"
    print("✓ refresh_all works correctly")
    
    # Test get_status
    status = settings_service.get_status()
    assert "buy_rate" in status, "Status should contain buy_rate"
    assert "myanmar_banks_count" in status, "Status should contain myanmar_banks_count"
    assert status["myanmar_banks_count"] == 2, f"Expected 2 Myanmar banks in status, got {status['myanmar_banks_count']}"
    print("✓ get_status works correctly")
    
    # Test maintenance mode
    mock_backend_client.fetch_settings = AsyncMock(return_value={
        "buy": 0.0036,
        "sell": 0.0035,
        "maintenance_mode": True,
        "auth_feature": False
    })
    await settings_service.fetch_settings()
    assert settings_service.maintenance_mode, "maintenance_mode should be True"
    print("✓ maintenance_mode check works correctly")
    
    # Test auth_required
    mock_backend_client.fetch_settings = AsyncMock(return_value={
        "buy": 0.0036,
        "sell": 0.0035,
        "maintenance_mode": False,
        "auth_feature": True
    })
    await settings_service.fetch_settings()
    assert settings_service.auth_required, "auth_required should be True"
    print("✓ auth_required check works correctly")
    
    print("\n✅ All SettingsService tests passed!")


if __name__ == "__main__":
    asyncio.run(test_settings_service())
