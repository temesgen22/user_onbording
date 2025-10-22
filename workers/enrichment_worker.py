"""
Kafka consumer worker for processing user enrichment requests.

This worker:
1. Consumes messages from user.enrichment.requested topic
2. Fetches Okta data with retry logic
3. Enriches and stores user data
4. Commits offset on success
5. Publishes failed messages to DLQ
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Optional
from confluent_kafka import Consumer, Producer
from confluent_kafka.error import KafkaError

# Add current directory to path for app module
sys.path.insert(0, '/app')

from app.schemas import HRUserIn, EnrichedUser
from app.services.okta_loader import load_okta_user_by_email
from app.dependencies import get_user_store
from app.kafka_config import KafkaSettings, create_kafka_consumer, create_kafka_producer
from app.exceptions import OktaUserNotFoundError, OktaConfigurationError, OktaAPIError
from app.security import scrub_pii
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
    before_sleep_log,
    after_log
)

logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=(
        retry_if_exception_type((OktaAPIError, ConnectionError, TimeoutError)) &
        retry_if_not_exception_type((OktaUserNotFoundError, OktaConfigurationError))
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def fetch_okta_data_with_retry(email: str):
    """Fetch Okta user data with automatic retry on transient failures."""
    return await load_okta_user_by_email(email)


async def process_enrichment_message(message_value: dict, store) -> tuple[bool, Optional[str]]:
    """
    Process a single enrichment message.
    
    Args:
        message_value: Deserialized message from Kafka
        store: User store instance
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    employee_id = message_value.get("employee_id")
    email = message_value.get("email")
    correlation_id = message_value.get("correlation_id")
    
    logger.info(
        "Processing enrichment request",
        extra=scrub_pii({
            "employee_id": employee_id,
            "email": email,
            "correlation_id": correlation_id
        })
    )
    
    try:
        # Reconstruct HRUserIn from message
        hr_user = HRUserIn(**message_value)
        
        # Fetch Okta data with retry
        okta_data = await fetch_okta_data_with_retry(email)
        
        # Merge HR and Okta data
        enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_data)
        
        # Store enriched user
        store.put(enriched.id, enriched)
        
        logger.info(
            "Successfully completed enrichment",
            extra=scrub_pii({
                "employee_id": employee_id,
                "user_id": enriched.id,
                "email": enriched.email,
                "groups_count": len(enriched.groups),
                "apps_count": len(enriched.applications),
                "correlation_id": correlation_id
            })
        )
        
        return True, None
        
    except OktaUserNotFoundError as e:
        error_msg = f"Okta user not found: {email}"
        logger.error(
            "Enrichment failed: User not found (permanent error)",
            extra=scrub_pii({
                "employee_id": employee_id,
                "email": email,
                "error": str(e),
                "correlation_id": correlation_id
            })
        )
        return False, error_msg
        
    except OktaConfigurationError as e:
        error_msg = f"Okta configuration error: {str(e)}"
        logger.error(
            "Enrichment failed: Configuration error (permanent error)",
            extra=scrub_pii({
                "employee_id": employee_id,
                "error": str(e),
                "correlation_id": correlation_id
            })
        )
        return False, error_msg
        
    except OktaAPIError as e:
        error_msg = f"Okta API error after retries: {str(e)}"
        logger.error(
            "Enrichment failed: API error after all retries",
            extra=scrub_pii({
                "employee_id": employee_id,
                "email": email,
                "error": str(e),
                "correlation_id": correlation_id
            })
        )
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(
            "Enrichment failed: Unexpected error",
            extra=scrub_pii({
                "employee_id": employee_id,
                "email": email,
                "error": str(e),
                "correlation_id": correlation_id
            }),
            exc_info=True
        )
        return False, error_msg


async def publish_to_dlq(producer: Producer, dlq_topic: str, original_message: dict, error: str):
    """Publish failed message to dead letter queue."""
    try:
        dlq_message = {
            **original_message,
            "error": error,
            "original_topic": "user.enrichment.requested",
            "failed_at": str(asyncio.get_event_loop().time())
        }
        
        producer.produce(
            topic=dlq_topic,
            key=original_message.get("employee_id"),
            value=json.dumps(dlq_message).encode('utf-8')
        )
        producer.flush(timeout=5)
        
        logger.info(
            "Published failed message to DLQ",
            extra=scrub_pii({
                "employee_id": original_message.get("employee_id"),
                "email": original_message.get("email"),
                "dlq_topic": dlq_topic
            })
        )
    except Exception as e:
        logger.error(f"Failed to publish to DLQ: {e}")


async def run_consumer():
    """
    Main consumer loop - processes enrichment requests from Kafka.
    
    This runs as a separate service/process from the API.
    """
    settings = KafkaSettings()
    kafka_consumer = create_kafka_consumer(settings, settings.KAFKA_ENRICHMENT_TOPIC)
    dlq_producer = create_kafka_producer(settings)  # For DLQ
    store = get_user_store()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(
        "Starting enrichment worker",
        extra={
            "topic": settings.KAFKA_ENRICHMENT_TOPIC,
            "consumer_group": settings.KAFKA_CONSUMER_GROUP
        }
    )
    
    try:
        while not shutdown_requested:
            # Poll for messages (timeout 1 second for graceful shutdown)
            msg = kafka_consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue
            
            logger.debug(
                f"Received message from Kafka",
                extra={
                    "partition": msg.partition(),
                    "offset": msg.offset(),
                    "key": msg.key()
                }
            )
            
            # Process the message
            try:
                message_value = json.loads(msg.value().decode('utf-8'))
                success, error = await process_enrichment_message(message_value, store)
                
                if success:
                    # Commit offset on success
                    kafka_consumer.commit(msg)
                    logger.debug(f"Committed offset {msg.offset()}")
                else:
                    # Publish to DLQ and commit offset (don't retry indefinitely)
                    await publish_to_dlq(
                        dlq_producer,
                        settings.KAFKA_DLQ_TOPIC,
                        message_value,
                        error
                    )
                    kafka_consumer.commit(msg)
                    logger.warning(f"Message moved to DLQ, offset committed")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                # Commit offset even on error to avoid infinite reprocessing
                kafka_consumer.commit(msg)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    
    except Exception as e:
        logger.error(f"Fatal error in consumer loop: {e}", exc_info=True)
    
    finally:
        logger.info("Closing Kafka consumer and producer...")
        kafka_consumer.close()
        dlq_producer.flush()
        store.close() if hasattr(store, 'close') else None
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    from app.logging_config import setup_logging
    setup_logging()
    
    asyncio.run(run_consumer())
