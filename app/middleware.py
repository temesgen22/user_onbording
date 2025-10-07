"""
Authentication and security middleware.
"""

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import logging

from .config import get_settings
from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate API key for protected endpoints.
    Only validates requests to /v1/hr/webhook if API_KEY is configured.
    """
    
    def __init__(self, app, protected_paths: Optional[list] = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/v1/hr/webhook"]
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next):
        """Validate API key for protected endpoints."""
        # Skip validation if no API key is configured (development mode)
        if not self.settings.api_key:
            logger.debug("API key validation disabled (no API_KEY configured)")
            return await call_next(request)
        
        # Check if path needs protection
        if request.url.path in self.protected_paths:
            api_key = request.headers.get("X-API-Key")
            
            if not api_key:
                logger.warning(
                    "API key missing for protected endpoint",
                    extra={"path": request.url.path, "client": request.client.host if request.client else "unknown"}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
            
            if api_key != self.settings.api_key:
                logger.warning(
                    "Invalid API key for protected endpoint",
                    extra={"path": request.url.path, "client": request.client.host if request.client else "unknown"}
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid API key",
                )
            
            logger.debug("API key validated successfully", extra={"path": request.url.path})
        
        return await call_next(request)


async def verify_api_key(api_key: Optional[str] = None) -> str:
    """
    Dependency to verify API key.
    Can be used with Depends() in route handlers.
    """
    settings = get_settings()
    
    # If no API key configured, allow access (development mode)
    if not settings.api_key:
        return "dev-mode"
    
    if not api_key:
        raise AuthenticationError("API key required")
    
    if api_key != settings.api_key:
        raise AuthenticationError("Invalid API key")
    
    return api_key

