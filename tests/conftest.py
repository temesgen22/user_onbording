"""
Pytest configuration and fixtures for the User Onboarding Integration API tests.
"""

import os
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

# Set test environment variables BEFORE importing app modules
os.environ.setdefault("OKTA_ORG_URL", "https://test-org.okta.com")
os.environ.setdefault("OKTA_API_TOKEN", "test-token-12345")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("LOG_FORMAT", "text")

from app.main import create_app
from app.store import InMemoryUserStore, RedisUserStore
from app.config import Settings
from app.security import generate_webhook_signature
import json
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="function")
def test_settings():
    """Create test settings with mock Okta credentials."""
    return Settings(
        OKTA_ORG_URL="https://test-org.okta.com",
        OKTA_API_TOKEN="test-token-12345",
        API_KEY=None,  # Optional - not configured for tests
        LOG_LEVEL="DEBUG",
        LOG_FORMAT="text",
        API_TIMEOUT_SECONDS=10,
        STORAGE_BACKEND="memory"
    )


@pytest.fixture(scope="function")
def test_settings_redis():
    """Create test settings with Redis backend."""
    return Settings(
        OKTA_ORG_URL="https://test-org.okta.com",
        OKTA_API_TOKEN="test-token-12345",
        API_KEY=None,
        LOG_LEVEL="DEBUG",
        LOG_FORMAT="text",
        API_TIMEOUT_SECONDS=10,
        STORAGE_BACKEND="redis",
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=0,
        REDIS_PASSWORD=None,
        REDIS_KEY_PREFIX="test:",
        REDIS_CONNECTION_TIMEOUT=5
    )


@pytest.fixture(scope="function")
def app(test_settings):
    """Create a test FastAPI application with mocked settings."""
    with patch("app.main.init_settings", return_value=test_settings):
        with patch("app.main.get_settings", return_value=test_settings):
            with patch("app.config.get_settings", return_value=test_settings):
                with patch("app.middleware.get_settings", return_value=test_settings):
                    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def user_store():
    """Create a fresh in-memory user store for each test."""
    return InMemoryUserStore()


@pytest.fixture
def mock_redis_client():
    """Create a mocked Redis client for testing."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def redis_user_store(mock_redis_client):
    """Create a RedisUserStore instance with mocked Redis client."""
    with patch('redis.Redis', return_value=mock_redis_client):
        store = RedisUserStore(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            key_prefix="test:",
            connection_timeout=5
        )
        return store


@pytest.fixture
def sample_hr_user():
    """Sample HR user data for testing."""
    return {
        "employee_id": "12345",
        "first_name": "Jane",
        "last_name": "Doe",
        "preferred_name": "Janey",
        "email": "test.user@example.com",
        "title": "Software Engineer",
        "department": "Engineering",
        "manager_email": "john.smith@example.com",
        "location": "Stockholm",
        "office": "HQ",
        "employment_type": "Full-Time",
        "employment_status": "Active",
        "start_date": "2024-01-15",
        "termination_date": None,
        "cost_center": "ENG-SE-001",
        "employee_type": "Regular",
        "work_phone": "+46 8 123 456 78",
        "mobile_phone": "+46 70 987 6543",
        "country": "Sweden",
        "time_zone": "Europe/Stockholm",
        "legal_entity": "Epidemic Sound AB",
        "division": "Product & Engineering"
    }


@pytest.fixture
def sample_okta_user():
    """Sample Okta user data for testing."""
    return {
        "profile": {
            "login": "test.user@example.com",
            "firstName": "Jane",
            "lastName": "Doe",
            "email": "test.user@example.com",
            "employeeNumber": None
        },
        "groups": [
            "Everyone",
            "Engineering",
            "Full-Time Employees"
        ],
        "applications": [
            "Google Workspace",
            "Slack",
            "Jira"
        ]
    }


@pytest.fixture
def mock_okta_credentials():
    """Mock Okta credentials for testing."""
    return {
        "OKTA_ORG_URL": "https://test-org.okta.com",
        "OKTA_API_TOKEN": "test-token-12345"
    }


@pytest.fixture
def temp_env_file(mock_okta_credentials):
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        for key, value in mock_okta_credentials.items():
            f.write(f"{key}={value}\n")
        f.write("LOG_LEVEL=DEBUG\n")
        f.write("LOG_FILE=test.log\n")
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    try:
        os.unlink(temp_file)
    except FileNotFoundError:
        pass


@pytest.fixture(autouse=True)
def cleanup_env():
    """Clean up environment variables after each test."""
    # Store original values
    original_env = {}
    for key in ["OKTA_ORG_URL", "OKTA_API_TOKEN", "LOG_LEVEL", "LOG_FILE"]:
        original_env[key] = os.environ.get(key)
    
    yield
    
    # Restore original values
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
