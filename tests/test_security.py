"""
Tests for security utilities (PII scrubbing, webhook signatures).
"""

import pytest
import hmac
import hashlib

from app.security import (
    mask_email,
    hash_identifier,
    scrub_pii,
    generate_webhook_signature,
    verify_webhook_signature
)


class TestEmailMasking:
    """Test email address masking for PII protection."""
    
    def test_mask_standard_email(self):
        """Test masking a standard email address."""
        email = "jane.doe@example.com"
        masked = mask_email(email)
        
        assert masked == "ja***@example.com"
        assert "@" in masked
        assert "example.com" in masked
    
    def test_mask_short_email(self):
        """Test masking a short email (2 chars or less)."""
        email = "ab@example.com"
        masked = mask_email(email)
        
        assert masked == "**@example.com"
        assert "example.com" in masked
    
    def test_mask_single_char_email(self):
        """Test masking a single character email."""
        email = "a@example.com"
        masked = mask_email(email)
        
        assert masked == "*@example.com"
        assert "example.com" in masked
    
    def test_mask_empty_email(self):
        """Test masking an empty email."""
        masked = mask_email("")
        assert masked == "***"
    
    def test_mask_invalid_email(self):
        """Test masking an invalid email (no @ symbol)."""
        masked = mask_email("notanemail")
        assert masked == "***"
    
    def test_mask_long_email(self):
        """Test masking a long email address."""
        email = "verylongemailaddress@example.com"
        masked = mask_email(email)
        
        assert masked == "ve***@example.com"
        assert "example.com" in masked


class TestHashIdentifier:
    """Test identifier hashing for PII protection."""
    
    def test_hash_employee_id(self):
        """Test hashing an employee ID."""
        employee_id = "12345"
        hashed = hash_identifier(employee_id)
        
        # Should return first 8 chars of SHA-256 hash
        assert len(hashed) == 8
        assert hashed.isalnum()
        
        # Verify it's consistent
        assert hash_identifier(employee_id) == hashed
    
    def test_hash_different_ids(self):
        """Test that different IDs produce different hashes."""
        hash1 = hash_identifier("12345")
        hash2 = hash_identifier("67890")
        
        assert hash1 != hash2
    
    def test_hash_empty_string(self):
        """Test hashing an empty string."""
        hashed = hash_identifier("")
        assert hashed == "***"
    
    def test_hash_consistency(self):
        """Test that hashing is deterministic."""
        identifier = "test-user-123"
        hash1 = hash_identifier(identifier)
        hash2 = hash_identifier(identifier)
        
        assert hash1 == hash2
    
    def test_hash_format(self):
        """Test that hash is in expected format."""
        identifier = "employee-456"
        hashed = hash_identifier(identifier)
        
        # Should be 8 hexadecimal characters
        assert len(hashed) == 8
        assert all(c in '0123456789abcdef' for c in hashed)


class TestScrubPII:
    """Test PII scrubbing for log data."""
    
    def test_scrub_email(self):
        """Test scrubbing email addresses."""
        data = {"email": "jane.doe@example.com", "other": "value"}
        scrubbed = scrub_pii(data)
        
        assert scrubbed["email"] == "ja***@example.com"
        assert scrubbed["other"] == "value"
    
    def test_scrub_manager_email(self):
        """Test scrubbing manager_email field."""
        data = {"manager_email": "john.smith@example.com"}
        scrubbed = scrub_pii(data)
        
        assert scrubbed["manager_email"] == "jo***@example.com"
    
    def test_scrub_employee_id(self):
        """Test scrubbing employee ID (hashed)."""
        data = {"employee_id": "12345", "other": "value"}
        scrubbed = scrub_pii(data)
        
        # Employee ID should be removed and replaced with hash
        assert "employee_id" not in scrubbed
        assert "employee_id_hash" in scrubbed
        assert len(scrubbed["employee_id_hash"]) == 8
        assert scrubbed["other"] == "value"
    
    def test_scrub_names(self):
        """Test scrubbing first and last names."""
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "preferred_name": "Janey"
        }
        scrubbed = scrub_pii(data)
        
        assert scrubbed["first_name"] == "J***"
        assert scrubbed["last_name"] == "D***"
        assert scrubbed["preferred_name"] == "J***"
    
    def test_scrub_phone_numbers(self):
        """Test scrubbing phone numbers."""
        data = {
            "work_phone": "+46 8 123 456 78",
            "mobile_phone": "+46 70 987 6543"
        }
        scrubbed = scrub_pii(data)
        
        # Should keep last 4 digits only
        assert scrubbed["work_phone"] == "***4678"
        assert scrubbed["mobile_phone"] == "***6543"
    
    def test_scrub_short_phone(self):
        """Test scrubbing a short phone number (< 4 digits)."""
        data = {"phone": "123"}
        scrubbed = scrub_pii(data)
        
        assert scrubbed["phone"] == "***"
    
    def test_scrub_none_values(self):
        """Test scrubbing None values."""
        data = {
            "email": None,
            "first_name": None,
            "employee_id": None
        }
        scrubbed = scrub_pii(data)
        
        assert scrubbed["email"] is None
        assert scrubbed["first_name"] is None
        # employee_id becomes employee_id_hash even if None
        assert "employee_id_hash" in scrubbed
    
    def test_scrub_complex_data(self):
        """Test scrubbing complex nested data."""
        data = {
            "employee_id": "12345",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "work_phone": "+1-555-123-4567",
            "department": "Engineering",
            "title": "Software Engineer",
            "status_code": 200
        }
        scrubbed = scrub_pii(data)
        
        # Check PII is scrubbed
        assert "employee_id_hash" in scrubbed
        assert "employee_id" not in scrubbed
        assert scrubbed["first_name"] == "J***"
        assert scrubbed["last_name"] == "D***"
        assert scrubbed["email"] == "ja***@example.com"
        assert scrubbed["work_phone"] == "***4567"
        
        # Check non-PII is preserved
        assert scrubbed["department"] == "Engineering"
        assert scrubbed["title"] == "Software Engineer"
        assert scrubbed["status_code"] == 200
    
    def test_scrub_empty_dict(self):
        """Test scrubbing an empty dictionary."""
        data = {}
        scrubbed = scrub_pii(data)
        
        assert scrubbed == {}
    
    def test_scrub_preserves_non_pii(self):
        """Test that non-PII fields are preserved."""
        data = {
            "department": "Engineering",
            "title": "Software Engineer",
            "status": "Active",
            "count": 42,
            "enabled": True
        }
        scrubbed = scrub_pii(data)
        
        assert scrubbed == data


