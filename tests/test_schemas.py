"""
Tests for Pydantic schemas.
"""

import pytest
from pydantic import ValidationError

from app.schemas import HRUserIn, OktaUser, OktaProfile, EnrichedUser


class TestHRUserIn:
    """Test HRUserIn schema validation."""
    
    def test_valid_hr_user(self, sample_hr_user):
        """Test creating a valid HR user."""
        hr_user = HRUserIn(**sample_hr_user)
        assert hr_user.employee_id == "12345"
        assert hr_user.email == "test.user@example.com"
        assert hr_user.first_name == "Jane"
        assert hr_user.last_name == "Doe"
        assert hr_user.department == "Engineering"
    
    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            HRUserIn(
                employee_id="12345",
                # Missing required fields
            )
    
    def test_email_validation(self):
        """Test email validation."""
        invalid_data = {
            "employee_id": "12345",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "invalid-email"  # Invalid email format
        }
        
        with pytest.raises(ValidationError):
            HRUserIn(**invalid_data)
    
    def test_optional_fields(self):
        """Test that optional fields work correctly."""
        minimal_data = {
            "employee_id": "12345",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com"
        }
        
        hr_user = HRUserIn(**minimal_data)
        assert hr_user.employee_id == "12345"
        assert hr_user.title is None
        assert hr_user.department is None


class TestOktaProfile:
    """Test OktaProfile schema validation."""
    
    def test_valid_profile(self, sample_okta_user):
        """Test creating a valid Okta profile."""
        profile_data = sample_okta_user["profile"]
        profile = OktaProfile(**profile_data)
        
        assert profile.login == "test.user@example.com"
        assert profile.email == "test.user@example.com"
        assert profile.firstName == "Jane"
        assert profile.lastName == "Doe"
        assert profile.employeeNumber is None
    
    def test_email_validation(self):
        """Test email validation in Okta profile."""
        with pytest.raises(ValidationError):
            OktaProfile(
                login="invalid-email",
                email="invalid-email",
                firstName="Jane",
                lastName="Doe"
            )


class TestOktaUser:
    """Test OktaUser schema validation."""
    
    def test_valid_okta_user(self, sample_okta_user):
        """Test creating a valid Okta user."""
        okta_user = OktaUser(**sample_okta_user)
        
        assert okta_user.profile.email == "test.user@example.com"
        assert "Everyone" in okta_user.groups
        assert "Engineering" in okta_user.groups
        assert "Google Workspace" in okta_user.applications
    
    def test_empty_groups_and_applications(self):
        """Test Okta user with empty groups and applications."""
        data = {
            "profile": {
                "login": "test@example.com",
                "email": "test@example.com",
                "firstName": "Test",
                "lastName": "User"
            },
            "groups": [],
            "applications": []
        }
        
        okta_user = OktaUser(**data)
        assert okta_user.groups == []
        assert okta_user.applications == []


class TestEnrichedUser:
    """Test EnrichedUser schema validation."""
    
    def test_from_sources(self, sample_hr_user, sample_okta_user):
        """Test creating an enriched user from HR and Okta sources."""
        hr_user = HRUserIn(**sample_hr_user)
        okta_user = OktaUser(**sample_okta_user)
        
        enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_user)
        
        assert enriched.id == "12345"
        assert enriched.name == "Jane Doe"
        assert enriched.email == "test.user@example.com"
        assert enriched.title == "Software Engineer"
        assert enriched.department == "Engineering"
        assert enriched.startDate == "2024-01-15"
        assert enriched.onboarded is True
        assert "Engineering" in enriched.groups
        assert "Google Workspace" in enriched.applications
    
    def test_name_construction(self):
        """Test name construction from first and last names."""
        hr_data = {
            "employee_id": "12345",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john.smith@example.com"
        }
        okta_data = {
            "profile": {
                "login": "john.smith@example.com",
                "email": "john.smith@example.com",
                "firstName": "John",
                "lastName": "Smith"
            },
            "groups": [],
            "applications": []
        }
        
        hr_user = HRUserIn(**hr_data)
        okta_user = OktaUser(**okta_data)
        
        enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_user)
        assert enriched.name == "John Smith"
    
    def test_name_with_preferred_name(self):
        """Test name construction with preferred name."""
        hr_data = {
            "employee_id": "12345",
            "first_name": "Robert",
            "last_name": "Johnson",
            "preferred_name": "Bob",
            "email": "robert.johnson@example.com"
        }
        okta_data = {
            "profile": {
                "login": "robert.johnson@example.com",
                "email": "robert.johnson@example.com",
                "firstName": "Robert",
                "lastName": "Johnson"
            },
            "groups": [],
            "applications": []
        }
        
        hr_user = HRUserIn(**hr_data)
        okta_user = OktaUser(**okta_data)
        
        enriched = EnrichedUser.from_sources(hr=hr_user, okta=okta_user)
        # Note: The current implementation uses first_name + last_name, not preferred_name
        assert enriched.name == "Robert Johnson"
