from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
import logging

from ..schemas import HRUserIn, EnrichedUser
from ..services.okta_loader import load_okta_user_by_email
from ..dependencies import get_user_store
from ..store import InMemoryUserStore
from ..exceptions import (
    OktaAPIError,
    OktaUserNotFoundError,
    OktaConfigurationError,
    UserOnboardingError
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/hr", tags=["hr"])


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED, response_model=EnrichedUser)
async def hr_webhook(
    hr_user: HRUserIn,
    store: InMemoryUserStore = Depends(get_user_store),
):
    """Accept HR user payload, enrich with Okta data, store, and return the enriched record."""
    logger.info(
        "Received HR webhook for employee",
        extra={"employee_id": hr_user.employee_id, "email": hr_user.email}
    )

    try:
        okta_data = await load_okta_user_by_email(hr_user.email)
    except OktaUserNotFoundError as e:
        logger.warning(
            "Okta user not found",
            extra={"email": hr_user.email, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Okta user not found for email: {hr_user.email}"
        )
    except OktaConfigurationError as e:
        logger.error(
            "Okta configuration error",
            extra={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Okta service configuration error"
        )
    except OktaAPIError as e:
        logger.error(
            "Okta API error",
            extra={"email": hr_user.email, "error": str(e), "status_code": e.status_code}
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch data from Okta API"
        )
    except Exception as e:
        logger.error(
            "Unexpected error processing HR webhook",
            extra={"employee_id": hr_user.employee_id, "email": hr_user.email, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook"
        )

    enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_data)
    store.put(enriched.id, enriched)
    
    logger.info(
        "Successfully stored enriched user",
        extra={
            "user_id": enriched.id,
            "email": enriched.email,
            "groups_count": len(enriched.groups),
            "apps_count": len(enriched.applications)
        }
    )
    
    return JSONResponse(content=enriched.model_dump(), status_code=status.HTTP_202_ACCEPTED)


