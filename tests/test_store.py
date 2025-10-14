"""
Tests for the in-memory user store.
"""

import pytest

from app.store import InMemoryUserStore
from app.schemas import EnrichedUser


class TestInMemoryUserStore:
    """Test the InMemoryUserStore functionality."""
    
    def test_put_and_get_user(self):
        """Test storing and retrieving a user."""
        store = InMemoryUserStore()
        
        # Create a test user
        user = EnrichedUser(
            id="12345",
            name="Jane Doe",
            email="jane.doe@example.com",
            title="Software Engineer",
            department="Engineering",
            startDate="2024-01-15",
            groups=["Engineering"],
            applications=["Slack"],
            onboarded=True
        )
        
        # Store the user
        store.put(user.id, user)
        
        # Retrieve the user
        retrieved_user = store.get(user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.name == user.name
        assert retrieved_user.email == user.email
        assert retrieved_user.title == user.title
        assert retrieved_user.department == user.department
        assert retrieved_user.startDate == user.startDate
        assert retrieved_user.groups == user.groups
        assert retrieved_user.applications == user.applications
        assert retrieved_user.onboarded == user.onboarded
    
    def test_get_nonexistent_user(self):
        """Test retrieving a user that doesn't exist."""
        store = InMemoryUserStore()
        
        retrieved_user = store.get("nonexistent")
        
        assert retrieved_user is None
    
    def test_put_multiple_users(self):
        """Test storing multiple users."""
        store = InMemoryUserStore()
        
        # Create multiple users
        user1 = EnrichedUser(
            id="12345",
            name="Jane Doe",
            email="jane.doe@example.com",
            title="Software Engineer",
            department="Engineering"
        )
        
        user2 = EnrichedUser(
            id="67890",
            name="John Smith",
            email="john.smith@example.com",
            title="Product Manager",
            department="Product"
        )
        
        # Store both users
        store.put(user1.id, user1)
        store.put(user2.id, user2)
        
        # Retrieve both users
        retrieved_user1 = store.get(user1.id)
        retrieved_user2 = store.get(user2.id)
        
        assert retrieved_user1 is not None
        assert retrieved_user1.id == user1.id
        assert retrieved_user1.name == user1.name
        
        assert retrieved_user2 is not None
        assert retrieved_user2.id == user2.id
        assert retrieved_user2.name == user2.name
    
    def test_overwrite_existing_user(self):
        """Test overwriting an existing user."""
        store = InMemoryUserStore()
        
        # Create initial user
        user1 = EnrichedUser(
            id="12345",
            name="Jane Doe",
            email="jane.doe@example.com",
            title="Software Engineer",
            department="Engineering"
        )
        
        # Create updated user with same ID
        user2 = EnrichedUser(
            id="12345",
            name="Jane Doe Updated",
            email="jane.doe.updated@example.com",
            title="Senior Software Engineer",
            department="Engineering"
        )
        
        # Store initial user
        store.put(user1.id, user1)
        
        # Verify initial user is stored
        retrieved = store.get(user1.id)
        assert retrieved.name == "Jane Doe"
        assert retrieved.title == "Software Engineer"
        
        # Overwrite with updated user
        store.put(user2.id, user2)
        
        # Verify user was overwritten
        retrieved = store.get(user2.id)
        assert retrieved.name == "Jane Doe Updated"
        assert retrieved.title == "Senior Software Engineer"
        assert retrieved.email == "jane.doe.updated@example.com"
    
    def test_store_with_minimal_user_data(self):
        """Test storing a user with minimal required data."""
        store = InMemoryUserStore()
        
        # Create user with only required fields
        user = EnrichedUser(
            id="12345",
            name="Minimal User",
            email="minimal@example.com"
        )
        
        store.put(user.id, user)
        retrieved_user = store.get(user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == user.id
        assert retrieved_user.name == user.name
        assert retrieved_user.email == user.email
        assert retrieved_user.title is None
        assert retrieved_user.department is None
        assert retrieved_user.startDate is None
        assert retrieved_user.groups == []
        assert retrieved_user.applications == []
        assert retrieved_user.onboarded is True  # Default value
    
    def test_store_with_complex_data(self):
        """Test storing a user with complex groups and applications data."""
        store = InMemoryUserStore()
        
        user = EnrichedUser(
            id="12345",
            name="Complex User",
            email="complex@example.com",
            title="Full Stack Developer",
            department="Engineering",
            startDate="2024-01-15",
            groups=["Engineering", "Full-Time Employees", "Stockholm Office", "Senior Developers"],
            applications=["Google Workspace", "Slack", "Jira", "GitHub", "VS Code"],
            onboarded=True
        )
        
        store.put(user.id, user)
        retrieved_user = store.get(user.id)
        
        assert retrieved_user is not None
        assert len(retrieved_user.groups) == 4
        assert "Senior Developers" in retrieved_user.groups
        assert len(retrieved_user.applications) == 5
        assert "VS Code" in retrieved_user.applications
    
    def test_store_isolation(self):
        """Test that different store instances are isolated."""
        store1 = InMemoryUserStore()
        store2 = InMemoryUserStore()
        
        user1 = EnrichedUser(id="12345", name="User 1", email="user1@example.com")
        user2 = EnrichedUser(id="67890", name="User 2", email="user2@example.com")
        
        # Store user1 in store1 and user2 in store2
        store1.put(user1.id, user1)
        store2.put(user2.id, user2)
        
        # Verify isolation
        assert store1.get(user1.id) is not None
        assert store1.get(user2.id) is None
        assert store2.get(user1.id) is None
        assert store2.get(user2.id) is not None
