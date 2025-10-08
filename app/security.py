"""
Security utilities for PII protection and webhook signature verification.
"""

import hmac
import hashlib
import re
from typing import Dict, Any, Optional


def mask_email(email: str) -> str:
    """
    Mask email address for logging (PII protection).
    
    Example:
        jane.doe@example.com → ja***@example.com
    
    Args:
        email: Email address to mask
        
    Returns:
        Masked email address
    """
    if not email or '@' not in email:
        return "***"
    
    local, domain = email.split('@', 1)
    
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = local[:2] + "***"
    
    return f"{masked_local}@{domain}"


def hash_identifier(identifier: str) -> str:
    """
    Hash an identifier for logging (PII protection).
    
    Example:
        "12345" → "a665a45..."
    
    Args:
        identifier: String to hash
        
    Returns:
        First 8 characters of SHA-256 hash
    """
    if not identifier:
        return "***"
    
    hash_obj = hashlib.sha256(identifier.encode())
    return hash_obj.hexdigest()[:8]


def scrub_pii(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrub personally identifiable information from log data.
    
    Masks:
    - email, manager_email → Masked email (ja***@example.com)
    - employee_id → Hashed ID (first 8 chars of SHA-256)
    - first_name, last_name → First letter only
    - phone numbers → Last 4 digits only
    
    Args:
        data: Dictionary containing potentially sensitive data
        
    Returns:
        Dictionary with PII masked/hashed
    """
    scrubbed = {}
    
    for key, value in data.items():
        if value is None:
            scrubbed[key] = None
            continue
        
        # Mask emails
        if 'email' in key.lower() and isinstance(value, str):
            scrubbed[key] = mask_email(value)
        
        # Hash employee IDs
        elif key == 'employee_id' and isinstance(value, str):
            scrubbed['employee_id_hash'] = hash_identifier(value)
            # Don't include original employee_id
        
        # Mask names (first letter only)
        elif key in ('first_name', 'last_name', 'preferred_name') and isinstance(value, str):
            scrubbed[key] = value[0] + "***" if value else "***"
        
        # Mask phone numbers (last 4 digits only)
        elif 'phone' in key.lower() and isinstance(value, str):
            # Extract just digits
            digits = re.sub(r'\D', '', value)
            if len(digits) >= 4:
                scrubbed[key] = f"***{digits[-4:]}"
            else:
                scrubbed[key] = "***"
        
        # Keep other fields as-is
        else:
            scrubbed[key] = value
    
    return scrubbed


def generate_webhook_signature(payload: bytes, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    
    Args:
        payload: Raw request body as bytes
        secret: Shared secret key
        
    Returns:
        Hex-encoded HMAC signature
    """
    signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.
    
    Uses constant-time comparison to prevent timing attacks.
    
    Args:
        payload: Raw request body as bytes
        signature: Signature from X-Webhook-Signature header
        secret: Shared secret key
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        return False
    
    expected_signature = generate_webhook_signature(payload, secret)
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)

