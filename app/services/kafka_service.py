"""Kafka producer/consumer service for user enrichment."""

import json
import logging
from typing import Optional
from confluent_kafka import Producer
from confluent_kafka.error import KafkaError

from ..schemas import HRUserIn
from ..kafka_config import KafkaSettings, create_kafka_producer
from ..security import scrub_pii

logger = logging.getLogger(__name__)


class UserEnrichmentProducer:
    """Kafka producer for publishing enrichment requests."""
    
    def __init__(self, producer: Producer, topic: str):
        self.producer = producer
        self.topic = topic
    
    async def publish_enrichment_request(
        self,
        hr_user: HRUserIn,
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Publish user enrichment request to Kafka.
        
        Args:
            hr_user: HR user data to enrich
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            True if published successfully, False otherwise
        """
        try:
            message = {
                "employee_id": hr_user.employee_id,
                "email": hr_user.email,
                "first_name": hr_user.first_name,
                "last_name": hr_user.last_name,
                "title": hr_user.title,
                "department": hr_user.department,
                "start_date": hr_user.start_date,
                "manager_email": hr_user.manager_email,
                "location": hr_user.location,
                "correlation_id": correlation_id,
                # Include all fields needed for enrichment
            }
            
            # Use employee_id as key for partitioning
            key = hr_user.employee_id
            
            # Publish message
            self.producer.produce(
                topic=self.topic,
                key=key,
                value=json.dumps(message).encode('utf-8'),
                callback=self._delivery_callback
            )
            
            # Flush to ensure message is sent
            self.producer.flush(timeout=10)
            
            logger.info(
                "Published enrichment request to Kafka",
                extra=scrub_pii({
                    "employee_id": hr_user.employee_id,
                    "email": hr_user.email,
                    "topic": self.topic,
                    "correlation_id": correlation_id
                })
            )
            
            return True
            
        except KafkaError as e:
            logger.error(
                f"Failed to publish enrichment request: {e}",
                extra=scrub_pii({
                    "employee_id": hr_user.employee_id,
                    "email": hr_user.email,
                    "error": str(e)
                })
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error publishing to Kafka: {e}",
                extra=scrub_pii({
                    "employee_id": hr_user.employee_id,
                    "email": hr_user.email,
                    "error": str(e)
                }),
                exc_info=True
            )
            return False
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery confirmation."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
            )
    
    def close(self):
        """Close the Kafka producer."""
        try:
            self.producer.flush()
            logger.info("Kafka producer closed")
        except Exception as e:
            logger.error(f"Error closing Kafka producer: {e}")
