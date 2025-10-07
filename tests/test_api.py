"""
Tests for API endpoints.
"""

import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import OktaUser, OktaProfile


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_endpoint(self, client):
        """Test that health endpoint returns 200 OK."""
        response = client.get("/v1/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestHRWebhookEndpoint:
    """Test HR webhook endpoint."""
    
    def test_hr_webhook_success(self, client, sample_hr_user, sample_okta_user):
        """Test successful HR webhook processing."""
        # Mock the Okta loader to return our sample data
        mock_okta_user = OktaUser(**sample_okta_user)
        
        with patch('app.api.hr.load_okta_user_by_email', return_value=mock_okta_user):
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            assert response.status_code == 202
            data = response.json()
            
            # Verify the enriched user data
            assert data["id"] == "12345"
            assert data["name"] == "Jane Doe"
            assert data["email"] == "test.user@example.com"
            assert data["title"] == "Software Engineer"
            assert data["department"] == "Engineering"
            assert data["startDate"] == "2024-01-15"
            assert data["onboarded"] is True
            assert "Engineering" in data["groups"]
            assert "Google Workspace" in data["applications"]
    
    def test_hr_webhook_okta_user_not_found(self, client, sample_hr_user):
        """Test HR webhook when Okta user is not found."""
        with patch('app.api.hr.load_okta_user_by_email', return_value=None):
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()
    
    def test_hr_webhook_invalid_data(self, client):
        """Test HR webhook with invalid data."""
        invalid_data = {
            "employee_id": "12345",
            # Missing required fields
        }
        
        response = client.post("/v1/hr/webhook", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_hr_webhook_invalid_email(self, client):
        """Test HR webhook with invalid email format."""
        invalid_data = {
            "employee_id": "12345",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "invalid-email-format"
        }
        
        response = client.post("/v1/hr/webhook", json=invalid_data)
        
        assert response.status_code == 422  # Validation error


class TestUsersEndpoint:
    """Test users retrieval endpoint."""
    
    def test_get_user_success(self, client, user_store, sample_hr_user, sample_okta_user):
        """Test successful user retrieval."""
        # Create and store a user
        from app.schemas import HRUserIn, EnrichedUser
        
        hr_user = HRUserIn(**sample_hr_user)
        okta_user = OktaUser(**sample_okta_user)
        enriched_user = EnrichedUser.from_sources(hr=hr_user, okta=okta_user)
        
        # Mock the store to return our user
        with patch('app.api.users.get_user_store', return_value=user_store):
            user_store.put(enriched_user.id, enriched_user)
            
            response = client.get(f"/v1/users/{enriched_user.id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] == "12345"
            assert data["name"] == "Jane Doe"
            assert data["email"] == "test.user@example.com"
    
    def test_get_user_not_found(self, client, user_store):
        """Test user retrieval when user is not found."""
        with patch('app.api.users.get_user_store', return_value=user_store):
            response = client.get("/v1/users/nonexistent")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data


class TestIntegration:
    """Integration tests for the complete flow."""
    
    def test_complete_webhook_and_retrieve_flow(self, client, sample_hr_user, sample_okta_user):
        """Test the complete flow: webhook -> store -> retrieve."""
        # Mock Okta data
        mock_okta_user = OktaUser(**sample_okta_user)
        
        with patch('app.api.hr.load_okta_user_by_email', return_value=mock_okta_user):
            # Step 1: Send webhook
            webhook_response = client.post("/v1/hr/webhook", json=sample_hr_user)
            assert webhook_response.status_code == 202
            
            webhook_data = webhook_response.json()
            user_id = webhook_data["id"]
            
            # Step 2: Retrieve the user
            get_response = client.get(f"/v1/users/{user_id}")
            assert get_response.status_code == 200
            
            get_data = get_response.json()
            
            # Verify the data is consistent
            assert get_data["id"] == webhook_data["id"]
            assert get_data["name"] == webhook_data["name"]
            assert get_data["email"] == webhook_data["email"]
            assert get_data["groups"] == webhook_data["groups"]
            assert get_data["applications"] == webhook_data["applications"]
    
    def test_webhook_with_different_emails(self, client, sample_hr_user, sample_okta_user):
        """Test webhook with different email addresses."""
        # Modify the sample data to have different emails
        sample_hr_user["email"] = "hr.user@example.com"
        sample_okta_user["profile"]["email"] = "okta.user@example.com"
        
        mock_okta_user = OktaUser(**sample_okta_user)
        
        with patch('app.api.hr.load_okta_user_by_email', return_value=mock_okta_user):
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            # Should still work, but the enriched user will have HR email
            assert response.status_code == 202
            data = response.json()
            assert data["email"] == "hr.user@example.com"  # HR email takes precedence
