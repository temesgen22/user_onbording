"""
Tests for Okta loader service.
"""

import os
import pytest
from unittest.mock import patch, Mock
import requests

from app.services.okta_loader import (
    load_okta_user_by_email,
    _get_okta_base_url,
    _get_okta_token,
    _find_okta_user_by_email,
    _get_user_groups,
    _get_user_applications
)


class TestOktaCredentials:
    """Test Okta credential retrieval."""
    
    def test_get_okta_base_url_with_env_var(self):
        """Test getting Okta base URL from environment variable."""
        with patch.dict(os.environ, {"OKTA_ORG_URL": "https://test-org.okta.com"}):
            url = _get_okta_base_url()
            assert url == "https://test-org.okta.com"
    
    def test_get_okta_base_url_with_trailing_slash(self):
        """Test that trailing slashes are removed from URL."""
        with patch.dict(os.environ, {"OKTA_ORG_URL": "https://test-org.okta.com/"}):
            url = _get_okta_base_url()
            assert url == "https://test-org.okta.com"
    
    def test_get_okta_base_url_missing(self):
        """Test behavior when OKTA_ORG_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            url = _get_okta_base_url()
            assert url is None
    
    def test_get_okta_token_with_env_var(self):
        """Test getting Okta token from environment variable."""
        with patch.dict(os.environ, {"OKTA_API_TOKEN": "test-token-123"}):
            token = _get_okta_token()
            assert token == "test-token-123"
    
    def test_get_okta_token_with_whitespace(self):
        """Test that whitespace is stripped from token."""
        with patch.dict(os.environ, {"OKTA_API_TOKEN": "  test-token-123  "}):
            token = _get_okta_token()
            assert token == "test-token-123"
    
    def test_get_okta_token_missing(self):
        """Test behavior when OKTA_API_TOKEN is not set."""
        with patch.dict(os.environ, {}, clear=True):
            token = _get_okta_token()
            assert token is None


class TestOktaUserSearch:
    """Test Okta user search functionality."""
    
    def test_find_okta_user_by_email_success(self):
        """Test successful user search by email."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [{"id": "user123", "profile": {"email": "test@example.com"}}]
        
        with patch('requests.Session.get', return_value=mock_response):
            user = _find_okta_user_by_email("test@example.com", "https://test.okta.com", "token123")
            
            assert user is not None
            assert user["id"] == "user123"
            assert user["profile"]["email"] == "test@example.com"
    
    def test_find_okta_user_by_email_not_found(self):
        """Test user search when user is not found."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = []
        
        with patch('requests.Session.get', return_value=mock_response):
            user = _find_okta_user_by_email("notfound@example.com", "https://test.okta.com", "token123")
            
            assert user is None
    
    def test_find_okta_user_by_email_api_error(self):
        """Test user search when API returns error."""
        mock_response = Mock()
        mock_response.ok = False
        
        with patch('requests.Session.get', return_value=mock_response):
            user = _find_okta_user_by_email("test@example.com", "https://test.okta.com", "token123")
            
            assert user is None
    
    def test_find_okta_user_by_email_request_exception(self):
        """Test user search when request raises exception."""
        with patch('requests.Session.get', side_effect=requests.RequestException("Network error")):
            user = _find_okta_user_by_email("test@example.com", "https://test.okta.com", "token123")
            
            assert user is None


class TestOktaGroupsAndApplications:
    """Test Okta groups and applications retrieval."""
    
    def test_get_user_groups_success(self):
        """Test successful groups retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [
            {"profile": {"name": "Engineering"}},
            {"profile": {"name": "Everyone"}}
        ]
        
        with patch('requests.get', return_value=mock_response):
            groups = _get_user_groups("user123", "https://test.okta.com", "token123")
            
            assert "Engineering" in groups
            assert "Everyone" in groups
    
    def test_get_user_groups_api_error(self):
        """Test groups retrieval when API returns error."""
        mock_response = Mock()
        mock_response.ok = False
        
        with patch('requests.get', return_value=mock_response):
            groups = _get_user_groups("user123", "https://test.okta.com", "token123")
            
            assert groups == []
    
    def test_get_user_applications_success(self):
        """Test successful applications retrieval."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = [
            {"label": "Google Workspace"},
            {"label": "Slack"}
        ]
        
        with patch('requests.get', return_value=mock_response):
            apps = _get_user_applications("user123", "https://test.okta.com", "token123")
            
            assert "Google Workspace" in apps
            assert "Slack" in apps
    
    def test_get_user_applications_api_error(self):
        """Test applications retrieval when API returns error."""
        mock_response = Mock()
        mock_response.ok = False
        
        with patch('requests.get', return_value=mock_response):
            apps = _get_user_applications("user123", "https://test.okta.com", "token123")
            
            assert apps == []


class TestLoadOktaUserByEmail:
    """Test the main load_okta_user_by_email function."""
    
    def test_load_user_success(self, sample_okta_user):
        """Test successful user loading."""
        mock_user_data = {
            "id": "user123",
            "profile": sample_okta_user["profile"]
        }
        
        with patch('app.services.okta_loader._get_okta_base_url', return_value="https://test.okta.com"), \
             patch('app.services.okta_loader._get_okta_token', return_value="token123"), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=mock_user_data), \
             patch('app.services.okta_loader._get_user_groups', return_value=sample_okta_user["groups"]), \
             patch('app.services.okta_loader._get_user_applications', return_value=sample_okta_user["applications"]):
            
            okta_user = load_okta_user_by_email("test.user@example.com")
            
            assert okta_user is not None
            assert okta_user.profile.email == "test.user@example.com"
            assert "Engineering" in okta_user.groups
            assert "Google Workspace" in okta_user.applications
    
    def test_load_user_missing_credentials(self):
        """Test user loading when credentials are missing."""
        with patch('app.services.okta_loader._get_okta_base_url', return_value=None), \
             patch('app.services.okta_loader._get_okta_token', return_value="token123"):
            
            okta_user = load_okta_user_by_email("test@example.com")
            
            assert okta_user is None
    
    def test_load_user_missing_token(self):
        """Test user loading when token is missing."""
        with patch('app.services.okta_loader._get_okta_base_url', return_value="https://test.okta.com"), \
             patch('app.services.okta_loader._get_okta_token', return_value=None):
            
            okta_user = load_okta_user_by_email("test@example.com")
            
            assert okta_user is None
    
    def test_load_user_not_found(self):
        """Test user loading when user is not found in Okta."""
        with patch('app.services.okta_loader._get_okta_base_url', return_value="https://test.okta.com"), \
             patch('app.services.okta_loader._get_okta_token', return_value="token123"), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=None):
            
            okta_user = load_okta_user_by_email("notfound@example.com")
            
            assert okta_user is None
    
    def test_load_user_invalid_profile(self):
        """Test user loading when profile data is invalid."""
        mock_user_data = {
            "id": "user123",
            "profile": None  # Invalid profile
        }
        
        with patch('app.services.okta_loader._get_okta_base_url', return_value="https://test.okta.com"), \
             patch('app.services.okta_loader._get_okta_token', return_value="token123"), \
             patch('app.services.okta_loader._find_okta_user_by_email', return_value=mock_user_data):
            
            okta_user = load_okta_user_by_email("test@example.com")
            
            assert okta_user is None
