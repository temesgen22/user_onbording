
import os
from typing import Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Okta Configuration
    okta_org_url: str = Field(
        ...,
        description="Okta organization URL (e.g., https://trial-123456.okta.com)",
        validation_alias="OKTA_ORG_URL"
    )
    okta_api_token: str = Field(
        ...,
        description="Okta API token (SSWS token)",
        validation_alias="OKTA_API_TOKEN"
    )
    
    # API Security
    api_key: Optional[str] = Field(
        default=None,
        description="API key for webhook authentication (optional)",
        validation_alias="API_KEY"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        validation_alias="LOG_LEVEL"
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log format (json or text)",
        validation_alias="LOG_FORMAT"
    )
    
    # API Configuration
    api_timeout_seconds: int = Field(
        default=10,
        description="Timeout for external API calls in seconds",
        validation_alias="API_TIMEOUT_SECONDS"
    )
    
    # Storage Configuration
    storage_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description="Storage backend to use (memory or redis)",
        validation_alias="STORAGE_BACKEND"
    )
    
    # Redis Configuration (only used when storage_backend='redis')
    redis_host: str = Field(
        default="192.168.1.130",
        description="Redis host address",
        validation_alias="REDIS_HOST"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port",
        validation_alias="REDIS_PORT"
    )
    redis_db: int = Field(
        default=0,
        description="Redis database number",
        validation_alias="REDIS_DB"
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password (optional)",
        validation_alias="REDIS_PASSWORD"
    )
    redis_key_prefix: str = Field(
        default="user_onboarding:",
        description="Prefix for Redis keys",
        validation_alias="REDIS_KEY_PREFIX"
    )
    redis_connection_timeout: int = Field(
        default=5,
        description="Redis connection timeout in seconds",
        validation_alias="REDIS_CONNECTION_TIMEOUT"
    )
    
    @field_validator("okta_org_url")
    @classmethod
    def validate_okta_url(cls, v: str) -> str:
        """Validate and normalize Okta URL."""
        if not v:
            raise ValueError("OKTA_ORG_URL is required")
        # Remove trailing slash
        return v.rstrip("/")
    
    @field_validator("okta_api_token")
    @classmethod
    def validate_okta_token(cls, v: str) -> str:
        """Validate Okta token is not empty."""
        if not v or not v.strip():
            raise ValueError("OKTA_API_TOKEN is required and cannot be empty")
        return v.strip()
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v_upper
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings() -> Settings:
    """Initialize and validate settings at startup."""
    return get_settings()

