"""
Tests for the Redis user store.
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from app.store import RedisUserStore
from app.schemas import EnrichedUser


class TestRedisUserStore:
    """Test the RedisUserStore functionality."""
    
    def test_put_and_get_user(self, redis_user_store, mock_redis_client):
        """Test storing and retrieving a user."""
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
        redis_user_store.put(user.id, user)
        
        # Verify Redis set was called with correct key and JSON value
        expected_key = "test:12345"
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == expected_key
        
        # Mock the get to return the serialized user
        user_json = user.model_dump_json()
        mock_redis_client.get.return_value = user_json
        
        # Retrieve the user
        retrieved_user = redis_user_store.get(user.id)
        
        # Verify retrieval
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
    
    def test_get_nonexistent_user(self, redis_user_store, mock_redis_client):
        """Test retrieving a user that doesn't exist."""
        # Mock Redis to return None
        mock_redis_client.get.return_value = None
        
        retrieved_user = redis_user_store.get("nonexistent")
        
        assert retrieved_user is None
        mock_redis_client.get.assert_called_with("test:nonexistent")
    
    def test_put_multiple_users(self, redis_user_store, mock_redis_client):
        """Test storing multiple users."""
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
        redis_user_store.put(user1.id, user1)
        redis_user_store.put(user2.id, user2)
        
        # Verify both were stored with correct keys
        assert mock_redis_client.set.call_count == 2
        
        # Mock retrieval for user1
        mock_redis_client.get.return_value = user1.model_dump_json()
        retrieved_user1 = redis_user_store.get(user1.id)
        
        assert retrieved_user1 is not None
        assert retrieved_user1.id == user1.id
        assert retrieved_user1.name == user1.name
        
        # Mock retrieval for user2
        mock_redis_client.get.return_value = user2.model_dump_json()
        retrieved_user2 = redis_user_store.get(user2.id)
        
        assert retrieved_user2 is not None
        assert retrieved_user2.id == user2.id
        assert retrieved_user2.name == user2.name
    
    def test_overwrite_existing_user(self, redis_user_store, mock_redis_client):
        """Test overwriting an existing user."""
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
        redis_user_store.put(user1.id, user1)
        
        # Mock retrieval of initial user
        mock_redis_client.get.return_value = user1.model_dump_json()
        retrieved = redis_user_store.get(user1.id)
        assert retrieved.name == "Jane Doe"
        assert retrieved.title == "Software Engineer"
        
        # Overwrite with updated user
        redis_user_store.put(user2.id, user2)
        
        # Mock retrieval of updated user
        mock_redis_client.get.return_value = user2.model_dump_json()
        retrieved = redis_user_store.get(user2.id)
        assert retrieved.name == "Jane Doe Updated"
        assert retrieved.title == "Senior Software Engineer"
        assert retrieved.email == "jane.doe.updated@example.com"
    
    def test_store_with_minimal_user_data(self, redis_user_store, mock_redis_client):
        """Test storing a user with minimal required data."""
        # Create user with only required fields
        user = EnrichedUser(
            id="12345",
            name="Minimal User",
            email="minimal@example.com"
        )
        
        redis_user_store.put(user.id, user)
        
        # Mock retrieval
        mock_redis_client.get.return_value = user.model_dump_json()
        retrieved_user = redis_user_store.get(user.id)
        
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
    
    def test_store_with_complex_data(self, redis_user_store, mock_redis_client):
        """Test storing a user with complex groups and applications data."""
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
        
        redis_user_store.put(user.id, user)
        
        # Mock retrieval
        mock_redis_client.get.return_value = user.model_dump_json()
        retrieved_user = redis_user_store.get(user.id)
        
        assert retrieved_user is not None
        assert len(retrieved_user.groups) == 4
        assert "Senior Developers" in retrieved_user.groups
        assert len(retrieved_user.applications) == 5
        assert "VS Code" in retrieved_user.applications


