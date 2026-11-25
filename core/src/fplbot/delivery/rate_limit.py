"""Per-chat limit on wrong invite codes (ticket 16).

Held in memory only: strangers' chat IDs are never written to the database, and a restart
simply forgets old attempts.
"""

from collections import deque
from datetime import datetime, timedelta


class AttemptLimiter:
    def __init__(self, max_attempts: int, window: timedelta) -> None:
        self._max_attempts = max_attempts
        self._window = window
        self._failures: dict[int, deque[datetime]] = {}

    def is_locked(self, key: int, now: datetime) -> bool:
        failures = self._failures.get(key)
        if failures is None:
            return False
        while failures and failures[0] <= now - self._window:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return False
        return len(failures) >= self._max_attempts

    def record_failure(self, key: int, now: datetime) -> None:
        self._failures.setdefault(key, deque()).append(now)
