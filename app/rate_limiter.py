"""Two small, thread-safe rate limiters."""

from collections import deque
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable


class SlidingWindow:
    """Keep timestamps for requests inside a rolling time window."""

    def __init__(
        self,
        limit: int = 10,
        window_seconds: float = 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Create a limiter with a request limit and rolling window."""
        # Time/space: O(1).
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.requests = {}
        self.last_seen = {}
        self.lock = Lock()

    def allow(self, key: str) -> bool:
        """Return whether this key can make a request now."""
        # Time: O(1) amortized; space: O(1) per request.
        now = self.clock()
        with self.lock:
            times = self.requests.setdefault(key, deque())
            while times and now - times[0] >= self.window_seconds:
                times.popleft()
            self.last_seen[key] = now
            if len(times) >= self.limit:
                return False
            times.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Return whole seconds until the next request is allowed."""
        # Time/space: O(1).
        with self.lock:
            times = self.requests.get(key)
            if not times:
                return 1
            return max(1, ceil(times[0] + self.window_seconds - self.clock()))

    def cleanup(self, idle_seconds: float | None = None) -> int:
        """Remove keys idle for the requested number of seconds."""
        # Time: O(m); space: O(1), where m is the number of IPs.
        now = self.clock()
        idle_seconds = self.window_seconds if idle_seconds is None else idle_seconds
        with self.lock:
            idle = [
                ip
                for ip, seen in self.last_seen.items()
                if now - seen >= idle_seconds
            ]
            for ip in idle:
                del self.last_seen[ip]
                self.requests.pop(ip, None)
            return len(idle)


class TokenBucket:
    """Allow bursts, then refill tokens at a steady rate."""

    def __init__(
        self,
        capacity: int = 10,
        refill_rate: float = 10 / 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Create buckets with the given capacity and refill rate."""
        # Time/space: O(1).
        self.capacity = capacity
        self.rate = refill_rate
        self.clock = clock
        self.buckets = {}
        self.last_seen = {}
        self.lock = Lock()

    def allow(self, key: str) -> bool:
        """Refill and consume a token, if one is available."""
        # Time/space: O(1).
        now = self.clock()
        with self.lock:
            tokens, updated = self.buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - updated) * self.rate)
            self.last_seen[key] = now
            if tokens < 1:
                self.buckets[key] = (tokens, now)
                return False
            self.buckets[key] = (tokens - 1, now)
            return True

    def retry_after(self, key: str) -> int:
        """Return whole seconds until the next token is available."""
        # Time/space: O(1).
        with self.lock:
            tokens, updated = self.buckets.get(
                key, (self.capacity, self.clock())
            )
            tokens = min(
                self.capacity, tokens + (self.clock() - updated) * self.rate
            )
            return max(1, ceil((1 - tokens) / self.rate)) if tokens < 1 else 1

    def cleanup(self, idle_seconds: float = 60) -> int:
        """Remove buckets idle for the requested number of seconds."""
        # Time: O(m); space: O(1), where m is the number of IPs.
        now = self.clock()
        with self.lock:
            idle = [
                ip
                for ip, seen in self.last_seen.items()
                if now - seen >= idle_seconds
            ]
            for ip in idle:
                del self.last_seen[ip]
                self.buckets.pop(ip, None)
            return len(idle)
