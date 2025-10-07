"""
Custom exception classes for better error handling.
"""

from typing import Optional


class UserOnboardingError(Exception):
    """Base exception for all user onboarding errors."""
    pass


class OktaAPIError(UserOnboardingError):
    """Raised when Okta API calls fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, email: Optional[str] = None):
        self.status_code = status_code
        self.email = email
        super().__init__(message)


class OktaUserNotFoundError(OktaAPIError):
    """Raised when Okta user is not found."""
    
    def __init__(self, email: str):
        super().__init__(f"Okta user not found for email: {email}", status_code=404, email=email)


class OktaConfigurationError(OktaAPIError):
    """Raised when Okta configuration is missing or invalid."""
    
    def __init__(self, message: str = "Okta configuration is missing or invalid"):
        super().__init__(message, status_code=500)


class UserNotFoundError(UserOnboardingError):
    """Raised when user is not found in store."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class AuthenticationError(UserOnboardingError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)

