"""
Tests for API endpoints.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
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
        """Test successful HR webhook acceptance with Kafka publishing."""
        # Mock the Kafka producer to return success
        mock_producer = AsyncMock()
        mock_producer.publish_enrichment_request.return_value = True
        
        with patch('app.dependencies.get_kafka_producer', return_value=mock_producer):
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            assert response.status_code == 202
            data = response.json()
            
            # Verify the webhook was accepted and published to Kafka
            assert data["status"] == "accepted"
            assert data["employee_id"] == "12345"
            assert data["email"] == "test.user@example.com"
            assert "queued" in data["message"].lower()
            assert "correlation_id" in data
            
            # Verify Kafka producer was called
            mock_producer.publish_enrichment_request.assert_called_once()
            call_args = mock_producer.publish_enrichment_request.call_args
            assert call_args[1]["hr_user"].employee_id == "12345"
            assert call_args[1]["correlation_id"] is not None
    
    def test_hr_webhook_kafka_publish_failure(self, client, sample_hr_user):
        """Test HR webhook when Kafka publishing fails."""
        # Mock the Kafka producer to return failure
        mock_producer = AsyncMock()
        mock_producer.publish_enrichment_request.return_value = False
        
        with patch('app.dependencies.get_kafka_producer', return_value=mock_producer):
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            # Should return 503 Service Unavailable when Kafka publish fails
            assert response.status_code == 503
            data = response.json()
            assert "Unable to queue enrichment request" in data["detail"]
    
    def test_hr_webhook_okta_user_not_found(self, client, sample_hr_user):
        """Test HR webhook when Okta user is not found - now handled by Kafka workers."""
        # Mock the Kafka producer to return success (webhook accepts)
        mock_producer = AsyncMock()
        mock_producer.publish_enrichment_request.return_value = True
        
        # Use a unique employee_id to avoid conflicts with other tests
        sample_hr_user["employee_id"] = "99999"
        
        with patch('app.dependencies.get_kafka_producer', return_value=mock_producer):
            # Webhook should accept (202) and publish to Kafka
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "accepted"
            assert data["employee_id"] == "99999"
            
            # Verify Kafka producer was called
            mock_producer.publish_enrichment_request.assert_called_once()
            
            # User should NOT be in the store initially (worker hasn't processed yet)
            get_response = client.get("/v1/users/99999")
            assert get_response.status_code == 404
    
    def test_hr_webhook_invalid_data(self, client):
        """Test HR webhook with invalid data."""
        invalid_data = {
            "employee_id": "12345",
            # Missing required fields (first_name, last_name, email)
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
        with patch('app.dependencies.get_user_store', return_value=user_store):
            user_store.put(enriched_user.id, enriched_user)
            
            response = client.get(f"/v1/users/{enriched_user.id}")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["id"] == "12345"
            assert data["name"] == "Jane Doe"
            assert data["email"] == "test.user@example.com"
    
    def test_get_user_not_found(self, client, user_store):
        """Test user retrieval when user is not found."""
        with patch('app.dependencies.get_user_store', return_value=user_store):
            response = client.get("/v1/users/nonexistent")
            
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data


class TestIntegration:
    """Integration tests for the complete flow."""
    
    def test_complete_webhook_and_retrieve_flow(self, client, sample_hr_user, sample_okta_user):
        """Test the complete flow: webhook acceptance -> Kafka publishing -> retrieve."""
        # Mock Kafka producer
        mock_producer = AsyncMock()
        mock_producer.publish_enrichment_request.return_value = True
        
        with patch('app.dependencies.get_kafka_producer', return_value=mock_producer):
            # Step 1: Send webhook (returns immediately)
            webhook_response = client.post("/v1/hr/webhook", json=sample_hr_user)
            assert webhook_response.status_code == 202
            
            webhook_data = webhook_response.json()
            assert webhook_data["status"] == "accepted"
            assert webhook_data["employee_id"] == "12345"
            assert "correlation_id" in webhook_data
            
            # Verify Kafka producer was called
            mock_producer.publish_enrichment_request.assert_called_once()
            
            # Step 2: User should not be available yet (worker hasn't processed)
            get_response = client.get("/v1/users/12345")
            assert get_response.status_code == 404
    
    def test_webhook_with_different_emails(self, client, sample_hr_user, sample_okta_user):
        """Test webhook with different email addresses."""
        # Mock Kafka producer
        mock_producer = AsyncMock()
        mock_producer.publish_enrichment_request.return_value = True
        
        # Modify the sample data to have different emails
        sample_hr_user["email"] = "hr.user@example.com"
        
        with patch('app.dependencies.get_kafka_producer', return_value=mock_producer):
            # Webhook accepts immediately
            response = client.post("/v1/hr/webhook", json=sample_hr_user)
            assert response.status_code == 202
            
            webhook_data = response.json()
            assert webhook_data["email"] == "hr.user@example.com"
            assert "correlation_id" in webhook_data
            
            # Verify Kafka producer was called with correct data
            mock_producer.publish_enrichment_request.assert_called_once()
            call_args = mock_producer.publish_enrichment_request.call_args
            assert call_args[1]["hr_user"].email == "hr.user@example.com"
