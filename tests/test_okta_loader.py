"""
Tests for Okta loader service (async implementation with httpx).
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
import httpx

from app.services.okta_loader import (
    load_okta_user_by_email,
    _find_okta_user_by_email,
    _get_user_groups,
    _get_user_applications,
    _auth_headers
)
from app.schemas import OktaUser
from app.config import Settings
from app.exceptions import (
    OktaAPIError,
    OktaUserNotFoundError,
    OktaConfigurationError
)


class TestAuthHeaders:
    """Test authorization header generation."""
    
    def test_auth_headers_format(self):
        """Test that auth headers are correctly formatted."""
        token = "test-token-123"
        headers = _auth_headers(token)
        
        assert headers["Authorization"] == "SSWS test-token-123"
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"


class TestFindOktaUserByEmail:
    """Test Okta user search functionality."""
    
    @pytest.mark.asyncio
    async def test_find_user_success(self):
        """Test successful user search by email."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": "user123",
                "profile": {"email": "test@example.com", "firstName": "Test", "lastName": "User"}
            }
        ]
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            user = await _find_okta_user_by_email(
                email="test@example.com",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert user is not None
            assert user["id"] == "user123"
            assert user["profile"]["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_find_user_not_found(self):
        """Test user search when user is not found."""
        mock_response = Mock()
        mock_response.json.return_value = []
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            user = await _find_okta_user_by_email(
                email="notfound@example.com",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert user is None
    
    @pytest.mark.asyncio
    async def test_find_user_http_error(self):
        """Test user search when API returns HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 401
        
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Unauthorized",
            request=Mock(),
            response=mock_response
        ))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(OktaAPIError, match="Okta API error: 401"):
                await _find_okta_user_by_email(
                    email="test@example.com",
                    base_url="https://test.okta.com",
                    token="token123",
                    timeout=10
                )
    
    @pytest.mark.asyncio
    async def test_find_user_timeout(self):
        """Test user search timeout handling."""
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(OktaAPIError, match="Okta API timeout"):
                await _find_okta_user_by_email(
                    email="test@example.com",
                    base_url="https://test.okta.com",
                    token="token123",
                    timeout=10
                )
    
    @pytest.mark.asyncio
    async def test_find_user_request_error(self):
        """Test user search network error handling."""
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.RequestError("Network error"))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(OktaAPIError, match="Okta API request failed"):
                await _find_okta_user_by_email(
                    email="test@example.com",
                    base_url="https://test.okta.com",
                    token="token123",
                    timeout=10
                )


class TestGetUserGroups:
    """Test Okta groups retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_groups_success(self):
        """Test successful groups retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"profile": {"name": "Engineering"}},
            {"profile": {"name": "Everyone"}}
        ]
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            groups = await _get_user_groups(
                user_id="user123",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert "Engineering" in groups
            assert "Everyone" in groups
            assert len(groups) == 2
    
    @pytest.mark.asyncio
    async def test_get_groups_http_error_returns_empty(self):
        """Test that HTTP errors return empty list instead of raising."""
        mock_response = Mock()
        mock_response.status_code = 500
        
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Server error",
            request=Mock(),
            response=mock_response
        ))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            groups = await _get_user_groups(
                user_id="user123",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert groups == []
    
    @pytest.mark.asyncio
    async def test_get_groups_timeout_returns_empty(self):
        """Test that timeout returns empty list."""
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            groups = await _get_user_groups(
                user_id="user123",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert groups == []


class TestGetUserApplications:
    """Test Okta applications retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_applications_success(self):
        """Test successful applications retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {"label": "Google Workspace"},
            {"label": "Slack"},
            {"label": "Jira"}
        ]
        
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            apps = await _get_user_applications(
                user_id="user123",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert "Google Workspace" in apps
            assert "Slack" in apps
            assert "Jira" in apps
            assert len(apps) == 3
    
    @pytest.mark.asyncio
    async def test_get_applications_http_error_returns_empty(self):
        """Test that HTTP errors return empty list."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        mock_client = AsyncMock()
        mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Not found",
            request=Mock(),
            response=mock_response
        ))
        mock_client.__aenter__.return_value.get = mock_get
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            apps = await _get_user_applications(
                user_id="user123",
                base_url="https://test.okta.com",
                token="token123",
                timeout=10
            )
            
            assert apps == []


class TestLoadOktaUserByEmail:
    """Test the main load_okta_user_by_email function."""
    
    @pytest.mark.asyncio
    async def test_load_user_success(self, sample_okta_user):
        """Test successful user loading with all data."""
        mock_user_data = {
            "id": "user123",
            "profile": sample_okta_user["profile"]
        }
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="token123",
            API_TIMEOUT_SECONDS=10
        )
        
        with patch('app.services.okta_loader.get_settings', return_value=test_settings), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=mock_user_data), \
             patch('app.services.okta_loader._get_user_groups', return_value=sample_okta_user["groups"]), \
             patch('app.services.okta_loader._get_user_applications', return_value=sample_okta_user["applications"]):
            
            okta_user = await load_okta_user_by_email("test.user@example.com")
            
            assert okta_user is not None
            assert isinstance(okta_user, OktaUser)
            assert okta_user.profile.email == "test.user@example.com"
            assert "Engineering" in okta_user.groups
            assert "Google Workspace" in okta_user.applications
    
    @pytest.mark.asyncio
    async def test_load_user_not_found(self):
        """Test loading when user is not found in Okta."""
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="token123",
            API_TIMEOUT_SECONDS=10
        )
        
        with patch('app.services.okta_loader.get_settings', return_value=test_settings), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=None):
            
            with pytest.raises(OktaUserNotFoundError):
                await load_okta_user_by_email("notfound@example.com")
    
    @pytest.mark.asyncio
    async def test_load_user_invalid_structure(self):
        """Test loading when user data structure is invalid."""
        mock_user_data = {
            "id": "user123",
            "profile": None  # Invalid profile - will become {} and fail validation
        }
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="token123",
            API_TIMEOUT_SECONDS=10
        )
        
        with patch('app.services.okta_loader.get_settings', return_value=test_settings), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=mock_user_data):
            
            # Profile=None becomes {}, which fails Pydantic validation later
            with pytest.raises(OktaAPIError, match="Failed to validate Okta user data"):
                await load_okta_user_by_email("test@example.com")
    
    @pytest.mark.asyncio
    async def test_load_user_missing_user_id(self):
        """Test loading when user ID is missing."""
        mock_user_data = {
            "profile": {"email": "test@example.com"}
            # Missing 'id' field
        }
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="token123",
            API_TIMEOUT_SECONDS=10
        )
        
        with patch('app.services.okta_loader.get_settings', return_value=test_settings), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=mock_user_data):
            
            with pytest.raises(OktaAPIError, match="Invalid Okta user data structure"):
                await load_okta_user_by_email("test@example.com")
    
    @pytest.mark.asyncio
    async def test_load_user_config_error(self):
        """Test that configuration errors are handled properly."""
        with patch('app.services.okta_loader.get_settings', side_effect=Exception("Config error")):
            with pytest.raises(OktaConfigurationError, match="Okta configuration error"):
                await load_okta_user_by_email("test@example.com")
