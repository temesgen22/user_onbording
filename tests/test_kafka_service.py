"""
Tests for Kafka service functionality.
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
import json
from confluent_kafka import KafkaError

from app.services.kafka_service import UserEnrichmentProducer
from app.schemas import HRUserIn


class TestUserEnrichmentProducer:
    """Test Kafka producer functionality."""
    
    @pytest.fixture
    def mock_kafka_producer(self):
        """Create a mock Kafka producer."""
        producer = Mock()
        producer.produce = Mock()
        producer.poll = Mock()
        producer.flush = Mock()
        return producer
    
    @pytest.fixture
    def kafka_producer_service(self, mock_kafka_producer):
        """Create UserEnrichmentProducer with mocked Kafka producer."""
        return UserEnrichmentProducer(
            producer=mock_kafka_producer,
            topic="test.topic"
        )
    
    @pytest.fixture
    def sample_hr_user_data(self):
        """Sample HR user data for testing."""
        return {
            "employee_id": "12345",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "test.user@example.com",
            "title": "Software Engineer",
            "department": "Engineering",
            "start_date": "2024-01-15",
            "manager_email": "john.smith@example.com",
            "location": "Stockholm"
        }
    
    @pytest.mark.asyncio
    async def test_publish_enrichment_request_success(self, kafka_producer_service, sample_hr_user_data):
        """Test successful message publishing."""
        hr_user = HRUserIn(**sample_hr_user_data)
        correlation_id = "test-correlation-123"
        
        # Mock successful delivery
        kafka_producer_service._delivery_callback = Mock()
        
        result = await kafka_producer_service.publish_enrichment_request(
            hr_user=hr_user,
            correlation_id=correlation_id
        )
        
        assert result is True
        
        # Verify producer.produce was called
        kafka_producer_service.producer.produce.assert_called_once()
        call_args = kafka_producer_service.producer.produce.call_args
        
        # Check topic
        assert call_args[1]["topic"] == "test.topic"
        
        # Check key (employee_id) - should be string, not bytes
        assert call_args[1]["key"] == "12345"
        
        # Check value (message content)
        message_data = json.loads(call_args[1]["value"].decode('utf-8'))
        assert message_data["employee_id"] == "12345"
        assert message_data["email"] == "test.user@example.com"
        assert message_data["correlation_id"] == correlation_id
        
        # Verify flush was called to ensure message delivery
        kafka_producer_service.producer.flush.assert_called_once_with(timeout=10)
    
    @pytest.mark.asyncio
    async def test_publish_enrichment_request_without_correlation_id(self, kafka_producer_service, sample_hr_user_data):
        """Test message publishing without correlation ID."""
        hr_user = HRUserIn(**sample_hr_user_data)
        
        result = await kafka_producer_service.publish_enrichment_request(hr_user=hr_user)
        
        assert result is True
        
        # Verify message was published
        call_args = kafka_producer_service.producer.produce.call_args
        message_data = json.loads(call_args[1]["value"].decode('utf-8'))
        assert message_data["correlation_id"] is None
    
    @pytest.mark.asyncio
    async def test_publish_enrichment_request_kafka_error(self, kafka_producer_service, sample_hr_user_data):
        """Test handling of Kafka errors during publishing."""
        hr_user = HRUserIn(**sample_hr_user_data)
        
        # Mock Kafka error
        kafka_producer_service.producer.produce.side_effect = KafkaError(KafkaError._INVALID_ARG, "Test error")
        
        result = await kafka_producer_service.publish_enrichment_request(hr_user=hr_user)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_enrichment_request_unexpected_error(self, kafka_producer_service, sample_hr_user_data):
        """Test handling of unexpected errors during publishing."""
        hr_user = HRUserIn(**sample_hr_user_data)
        
        # Mock unexpected error
        kafka_producer_service.producer.produce.side_effect = Exception("Unexpected error")
        
        result = await kafka_producer_service.publish_enrichment_request(hr_user=hr_user)
        
        assert result is False
    
    def test_delivery_callback_success(self, kafka_producer_service):
        """Test delivery callback for successful delivery."""
        # Mock message object
        mock_msg = Mock()
        mock_msg.topic.return_value = "test.topic"
        mock_msg.partition.return_value = 0
        mock_msg.offset.return_value = 123
        
        # Should not raise any exceptions
        kafka_producer_service._delivery_callback(None, mock_msg)
    
    def test_delivery_callback_error(self, kafka_producer_service):
        """Test delivery callback for delivery error."""
        # Mock error
        mock_error = Mock()
        mock_error.__str__ = Mock(return_value="Delivery failed")
        
        # Should not raise any exceptions
        kafka_producer_service._delivery_callback(mock_error, None)
    
    def test_close(self, kafka_producer_service):
        """Test producer close method."""
        kafka_producer_service.close()
        
        # Verify flush was called
        kafka_producer_service.producer.flush.assert_called_once()
    
    def test_close_with_error(self, kafka_producer_service):
        """Test producer close method with error."""
        # Mock flush to raise error
        kafka_producer_service.producer.flush.side_effect = Exception("Flush error")
        
        # Should not raise exception
        kafka_producer_service.close()


class TestKafkaConfiguration:
    """Test Kafka configuration and client creation."""
    
    def test_kafka_settings_defaults(self):
        """Test default Kafka settings."""
        import os
        from app.kafka_config import KafkaSettings
        
        # Clear environment variables that might affect the test
        env_vars_to_clear = [
            "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_ENRICHMENT_TOPIC", 
            "KAFKA_DLQ_TOPIC", "KAFKA_CONSUMER_GROUP"
        ]
        original_values = {}
        for var in env_vars_to_clear:
            original_values[var] = os.environ.get(var)
            os.environ.pop(var, None)
        
        try:
            settings = KafkaSettings()
            
            assert settings.KAFKA_BOOTSTRAP_SERVERS == "localhost:9092"
            assert settings.KAFKA_ENRICHMENT_TOPIC == "user.enrichment.requested"
            assert settings.KAFKA_DLQ_TOPIC == "user.enrichment.failed"
            assert settings.KAFKA_CONSUMER_GROUP == "user-enrichment-workers"
            assert settings.KAFKA_ENABLE_IDEMPOTENCE is True
            assert settings.KAFKA_ACKS == "all"
            assert settings.KAFKA_COMPRESSION_TYPE == "gzip"
        finally:
            # Restore original environment variables
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value
    
    def test_kafka_settings_from_env(self):
        """Test Kafka settings from environment variables."""
        import os
        from app.kafka_config import KafkaSettings
        
        # Set environment variables
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:9093"
        os.environ["KAFKA_ENRICHMENT_TOPIC"] = "test.enrichment"
        os.environ["KAFKA_DLQ_TOPIC"] = "test.dlq"
        
        try:
            settings = KafkaSettings()
            
            assert settings.KAFKA_BOOTSTRAP_SERVERS == "kafka:9093"
            assert settings.KAFKA_ENRICHMENT_TOPIC == "test.enrichment"
            assert settings.KAFKA_DLQ_TOPIC == "test.dlq"
        finally:
            # Clean up environment variables
            for key in ["KAFKA_BOOTSTRAP_SERVERS", "KAFKA_ENRICHMENT_TOPIC", "KAFKA_DLQ_TOPIC"]:
                os.environ.pop(key, None)
    
    @patch('app.kafka_config.Producer')
    def test_create_kafka_producer_success(self, mock_producer_class):
        """Test successful Kafka producer creation."""
        from app.kafka_config import KafkaSettings, create_kafka_producer
        
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        settings = KafkaSettings()
        producer = create_kafka_producer(settings)
        
        assert producer == mock_producer
        mock_producer_class.assert_called_once()
        
        # Verify producer configuration
        call_args = mock_producer_class.call_args[0][0]
        assert call_args["bootstrap.servers"] == "localhost:9092"
        assert call_args["acks"] == "all"
        assert call_args["enable.idempotence"] is True
        assert call_args["compression.type"] == "gzip"
    
    @patch('app.kafka_config.Producer')
    def test_create_kafka_producer_error(self, mock_producer_class):
        """Test Kafka producer creation with error."""
        from app.kafka_config import KafkaSettings, create_kafka_producer
        from confluent_kafka import KafkaError
        
        mock_producer_class.side_effect = KafkaError(KafkaError._INVALID_ARG, "Connection failed")
        
        settings = KafkaSettings()
        
        with pytest.raises(Exception):  # KafkaError is not a proper exception class
            create_kafka_producer(settings)
    
    @patch('app.kafka_config.Consumer')
    def test_create_kafka_consumer_success(self, mock_consumer_class):
        """Test successful Kafka consumer creation."""
        import os
        from app.kafka_config import KafkaSettings, create_kafka_consumer
        
        # Clear environment variables that might affect the test
        env_vars_to_clear = ["KAFKA_CONSUMER_GROUP"]
        original_values = {}
        for var in env_vars_to_clear:
            original_values[var] = os.environ.get(var)
            os.environ.pop(var, None)
        
        try:
            mock_consumer = Mock()
            mock_consumer_class.return_value = mock_consumer
            
            settings = KafkaSettings()
            consumer = create_kafka_consumer(settings, "test.topic")
            
            assert consumer == mock_consumer
            mock_consumer_class.assert_called_once()
            mock_consumer.subscribe.assert_called_once_with(["test.topic"])
            
            # Verify consumer configuration
            call_args = mock_consumer_class.call_args[0][0]
            assert call_args["bootstrap.servers"] == "localhost:9092"
            assert call_args["group.id"] == "user-enrichment-workers"
            assert call_args["enable.auto.commit"] is False
            assert call_args["auto.offset.reset"] == "earliest"
        finally:
            # Restore original environment variables
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value
    
    @patch('app.kafka_config.Consumer')
    def test_create_kafka_consumer_error(self, mock_consumer_class):
        """Test Kafka consumer creation with error."""
        from app.kafka_config import KafkaSettings, create_kafka_consumer
        from confluent_kafka import KafkaError
        
        mock_consumer_class.side_effect = KafkaError(KafkaError._INVALID_ARG, "Connection failed")
        
        settings = KafkaSettings()
        
        with pytest.raises(Exception):  # KafkaError is not a proper exception class
            create_kafka_consumer(settings, "test.topic")
