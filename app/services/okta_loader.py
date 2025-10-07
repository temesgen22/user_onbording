"""
Okta API client for fetching user data asynchronously.
"""

import logging
from typing import Optional, Dict, List, Any
import httpx

from ..schemas import OktaUser, OktaProfile
from ..config import get_settings
from ..exceptions import OktaAPIError, OktaUserNotFoundError, OktaConfigurationError

logger = logging.getLogger(__name__)


def _auth_headers(token: str) -> Dict[str, str]:
    """Generate authorization headers for Okta API."""
    return {
        "Authorization": f"SSWS {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def _find_okta_user_by_email(
    email: str,
    base_url: str,
    token: str,
    timeout: int
) -> Optional[Dict[str, Any]]:
    """
    Find Okta user by email address.
    
    Args:
        email: User email address to search for
        base_url: Okta organization URL
        token: Okta API token
        timeout: Request timeout in seconds
        
    Returns:
        User data dict if found, None otherwise
        
    Raises:
        OktaAPIError: If API call fails
    """
    headers = _auth_headers(token)
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/api/v1/users",
                headers=headers,
                params={"search": f'profile.email eq "{email}"'},
                timeout=timeout,
            )
            resp.raise_for_status()
            
            users = resp.json()
            if isinstance(users, list) and users:
                logger.info(f"Found Okta user for email: {email}")
                return users[0]
            
            logger.warning(f"No Okta user found for email: {email}")
            return None
            
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Okta API returned error status for email {email}: {e.response.status_code}",
            extra={"email": email, "status_code": e.response.status_code}
        )
        raise OktaAPIError(
            f"Okta API error: {e.response.status_code}",
            status_code=e.response.status_code,
            email=email
        )
    except httpx.TimeoutException as e:
        logger.error(f"Okta API timeout for email {email}", extra={"email": email})
        raise OktaAPIError(f"Okta API timeout", email=email)
    except httpx.RequestError as e:
        logger.error(
            f"Okta API request failed for email {email}: {str(e)}",
            extra={"email": email, "error": str(e)}
        )
        raise OktaAPIError(f"Okta API request failed: {str(e)}", email=email)
    except Exception as e:
        logger.error(
            f"Unexpected error finding Okta user for email {email}: {str(e)}",
            extra={"email": email, "error": str(e)}
        )
        raise OktaAPIError(f"Unexpected error: {str(e)}", email=email)


async def _get_user_groups(
    user_id: str,
    base_url: str,
    token: str,
    timeout: int
) -> List[str]:
    """
    Fetch user's group memberships from Okta.
    
    Args:
        user_id: Okta user ID
        base_url: Okta organization URL
        token: Okta API token
        timeout: Request timeout in seconds
        
    Returns:
        List of group names
    """
    headers = _auth_headers(token)
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/api/v1/users/{user_id}/groups",
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            
            payload = resp.json()
            names = []
            for g in payload if isinstance(payload, list) else []:
                # Okta group name may be under 'profile' or top-level 'profile' with 'name'
                name = None
                if isinstance(g, dict):
                    profile = g.get("profile")
                    if isinstance(profile, dict):
                        name = profile.get("name") or profile.get("description")
                    if not name:
                        name = g.get("label") or g.get("type")
                if name:
                    names.append(str(name))
            
            logger.debug(f"Found {len(names)} groups for user {user_id}")
            return names
            
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Failed to fetch groups for user {user_id}: {e.response.status_code}",
            extra={"user_id": user_id, "status_code": e.response.status_code}
        )
        return []
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching groups for user {user_id}", extra={"user_id": user_id})
        return []
    except httpx.RequestError as e:
        logger.warning(
            f"Request error fetching groups for user {user_id}: {str(e)}",
            extra={"user_id": user_id, "error": str(e)}
        )
        return []
    except Exception as e:
        logger.warning(
            f"Unexpected error fetching groups for user {user_id}: {str(e)}",
            extra={"user_id": user_id, "error": str(e)}
        )
        return []


