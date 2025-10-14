from abc import ABC, abstractmethod
from typing import Dict, Optional
import json
import logging

from .schemas import EnrichedUser

logger = logging.getLogger(__name__)


class UserStore(ABC):
    """Abstract base class for user storage backends."""
    
    @abstractmethod
    def put(self, user_id: str, user: EnrichedUser) -> None:
        """Store a user by ID."""
        pass
    
    @abstractmethod
    def get(self, user_id: str) -> Optional[EnrichedUser]:
        """Retrieve a user by ID."""
        pass


class InMemoryUserStore(UserStore):
    """In-memory user storage implementation."""
    
    def __init__(self) -> None:
        self._users: Dict[str, EnrichedUser] = {}
        logger.info("Initialized InMemoryUserStore")

    def put(self, user_id: str, user: EnrichedUser) -> None:
        self._users[user_id] = user

    def get(self, user_id: str) -> Optional[EnrichedUser]:
        return self._users.get(user_id)


class RedisUserStore(UserStore):
    """Redis-backed user storage implementation."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "user_onboarding:",
        connection_timeout: int = 5
    ) -> None:
        """
        Initialize Redis user store.
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (optional)
            key_prefix: Prefix for all keys stored in Redis
            connection_timeout: Connection timeout in seconds
        """
        try:
            import redis
        except ImportError:
            raise RuntimeError(
                "redis package is required for RedisUserStore. "
                "Install it with: pip install redis"
            )
        
        self.key_prefix = key_prefix
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,  # Automatically decode responses to strings
            socket_connect_timeout=connection_timeout,
            socket_timeout=connection_timeout
        )
        
        # Test connection
        try:
            self.client.ping()
            logger.info(
                f"Successfully connected to Redis at {host}:{port} (db={db})",
                extra={
                    "redis_host": host,
                    "redis_port": port,
                    "redis_db": db,
                    "key_prefix": key_prefix
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to connect to Redis at {host}:{port}: {str(e)}",
                extra={
                    "redis_host": host,
                    "redis_port": port,
                    "error": str(e)
                }
            )
            raise
    
    def _make_key(self, user_id: str) -> str:
        """Generate Redis key for a user ID."""
        return f"{self.key_prefix}{user_id}"
    
    def put(self, user_id: str, user: EnrichedUser) -> None:
        """
        Store a user in Redis.
        
        The user object is serialized to JSON before storage.
        """
        try:
            key = self._make_key(user_id)
            # Serialize EnrichedUser to JSON
            user_json = user.model_dump_json()
            self.client.set(key, user_json)
            logger.debug(f"Stored user in Redis: {user_id}", extra={"user_id": user_id})
        except Exception as e:
            logger.error(
                f"Failed to store user in Redis: {str(e)}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    def get(self, user_id: str) -> Optional[EnrichedUser]:
        """
        Retrieve a user from Redis.
        
        Returns None if the user is not found.
        """
        try:
            key = self._make_key(user_id)
            user_json = self.client.get(key)
            
            if user_json is None:
                logger.debug(f"User not found in Redis: {user_id}", extra={"user_id": user_id})
                return None
            
            # Deserialize JSON to EnrichedUser
            user = EnrichedUser.model_validate_json(user_json)
            logger.debug(f"Retrieved user from Redis: {user_id}", extra={"user_id": user_id})
            return user
        except Exception as e:
            logger.error(
                f"Failed to retrieve user from Redis: {str(e)}",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    def close(self) -> None:
        """Close the Redis connection."""
        try:
            self.client.close()
            logger.info("Closed Redis connection")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {str(e)}")


