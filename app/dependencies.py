from typing import Optional

from .store import InMemoryUserStore


_user_store: Optional[InMemoryUserStore] = None


def init_user_store() -> InMemoryUserStore:
    global _user_store
    if _user_store is None:
        _user_store = InMemoryUserStore()
    return _user_store


def get_user_store() -> InMemoryUserStore:
    return init_user_store()


