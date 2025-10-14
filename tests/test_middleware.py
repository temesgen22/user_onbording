"""
Tests for API middleware (authentication, request validation).
"""

import pytest
from unittest.mock import patch, Mock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from app.middleware import APIKeyMiddleware, verify_api_key
from app.config import Settings
from app.exceptions import AuthenticationError


class TestAPIKeyMiddleware:
    """Test API key middleware for endpoint protection."""
    
    def test_middleware_allows_unprotected_paths_without_key(self):
        """Test that unprotected paths work without API key."""
        # Create test app
        app = FastAPI()
        
        @app.get("/public")
        async def public_endpoint():
            return {"message": "public"}
        
        # Create settings without API key
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY=None
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            response = client.get("/public")
            
            assert response.status_code == 200
    
    def test_middleware_allows_protected_paths_when_no_key_configured(self):
        """Test that protected paths work when API key is not configured (dev mode)."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"status": "ok"}
        
        # No API key configured
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY=None
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            response = client.post("/v1/hr/webhook")
            
            # Should allow access without key in dev mode
            assert response.status_code == 200
    
    def test_middleware_blocks_protected_path_without_key(self):
        """Test that protected paths are blocked without API key when configured."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"status": "ok"}
        
        # API key configured
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="secret-api-key-123"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            response = client.post("/v1/hr/webhook")
            
            assert response.status_code == 401
            assert "API key required" in response.json()["detail"]
    
    def test_middleware_blocks_protected_path_with_invalid_key(self):
        """Test that protected paths are blocked with invalid API key."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"status": "ok"}
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="correct-key-123"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            response = client.post(
                "/v1/hr/webhook",
                headers={"X-API-Key": "wrong-key-456"}
            )
            
            assert response.status_code == 403
            assert "Invalid API key" in response.json()["detail"]
    
    def test_middleware_allows_protected_path_with_valid_key(self):
        """Test that protected paths work with valid API key."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"status": "ok"}
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="correct-key-123"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            response = client.post(
                "/v1/hr/webhook",
                headers={"X-API-Key": "correct-key-123"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
    
    def test_middleware_protects_multiple_paths(self):
        """Test that middleware can protect multiple paths."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"endpoint": "webhook"}
        
        @app.post("/v1/admin/action")
        async def admin_action():
            return {"endpoint": "admin"}
        
        @app.get("/v1/public")
        async def public():
            return {"endpoint": "public"}
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="secret-key"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(
                APIKeyMiddleware,
                protected_paths=["/v1/hr/webhook", "/v1/admin/action"]
            )
            
            client = TestClient(app)
            
            # Protected paths without key should fail
            assert client.post("/v1/hr/webhook").status_code == 401
            assert client.post("/v1/admin/action").status_code == 401
            
            # Public path should work
            assert client.get("/v1/public").status_code == 200
            
            # Protected paths with valid key should work
            headers = {"X-API-Key": "secret-key"}
            assert client.post("/v1/hr/webhook", headers=headers).status_code == 200
            assert client.post("/v1/admin/action", headers=headers).status_code == 200
    
    def test_middleware_case_sensitive_key(self):
        """Test that API key comparison is case-sensitive."""
        app = FastAPI()
        
        @app.post("/v1/hr/webhook")
        async def webhook():
            return {"status": "ok"}
        
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="SecretKey123"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            app.add_middleware(APIKeyMiddleware, protected_paths=["/v1/hr/webhook"])
            
            client = TestClient(app)
            
            # Wrong case should fail
            response = client.post(
                "/v1/hr/webhook",
                headers={"X-API-Key": "secretkey123"}
            )
            assert response.status_code == 403
            
            # Correct case should work
            response = client.post(
                "/v1/hr/webhook",
                headers={"X-API-Key": "SecretKey123"}
            )
            assert response.status_code == 200


class TestVerifyAPIKeyDependency:
    """Test the verify_api_key dependency function."""
    
    @pytest.mark.asyncio
    async def test_verify_api_key_dev_mode(self):
        """Test API key verification in dev mode (no key configured)."""
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY=None
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            result = await verify_api_key(None)
            assert result == "dev-mode"
    
    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self):
        """Test API key verification when key is missing."""
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="required-key"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            with pytest.raises(AuthenticationError, match="API key required"):
                await verify_api_key(None)
    
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """Test API key verification with invalid key."""
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="correct-key"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                await verify_api_key("wrong-key")
    
    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self):
        """Test API key verification with valid key."""
        test_settings = Settings(
            OKTA_ORG_URL="https://test.okta.com",
            OKTA_API_TOKEN="test-token",
            API_KEY="correct-key"
        )
        
        with patch('app.middleware.get_settings', return_value=test_settings):
            result = await verify_api_key("correct-key")
            assert result == "correct-key"

