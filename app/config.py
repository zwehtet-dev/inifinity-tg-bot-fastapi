"""
Configuration management module for the FastAPI bot engine.
Loads and validates environment variables.
"""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Configuration
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    telegram_webhook_secret: str = Field(
        ..., description="Secret token for webhook validation"
    )
    telegram_webhook_url: str = Field(
        ..., description="Public URL for Telegram webhook"
    )

    # Backend Configuration
    backend_api_url: str = Field(..., description="Backend API base URL")
    backend_webhook_secret: str = Field(
        ..., description="Shared secret for backend webhook authentication"
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key for OCR")

    # Admin Group Configuration
    admin_group_id: int = Field(..., description="Telegram admin group ID")
    buy_topic_id: int = Field(..., description="Buy topic ID in admin group")
    sell_topic_id: int = Field(..., description="Sell topic ID in admin group")
    balance_topic_id: int = Field(..., description="Balance topic ID in admin group")

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="production", description="Environment name")
    host: str = Field(default="0.0.0.0", description="Host to bind to")  # nosec B104
    port: int = Field(default=8000, description="Port to bind to")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the expected values."""
        valid_envs = ["development", "staging", "production", "test"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return v_lower

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.
    Creates the instance on first call.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment.
    Useful for testing or configuration changes.
    """
    global _settings
    _settings = Settings()
    return _settings
