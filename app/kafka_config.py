"""Kafka configuration and client initialization."""

from pydantic import Field
from pydantic_settings import BaseSettings
from confluent_kafka import Producer, Consumer
from confluent_kafka.error import KafkaError
import json
import logging

logger = logging.getLogger(__name__)


class KafkaSettings(BaseSettings):
    """Kafka-specific settings."""
    
    KAFKA_BOOTSTRAP_SERVERS: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated)"
    )
    KAFKA_ENRICHMENT_TOPIC: str = Field(
        default="user.enrichment.requested",
        description="Topic for user enrichment requests"
    )
    KAFKA_DLQ_TOPIC: str = Field(
        default="user.enrichment.failed",
        description="Dead letter queue topic for failed enrichments"
    )
    KAFKA_CONSUMER_GROUP: str = Field(
        default="user-enrichment-workers",
        description="Consumer group ID"
    )
    KAFKA_ENABLE_IDEMPOTENCE: bool = Field(
        default=True,
        description="Enable idempotent producer"
    )
    KAFKA_ACKS: str = Field(
        default="all",
        description="Acknowledgment level (all, 1, 0)"
    )
    KAFKA_COMPRESSION_TYPE: str = Field(
        default="gzip",
        description="Compression type (gzip, snappy, lz4, none)"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


def create_kafka_producer(settings: KafkaSettings) -> Producer:
    """
    Create a Kafka producer with proper configuration.
    
    Returns:
        Producer instance configured for reliable message delivery
    """
    try:
        producer_config = {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'acks': settings.KAFKA_ACKS,
            'enable.idempotence': settings.KAFKA_ENABLE_IDEMPOTENCE,
            'max.in.flight.requests.per.connection': 5,
            'retries': 3,
            'compression.type': settings.KAFKA_COMPRESSION_TYPE,
            'batch.size': 16384,
            'linger.ms': 10,
        }
        
        producer = Producer(producer_config)
        
        logger.info("Kafka producer created successfully")
        return producer
        
    except KafkaError as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        raise


def create_kafka_consumer(settings: KafkaSettings, topic: str) -> Consumer:
    """
    Create a Kafka consumer for the enrichment topic.
    
    Returns:
        Consumer instance configured for reliable consumption
    """
    try:
        consumer_config = {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'group.id': settings.KAFKA_CONSUMER_GROUP,
            'enable.auto.commit': False,  # Manual commit for reliability
            'auto.offset.reset': 'earliest',  # Process all messages
            'max.poll.interval.ms': 300000,  # 5 minutes
        }
        
        consumer = Consumer(consumer_config)
        consumer.subscribe([topic])
        
        logger.info(f"Kafka consumer created for topic: {topic}")
        return consumer
        
    except KafkaError as e:
        logger.error(f"Failed to create Kafka consumer: {e}")
        raise
