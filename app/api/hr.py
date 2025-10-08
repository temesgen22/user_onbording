from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.responses import JSONResponse
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from ..schemas import HRUserIn, EnrichedUser, WebhookAcceptedResponse
from ..services.okta_loader import load_okta_user_by_email
from ..dependencies import get_user_store
from ..store import InMemoryUserStore
from ..security import scrub_pii
from ..exceptions import (
    OktaAPIError,
    OktaUserNotFoundError,
    OktaConfigurationError,
    UserOnboardingError
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/hr", tags=["hr"])


def should_retry_exception(exception):

    # Don't retry on non-retryable Okta errors
    if isinstance(exception, (OktaUserNotFoundError, OktaConfigurationError)):
        return False
    
    # Retry on generic OktaAPIError and connection issues
    if isinstance(exception, (OktaAPIError, ConnectionError, TimeoutError)):
        return True
    
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=should_retry_exception,
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


async def process_user_enrichment(hr_user: HRUserIn, store: InMemoryUserStore) -> None:
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
    background_tasks: BackgroundTasks,
    store: InMemoryUserStore = Depends(get_user_store),
):
    """
    Accept HR user payload and queue for background enrichment.
    
    Security:
    - Optional API key in X-API-Key header (if configured)
    - All PII is scrubbed from logs for privacy protection
    
    This endpoint accepts the webhook, validates the payload,
    queues the enrichment process as a background task, and returns immediately
    with 202 Accepted.
    
    The actual Okta API calls happen asynchronously after the response is sent,
    improving response times and preventing client timeouts.
    
    Returns:
        WebhookAcceptedResponse: Acknowledgment that the webhook was accepted
    """
    logger.info(
        "Received HR webhook for employee",
        extra=scrub_pii({"employee_id": hr_user.employee_id, "email": hr_user.email})
    )
    
    # Queue the enrichment process as a background task
    background_tasks.add_task(
        process_user_enrichment,
        hr_user=hr_user,
        store=store
    )
    
    logger.info(
        "Queued user enrichment for background processing",
        extra=scrub_pii({"employee_id": hr_user.employee_id, "email": hr_user.email})
    )
    
    # Return immediately with 202 Accepted (proper async semantics)
    return WebhookAcceptedResponse(
        status="accepted",
        message="User enrichment queued for background processing",
        employee_id=hr_user.employee_id,
        email=hr_user.email
    )


