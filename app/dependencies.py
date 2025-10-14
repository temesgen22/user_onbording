from typing import Optional
import logging

from .store import UserStore, InMemoryUserStore, RedisUserStore
from .config import get_settings

logger = logging.getLogger(__name__)

_user_store: Optional[UserStore] = None


def init_user_store() -> UserStore:
    """
    Initialize the user store based on configuration.
    
    Returns the configured storage backend (memory or redis).
    This is a singleton - only one instance is created per application lifecycle.
    """
    global _user_store
    if _user_store is None:
        settings = get_settings()
        
        if settings.storage_backend == "redis":
            logger.info(
                "Initializing Redis user store",
                extra={
                    "redis_host": settings.redis_host,
                    "redis_port": settings.redis_port,
                    "redis_db": settings.redis_db
                }
            )
            _user_store = RedisUserStore(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                key_prefix=settings.redis_key_prefix,
                connection_timeout=settings.redis_connection_timeout
            )
        else:
            logger.info("Initializing in-memory user store")
            _user_store = InMemoryUserStore()
    
    return _user_store


def get_user_store() -> UserStore:
    """Get the global user store instance."""
    return init_user_store()


