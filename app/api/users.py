from fastapi import APIRouter, Depends, HTTPException, status
import logging

from ..schemas import EnrichedUser
from ..dependencies import get_user_store
from ..store import InMemoryUserStore
from ..exceptions import UserNotFoundError


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=EnrichedUser)
async def get_user(user_id: str, store: InMemoryUserStore = Depends(get_user_store)):
    """Retrieve an enriched user by employee ID."""
    logger.debug(f"Fetching user with ID: {user_id}")
    
    user = store.get(user_id)
    if user is None:
        logger.warning(
            "User not found in store",
            extra={"user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {user_id}"
        )
    
    logger.info(
        "Successfully retrieved user",
        extra={"user_id": user_id, "email": user.email}
    )
    return user


