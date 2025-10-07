from typing import Dict, Optional

from .schemas import EnrichedUser


class InMemoryUserStore:
    def __init__(self) -> None:
        self._users: Dict[str, EnrichedUser] = {}

    def put(self, user_id: str, user: EnrichedUser) -> None:
        self._users[user_id] = user

    def get(self, user_id: str) -> Optional[EnrichedUser]:
        return self._users.get(user_id)


