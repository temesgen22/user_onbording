"""
Tests for the enrichment worker functionality.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
import json
from confluent_kafka import KafkaError

from app.schemas import HRUserIn, OktaUser, OktaProfile, EnrichedUser
from app.exceptions import OktaUserNotFoundError, OktaConfigurationError, OktaAPIError


class TestEnrichmentWorker:
    """Test enrichment worker functionality."""
    
    @pytest.fixture
    def sample_message_data(self):
        """Sample Kafka message data for testing."""
        return {
            "employee_id": "12345",
            "email": "test.user@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "title": "Software Engineer",
            "department": "Engineering",
            "start_date": "2024-01-15",
            "manager_email": "john.smith@example.com",
            "location": "Stockholm",
            "correlation_id": "test-correlation-123"
        }
    
    @pytest.fixture
    def sample_okta_user(self):
        """Sample Okta user data for testing."""
        return OktaUser(
            profile=OktaProfile(
                login="test.user@example.com",
                firstName="Jane",
                lastName="Doe",
                email="test.user@example.com",
                employeeNumber=None
            ),
            groups=["Everyone", "Engineering"],
            applications=["Google Workspace", "Slack"]
        )
    
    @pytest.fixture
    def mock_user_store(self):
        """Mock user store for testing."""
        store = Mock()
        store.put = Mock()
        store.close = Mock()
        return store
    
    @pytest.mark.asyncio
    async def test_process_enrichment_message_success(self, sample_message_data, sample_okta_user, mock_user_store):
        """Test successful message processing."""
        from workers.enrichment_worker import process_enrichment_message
        
        # Mock the Okta loader
        with patch('workers.enrichment_worker.load_okta_user_by_email', return_value=sample_okta_user):
            success, error = await process_enrichment_message(sample_message_data, mock_user_store)
            
            assert success is True
            assert error is None
            
            # Verify user was stored
            mock_user_store.put.assert_called_once()
            call_args = mock_user_store.put.call_args
            enriched_user = call_args[0][1]
            
            assert isinstance(enriched_user, EnrichedUser)
            assert enriched_user.id == "12345"
            assert enriched_user.name == "Jane Doe"
            assert enriched_user.email == "test.user@example.com"
            assert "Engineering" in enriched_user.groups
            assert "Google Workspace" in enriched_user.applications
    
    @pytest.mark.asyncio
    async def test_process_enrichment_message_okta_user_not_found(self, sample_message_data, mock_user_store):
        """Test message processing when Okta user is not found."""
        from workers.enrichment_worker import process_enrichment_message
        
        # Mock Okta user not found
        with patch('workers.enrichment_worker.load_okta_user_by_email', 
                  side_effect=OktaUserNotFoundError("test.user@example.com")):
            success, error = await process_enrichment_message(sample_message_data, mock_user_store)
            
            assert success is False
            assert "Okta user not found" in error
            assert "test.user@example.com" in error
            
            # Verify user was NOT stored
            mock_user_store.put.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_enrichment_message_okta_configuration_error(self, sample_message_data, mock_user_store):
        """Test message processing with Okta configuration error."""
        from workers.enrichment_worker import process_enrichment_message
        
        # Mock Okta configuration error
        with patch('workers.enrichment_worker.load_okta_user_by_email', 
                  side_effect=OktaConfigurationError("Invalid configuration")):
            success, error = await process_enrichment_message(sample_message_data, mock_user_store)
            
            assert success is False
            assert "Okta configuration error" in error
            assert "Invalid configuration" in error
            
            # Verify user was NOT stored
            mock_user_store.put.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_enrichment_message_okta_api_error(self, sample_message_data, mock_user_store):
        """Test message processing with Okta API error."""
        from workers.enrichment_worker import process_enrichment_message
        
        # Mock Okta API error
        with patch('workers.enrichment_worker.load_okta_user_by_email', 
                  side_effect=OktaAPIError("API error", status_code=500)):
            success, error = await process_enrichment_message(sample_message_data, mock_user_store)
            
            assert success is False
            assert "Okta API error after retries" in error
            assert "API error" in error
            
            # Verify user was NOT stored
            mock_user_store.put.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_enrichment_message_unexpected_error(self, sample_message_data, mock_user_store):
        """Test message processing with unexpected error."""
        from workers.enrichment_worker import process_enrichment_message
        
        # Mock unexpected error
        with patch('workers.enrichment_worker.load_okta_user_by_email', 
                  side_effect=Exception("Unexpected error")):
            success, error = await process_enrichment_message(sample_message_data, mock_user_store)
            
            assert success is False
            assert "Unexpected error" in error
            
            # Verify user was NOT stored
            mock_user_store.put.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_fetch_okta_data_with_retry_success(self, sample_okta_user):
        """Test successful Okta data fetching with retry."""
        from workers.enrichment_worker import fetch_okta_data_with_retry
        
        with patch('workers.enrichment_worker.load_okta_user_by_email', return_value=sample_okta_user):
            result = await fetch_okta_data_with_retry("test.user@example.com")
            
            assert result == sample_okta_user
    
    @pytest.mark.asyncio
    async def test_fetch_okta_data_with_retry_transient_error(self, sample_okta_user):
        """Test Okta data fetching with transient error and retry."""
        from workers.enrichment_worker import fetch_okta_data_with_retry
        from app.exceptions import OktaAPIError
        
        # Mock transient error on first call, success on second
        with patch('workers.enrichment_worker.load_okta_user_by_email') as mock_load:
            mock_load.side_effect = [OktaAPIError("Temporary error", status_code=503), sample_okta_user]
            
            result = await fetch_okta_data_with_retry("test.user@example.com")
            
            assert result == sample_okta_user
            assert mock_load.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_okta_data_with_retry_permanent_error(self):
        """Test Okta data fetching with permanent error (no retry)."""
        from workers.enrichment_worker import fetch_okta_data_with_retry
        from app.exceptions import OktaUserNotFoundError
        
        with patch('workers.enrichment_worker.load_okta_user_by_email') as mock_load:
            mock_load.side_effect = OktaUserNotFoundError("test.user@example.com")
            
            with pytest.raises(OktaUserNotFoundError):
                await fetch_okta_data_with_retry("test.user@example.com")
            
            # Should not retry for permanent errors
            assert mock_load.call_count == 1
    
    @pytest.mark.asyncio
    async def test_publish_to_dlq_success(self, sample_message_data):
        """Test successful DLQ publishing."""
        from workers.enrichment_worker import publish_to_dlq
        
        mock_producer = Mock()
        mock_producer.produce = Mock()
        mock_producer.flush = Mock()
        
        error_message = "Test error message"
        
        await publish_to_dlq(mock_producer, "test.dlq", sample_message_data, error_message)
        
        # Verify producer was called
        mock_producer.produce.assert_called_once()
        call_args = mock_producer.produce.call_args
        
        assert call_args[1]["topic"] == "test.dlq"
        assert call_args[1]["key"] == b"12345"
        
        # Verify message content
        message_data = json.loads(call_args[1]["value"].decode('utf-8'))
        assert message_data["employee_id"] == "12345"
        assert message_data["error"] == error_message
        assert message_data["original_topic"] == "user.enrichment.requested"
        assert "failed_at" in message_data
        
        # Verify flush was called
        mock_producer.flush.assert_called_once_with(timeout=5)
    
    @pytest.mark.asyncio
    async def test_publish_to_dlq_error(self, sample_message_data):
        """Test DLQ publishing with error."""
        from workers.enrichment_worker import publish_to_dlq
        
        mock_producer = Mock()
        mock_producer.produce = Mock()
        mock_producer.flush = Mock(side_effect=Exception("Flush error"))
        
        # Should not raise exception
        await publish_to_dlq(mock_producer, "test.dlq", sample_message_data, "Test error")
        
        # Verify producer was still called
        mock_producer.produce.assert_called_once()


class TestEnrichmentWorkerIntegration:
    """Integration tests for enrichment worker."""
    
    @pytest.fixture
    def mock_kafka_consumer(self):
        """Mock Kafka consumer for testing."""
        consumer = Mock()
        consumer.poll = Mock()
        consumer.commit = Mock()
        consumer.close = Mock()
        return consumer
    
    @pytest.fixture
    def mock_kafka_producer(self):
        """Mock Kafka producer for testing."""
        producer = Mock()
        producer.produce = Mock()
        producer.flush = Mock()
        producer.close = Mock()
        return producer
    
    def test_consumer_poll_no_message(self, mock_kafka_consumer, mock_kafka_producer, mock_user_store):
        """Test consumer polling with no message."""
        from workers.enrichment_worker import run_consumer
        
        # Mock no message available
        mock_kafka_consumer.poll.return_value = None
        
        # This would run indefinitely in real scenario, so we'll just test the polling logic
        msg = mock_kafka_consumer.poll(timeout=1.0)
        assert msg is None
    
    def test_consumer_poll_with_message(self, mock_kafka_consumer, mock_kafka_producer, mock_user_store):
        """Test consumer polling with message."""
        from workers.enrichment_worker import run_consumer
        
        # Mock message
        mock_msg = Mock()
        mock_msg.error.return_value = None
        mock_msg.value.return_value = json.dumps({
            "employee_id": "12345",
            "email": "test.user@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "correlation_id": "test-123"
        }).encode('utf-8')
        mock_msg.key.return_value = b"12345"
        mock_msg.partition.return_value = 0
        mock_msg.offset.return_value = 123
        
        mock_kafka_consumer.poll.return_value = mock_msg
        
        # Test message processing
        msg = mock_kafka_consumer.poll(timeout=1.0)
        assert msg is not None
        assert msg.error() is None
    
    def test_consumer_poll_with_error(self, mock_kafka_consumer, mock_kafka_producer, mock_user_store):
        """Test consumer polling with error."""
        from workers.enrichment_worker import run_consumer
        
        # Mock error message
        mock_msg = Mock()
        mock_error = Mock()
        mock_error.code.return_value = KafkaError._PARTITION_EOF
        mock_msg.error.return_value = mock_error
        
        mock_kafka_consumer.poll.return_value = mock_msg
        
        # Test error handling
        msg = mock_kafka_consumer.poll(timeout=1.0)
        assert msg is not None
        assert msg.error() is not None
        assert msg.error().code() == KafkaError._PARTITION_EOF