class TestWebhookSignature:
    """Test webhook signature generation and verification."""
    
    def test_generate_signature(self):
        """Test generating a webhook signature."""
        payload = b'{"employee_id": "12345"}'
        secret = "test-secret-key"
        
        signature = generate_webhook_signature(payload, secret)
        
        # Should be a hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA-256 produces 64 hex chars
        assert all(c in '0123456789abcdef' for c in signature)
    
    def test_generate_signature_consistency(self):
        """Test that signature generation is deterministic."""
        payload = b'{"test": "data"}'
        secret = "my-secret"
        
        sig1 = generate_webhook_signature(payload, secret)
        sig2 = generate_webhook_signature(payload, secret)
        
        assert sig1 == sig2
    
    def test_generate_signature_different_payloads(self):
        """Test that different payloads produce different signatures."""
        secret = "my-secret"
        
        sig1 = generate_webhook_signature(b'{"id": "1"}', secret)
        sig2 = generate_webhook_signature(b'{"id": "2"}', secret)
        
        assert sig1 != sig2
    
    def test_generate_signature_different_secrets(self):
        """Test that different secrets produce different signatures."""
        payload = b'{"test": "data"}'
        
        sig1 = generate_webhook_signature(payload, "secret1")
        sig2 = generate_webhook_signature(payload, "secret2")
        
        assert sig1 != sig2
    
    def test_verify_valid_signature(self):
        """Test verifying a valid webhook signature."""
        payload = b'{"employee_id": "12345"}'
        secret = "test-secret-key"
        
        signature = generate_webhook_signature(payload, secret)
        
        assert verify_webhook_signature(payload, signature, secret) is True
    
    def test_verify_invalid_signature(self):
        """Test verifying an invalid webhook signature."""
        payload = b'{"employee_id": "12345"}'
        secret = "test-secret-key"
        
        invalid_signature = "invalid_signature_123"
        
        assert verify_webhook_signature(payload, invalid_signature, secret) is False
    
    def test_verify_empty_signature(self):
        """Test verifying an empty signature."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        
        assert verify_webhook_signature(payload, "", secret) is False
    
    def test_verify_none_signature(self):
        """Test verifying a None signature."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        
        assert verify_webhook_signature(payload, None, secret) is False
    
    def test_verify_tampered_payload(self):
        """Test that verification fails if payload is tampered."""
        original_payload = b'{"employee_id": "12345"}'
        tampered_payload = b'{"employee_id": "67890"}'
        secret = "test-secret-key"
        
        # Generate signature for original
        signature = generate_webhook_signature(original_payload, secret)
        
        # Try to verify with tampered payload
        assert verify_webhook_signature(tampered_payload, signature, secret) is False
    
    def test_verify_wrong_secret(self):
        """Test that verification fails with wrong secret."""
        payload = b'{"test": "data"}'
        secret1 = "correct-secret"
        secret2 = "wrong-secret"
        
        signature = generate_webhook_signature(payload, secret1)
        
        assert verify_webhook_signature(payload, signature, secret2) is False
    
    def test_timing_attack_protection(self):
        """Test that signature comparison uses constant-time comparison."""
        payload = b'{"test": "data"}'
        secret = "test-secret"
        
        correct_signature = generate_webhook_signature(payload, secret)
        wrong_signature = "0" * 64  # Same length, all wrong
        
        # Should use hmac.compare_digest which is timing-attack resistant
        assert verify_webhook_signature(payload, correct_signature, secret) is True
        assert verify_webhook_signature(payload, wrong_signature, secret) is False
    
    def test_signature_with_special_characters(self):
        """Test signature generation with special characters in payload."""
        payload = b'{"name": "Test User", "email": "test@example.com", "special": "\u00e9\u00e8"}'
        secret = "test-secret"
        
        signature = generate_webhook_signature(payload, secret)
        
        assert verify_webhook_signature(payload, signature, secret) is True

