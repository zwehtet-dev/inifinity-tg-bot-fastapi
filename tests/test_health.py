"""Basic health check tests for the application."""

import pytest


def test_imports():
    """Test that core modules can be imported."""
    try:
        from app import config
        from app import main
        assert config is not None
        assert main is not None
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")


def test_config_validation():
    """Test that configuration validation works."""
    from app.config import Settings
    
    # This should work with environment variables set in CI
    settings = Settings()
    assert settings.telegram_bot_token is not None
    assert settings.backend_api_url is not None
    assert settings.environment in ["development", "staging", "production", "test"]


@pytest.mark.asyncio
async def test_app_creation():
    """Test that FastAPI app can be created."""
    from app.main import app
    
    assert app is not None
    assert hasattr(app, 'routes')