async def _get_user_applications(
    user_id: str,
    base_url: str,
    token: str,
    timeout: int
) -> List[str]:
    """
    Fetch user's application assignments from Okta.
    
    Args:
        user_id: Okta user ID
        base_url: Okta organization URL
        token: Okta API token
        timeout: Request timeout in seconds
        
    Returns:
        List of application names
    """
    headers = _auth_headers(token)
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/api/v1/users/{user_id}/appLinks",
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            
            payload = resp.json()
            labels = []
            for app in payload if isinstance(payload, list) else []:
                if isinstance(app, dict):
                    label = app.get("label") or app.get("appName")
                    if label:
                        labels.append(str(label))
            
            logger.debug(f"Found {len(labels)} applications for user {user_id}")
            return labels
            
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"Failed to fetch applications for user {user_id}: {e.response.status_code}",
            extra={"user_id": user_id, "status_code": e.response.status_code}
        )
        return []
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching applications for user {user_id}", extra={"user_id": user_id})
        return []
    except httpx.RequestError as e:
        logger.warning(
            f"Request error fetching applications for user {user_id}: {str(e)}",
            extra={"user_id": user_id, "error": str(e)}
        )
        return []
    except Exception as e:
        logger.warning(
            f"Unexpected error fetching applications for user {user_id}: {str(e)}",
            extra={"user_id": user_id, "error": str(e)}
        )
        return []


async def load_okta_user_by_email(email: str) -> Optional[OktaUser]:
    """
    Fetch Okta user and enrichments from Okta API using email address.
    
    Args:
        email: User email address to search for
        
    Returns:
        OktaUser object if found, None otherwise
        
    Raises:
        OktaConfigurationError: If Okta credentials are not configured
        OktaUserNotFoundError: If user is not found in Okta
        OktaAPIError: If Okta API calls fail
    """
    try:
        settings = get_settings()
        base_url = settings.okta_org_url
        token = settings.okta_api_token
        timeout = settings.api_timeout_seconds
    except Exception as e:
        logger.error(f"Failed to load Okta configuration: {str(e)}")
        raise OktaConfigurationError(f"Okta configuration error: {str(e)}")
    
    logger.info(f"Loading Okta user data for email: {email}")
    
    # Find user by email
    user = await _find_okta_user_by_email(email, base_url, token, timeout)
    if not user or not isinstance(user, dict):
        raise OktaUserNotFoundError(email)
    
    user_id = user.get("id")
    profile = user.get("profile") or {}
    
    if not user_id or not isinstance(profile, dict):
        logger.error(
            f"Invalid Okta user data structure for email {email}",
            extra={"email": email, "has_id": bool(user_id), "has_profile": isinstance(profile, dict)}
        )
        raise OktaAPIError(f"Invalid Okta user data structure", email=email)
    
    # Fetch groups and applications in parallel
    groups, applications = await _get_user_groups(user_id, base_url, token, timeout), \
                           await _get_user_applications(user_id, base_url, token, timeout)
    
    # Build OktaUser model
    modeled = {
        "profile": {
            "login": profile.get("login") or profile.get("email"),
            "firstName": profile.get("firstName"),
            "lastName": profile.get("lastName"),
            "email": profile.get("email") or profile.get("login"),
            "employeeNumber": profile.get("employeeNumber"),
        },
        "groups": groups,
        "applications": applications,
    }
    
    try:
        okta_user = OktaUser.model_validate(modeled)
        logger.info(
            f"Successfully loaded Okta user for email {email}",
            extra={
                "email": email,
                "groups_count": len(groups),
                "apps_count": len(applications)
            }
        )
        return okta_user
    except Exception as e:
        logger.error(
            f"Failed to validate Okta user data for email {email}: {str(e)}",
            extra={"email": email, "error": str(e)}
        )
        raise OktaAPIError(f"Failed to validate Okta user data: {str(e)}", email=email)
