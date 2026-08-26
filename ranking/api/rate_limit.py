"""Small, thread-safe sliding-window limiter for the single-process MVP."""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from threading import Lock


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float,
                 clock: Callable[[], float] = time.monotonic):
        if limit < 1 or window_seconds <= 0:
            raise ValueError("rate-limit values must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._next_cleanup = 0.0

    def consume(self, keys: Iterable[str]) -> int | None:
        """Consume one request for every key, or return Retry-After seconds."""
        keys = tuple(dict.fromkeys(keys))
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            if now >= self._next_cleanup:
                for key, events in list(self._events.items()):
                    while events and events[0] <= cutoff:
                        events.popleft()
                    if not events:
                        del self._events[key]
                self._next_cleanup = now + self.window_seconds

            retry_after = 0.0
            for key in keys:
                events = self._events[key]
                while events and events[0] <= cutoff:
                    events.popleft()
                if len(events) >= self.limit:
                    retry_after = max(retry_after, events[0] + self.window_seconds - now)

            if retry_after > 0:
                return max(1, math.ceil(retry_after))
            for key in keys:
                self._events[key].append(now)
            return None

    def refund(self, keys: Iterable[str]) -> None:
        """Undo the most recent consume for these keys (the action failed, so don't charge for it)."""
        with self._lock:
            for key in dict.fromkeys(keys):
                events = self._events.get(key)
                if events:
                    events.pop()
