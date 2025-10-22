from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
import logging
import uuid
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
    before_sleep_log,
    after_log
)

from ..schemas import HRUserIn, EnrichedUser, WebhookAcceptedResponse
from ..services.okta_loader import load_okta_user_by_email
from ..dependencies import get_user_store, get_kafka_producer
from ..store import UserStore
from ..services.kafka_service import UserEnrichmentProducer
from ..security import scrub_pii
from ..exceptions import (
    OktaAPIError,
    OktaUserNotFoundError,
    OktaConfigurationError,
    UserOnboardingError
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/hr", tags=["hr"])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    # Retry on OktaAPIError, ConnectionError, TimeoutError
    # BUT exclude OktaUserNotFoundError and OktaConfigurationError (which are subclasses of OktaAPIError)
    retry=(
        retry_if_exception_type((OktaAPIError, ConnectionError, TimeoutError)) &
        retry_if_not_exception_type((OktaUserNotFoundError, OktaConfigurationError))
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def fetch_okta_data_with_retry(email: str):
    """
    Fetch Okta user data with automatic retry on transient failures.
    
    Retry Strategy:
    - Attempts: Up to 3 attempts
    - Wait time: Exponential backoff (2s, 4s, 8s, max 30s)
    - Retry on: OktaAPIError, ConnectionError, TimeoutError
    - No retry on: OktaUserNotFoundError, OktaConfigurationError
    
    Args:
        email: User email address to search for
        
    Returns:
        OktaUser object if found
        
    Raises:
        OktaUserNotFoundError: User not found (no retry)
        OktaConfigurationError: Configuration error (no retry)
        OktaAPIError: API error after all retries exhausted
    """
    logger.debug(f"Attempting to fetch Okta data for {email}")
    return await load_okta_user_by_email(email)


async def process_user_enrichment(hr_user: HRUserIn, store: UserStore) -> None:
    """
    Background task to enrich HR user data with Okta information.
    
    This function runs asynchronously after the webhook returns 202 Accepted.
    Errors are logged but do not affect the webhook response.
    
    Args:
        hr_user: HR user data from webhook payload
        store: User store instance for persisting enriched data
    """
    employee_id = hr_user.employee_id
    email = hr_user.email
    
    logger.info(
        "Starting background enrichment process",
        extra=scrub_pii({"employee_id": employee_id, "email": email})
    )
    
    try:
        # Fetch Okta data with automatic retry on transient failures
        # Will retry up to 3 times with exponential backoff (2s, 4s, 8s)
        okta_data = await fetch_okta_data_with_retry(email)
        
        # Merge HR and Okta data
        enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_data)
        
        # Store enriched user
        store.put(enriched.id, enriched)
        
        logger.info(
            "Successfully completed background enrichment",
            extra=scrub_pii({
                "employee_id": employee_id,
                "user_id": enriched.id,
                "email": enriched.email,
                "groups_count": len(enriched.groups),
                "apps_count": len(enriched.applications)
            })
        )
        
    except OktaUserNotFoundError as e:
        logger.error(
            "Background enrichment failed: Okta user not found (no retry)",
            extra=scrub_pii({"employee_id": employee_id, "email": email, "error": str(e)})
        )
        
    except OktaConfigurationError as e:
        logger.error(
            "Background enrichment failed: Okta configuration error (no retry)",
            extra=scrub_pii({"employee_id": employee_id, "error": str(e)})
        )
        
    except OktaAPIError as e:
        logger.error(
            "Background enrichment failed: Okta API error after retries",
            extra=scrub_pii({
                "employee_id": employee_id,
                "email": email,
                "error": str(e),
                "status_code": e.status_code,
                "note": "Failed after 3 retry attempts with exponential backoff"
            })
        )
        
    except Exception as e:
        logger.error(
            "Background enrichment failed: Unexpected error",
            extra=scrub_pii({"employee_id": employee_id, "email": email, "error": str(e)}),
            exc_info=True
        )


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED, response_model=WebhookAcceptedResponse)
async def hr_webhook(
    hr_user: HRUserIn,
    kafka_producer: UserEnrichmentProducer = Depends(get_kafka_producer),
):
    """
    Accept HR user payload and publish to Kafka for background enrichment.
    
    Security:
    - Optional API key in X-API-Key header (if configured)
    - All PII is scrubbed from logs for privacy protection
    
    Changes from BackgroundTasks:
    - Publishes message to Kafka instead of in-process background task
    - Returns immediately after successful publish
    - Worker services consume and process messages
    - Guaranteed delivery and horizontal scaling
    
    Returns:
        WebhookAcceptedResponse: Acknowledgment that webhook was accepted
    """
    # Generate correlation ID for tracking
    correlation_id = str(uuid.uuid4())
    
    logger.info(
        "Received HR webhook for employee",
        extra=scrub_pii({
            "employee_id": hr_user.employee_id,
            "email": hr_user.email,
            "correlation_id": correlation_id
        })
    )
    
    # Publish to Kafka
    published = await kafka_producer.publish_enrichment_request(
        hr_user=hr_user,
        correlation_id=correlation_id
    )
    
    if not published:
        # Failed to publish - return 503 Service Unavailable
        logger.error(
            "Failed to queue enrichment request",
            extra=scrub_pii({
                "employee_id": hr_user.employee_id,
                "correlation_id": correlation_id
            })
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue enrichment request. Please retry."
        )
    
    logger.info(
        "Queued user enrichment in Kafka",
        extra=scrub_pii({
            "employee_id": hr_user.employee_id,
            "email": hr_user.email,
            "correlation_id": correlation_id
        })
    )
    
    # Return immediately with 202 Accepted
    return WebhookAcceptedResponse(
        status="accepted",
        message=f"User enrichment queued (correlation_id: {correlation_id})",
        employee_id=hr_user.employee_id,
        email=hr_user.email,
        correlation_id=correlation_id
    )


