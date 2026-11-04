"""Fixed-window rate limiter (in-memory).

WHAT: counts requests per key in 60-second windows.
WHY:  a runaway or abusive client must not be able to flood ingestion or
      evaluation endpoints. 429 + Retry-After is the standard contract.
HONEST LIMIT: counters live in this process's memory. With multiple
server instances behind a load balancer, move this to Redis (Phase 8
production note) - the interface (allow(key) -> (ok, retry_after))
stays the same.
"""
import threading
import time


class FixedWindowRateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit = limit_per_minute
        self._counts: dict[str, tuple[int, int]] = {}  # key -> (window, count)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        window = int(now // 60)
        with self._lock:
            win, count = self._counts.get(key, (window, 0))
            if win != window:
                win, count = window, 0
            if count >= self.limit:
                return False, max(1, 60 - int(now % 60))
            self._counts[key] = (win, count + 1)
            return True, 0