class TestRedisStoreSpecificFeatures:
    """Test Redis-specific features and error handling."""
    
    def test_redis_connection(self, mock_redis_client):
        """Test that Redis connection is verified on initialization."""
        with patch('redis.Redis', return_value=mock_redis_client) as mock_redis_class:
            store = RedisUserStore(
                host="localhost",
                port=6379,
                db=0,
                key_prefix="test:"
            )
            
            # Verify Redis client was created with correct parameters
            mock_redis_class.assert_called_once()
            call_kwargs = mock_redis_class.call_args.kwargs
            assert call_kwargs['host'] == "localhost"
            assert call_kwargs['port'] == 6379
            assert call_kwargs['db'] == 0
            assert call_kwargs['decode_responses'] is True
            
            # Verify ping was called to test connection
            mock_redis_client.ping.assert_called_once()
    
    def test_redis_connection_failure(self, mock_redis_client):
        """Test handling of Redis connection failures."""
        # Make ping raise an exception
        mock_redis_client.ping.side_effect = Exception("Connection failed")
        
        with patch('redis.Redis', return_value=mock_redis_client):
            with pytest.raises(Exception) as exc_info:
                RedisUserStore(
                    host="localhost",
                    port=6379,
                    db=0,
                    key_prefix="test:"
                )
            
            assert "Connection failed" in str(exc_info.value)
    
    def test_key_prefix(self, redis_user_store, mock_redis_client):
        """Test that key prefix is correctly applied to all keys."""
        user = EnrichedUser(
            id="test123",
            name="Test User",
            email="test@example.com"
        )
        
        # Store user
        redis_user_store.put(user.id, user)
        
        # Verify the key has the correct prefix
        call_args = mock_redis_client.set.call_args
        assert call_args[0][0] == "test:test123"
        
        # Get user
        redis_user_store.get(user.id)
        
        # Verify get also uses correct prefix
        mock_redis_client.get.assert_called_with("test:test123")
    
    def test_serialization(self, redis_user_store, mock_redis_client):
        """Test JSON serialization and deserialization."""
        user = EnrichedUser(
            id="12345",
            name="Jane Doe",
            email="jane.doe@example.com",
            title="Engineer",
            department="Engineering",
            groups=["Team A", "Team B"],
            applications=["App1", "App2"]
        )
        
        # Store user
        redis_user_store.put(user.id, user)
        
        # Get the serialized data that was passed to Redis
        call_args = mock_redis_client.set.call_args
        stored_json = call_args[0][1]
        
        # Verify it's valid JSON
        stored_data = json.loads(stored_json)
        assert stored_data['id'] == "12345"
        assert stored_data['name'] == "Jane Doe"
        assert stored_data['email'] == "jane.doe@example.com"
        assert stored_data['groups'] == ["Team A", "Team B"]
        
        # Mock retrieval with the same JSON
        mock_redis_client.get.return_value = stored_json
        retrieved_user = redis_user_store.get(user.id)
        
        # Verify deserialization works correctly
        assert retrieved_user.id == user.id
        assert retrieved_user.name == user.name
        assert retrieved_user.groups == user.groups
    
    def test_close_connection(self, redis_user_store, mock_redis_client):
        """Test closing the Redis connection."""
        redis_user_store.close()
        
        # Verify close was called on the Redis client
        mock_redis_client.close.assert_called_once()
    
    def test_put_redis_error(self, redis_user_store, mock_redis_client):
        """Test handling of Redis errors during put operation."""
        user = EnrichedUser(
            id="12345",
            name="Test User",
            email="test@example.com"
        )
        
        # Make Redis set raise an exception
        mock_redis_client.set.side_effect = Exception("Redis error")
        
        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            redis_user_store.put(user.id, user)
        
        assert "Redis error" in str(exc_info.value)
    
    def test_get_redis_error(self, redis_user_store, mock_redis_client):
        """Test handling of Redis errors during get operation."""
        # Make Redis get raise an exception
        mock_redis_client.get.side_effect = Exception("Redis error")
        
        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            redis_user_store.get("12345")
        
        assert "Redis error" in str(exc_info.value)
    
    def test_get_deserialization_error(self, redis_user_store, mock_redis_client):
        """Test handling of corrupt/invalid JSON data."""
        # Mock Redis to return invalid JSON
        mock_redis_client.get.return_value = "invalid json data {{{["
        
        # Should raise a validation error
        with pytest.raises(Exception):
            redis_user_store.get("12345")
    
    def test_custom_key_prefix(self, mock_redis_client):
        """Test using a custom key prefix."""
        with patch('redis.Redis', return_value=mock_redis_client):
            store = RedisUserStore(
                host="localhost",
                port=6379,
                db=0,
                key_prefix="custom_prefix:"
            )
            
            user = EnrichedUser(
                id="test123",
                name="Test User",
                email="test@example.com"
            )
            
            store.put(user.id, user)
            
            # Verify custom prefix is used
            call_args = mock_redis_client.set.call_args
            assert call_args[0][0] == "custom_prefix:test123"
    
    def test_password_authentication(self, mock_redis_client):
        """Test Redis initialization with password."""
        with patch('redis.Redis', return_value=mock_redis_client) as mock_redis_class:
            store = RedisUserStore(
                host="localhost",
                port=6379,
                db=0,
                password="secret_password",
                key_prefix="test:"
            )
            
            # Verify password was passed to Redis client
            call_kwargs = mock_redis_class.call_args.kwargs
            assert call_kwargs['password'] == "secret_password"
    
    def test_custom_connection_timeout(self, mock_redis_client):
        """Test Redis initialization with custom timeout."""
        with patch('redis.Redis', return_value=mock_redis_client) as mock_redis_class:
            store = RedisUserStore(
                host="localhost",
                port=6379,
                db=0,
                connection_timeout=10
            )
            
            # Verify timeout was passed to Redis client
            call_kwargs = mock_redis_class.call_args.kwargs
            assert call_kwargs['socket_connect_timeout'] == 10
            assert call_kwargs['socket_timeout'] == 10
    
    def test_different_database_number(self, mock_redis_client):
        """Test using a different Redis database number."""
        with patch('redis.Redis', return_value=mock_redis_client) as mock_redis_class:
            store = RedisUserStore(
                host="localhost",
                port=6379,
                db=5,
                key_prefix="test:"
            )
            
            # Verify database number was passed
            call_kwargs = mock_redis_class.call_args.kwargs
            assert call_kwargs['db'] == 5

