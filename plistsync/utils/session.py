import threading
import time
from importlib.metadata import version

import requests
from requests.sessions import HTTPAdapter
from urllib3.util.retry import Retry


class RateLimitAdapter(HTTPAdapter):
    """HTTPAdapter with rate limiting + automatic retries for API clients.

    Features:
    - Rate limits requests to ``rate_limit`` seconds apart (thread-safe)
    - Retries failed requests (502, 503, 504 by default) with exponential backoff
    - Override ``_wait_time(elapsed)`` for custom rate limiting strategies

    Usage:
        session.mount('https://api.example.com/', RateLimitingAdapter(0.25))
    """

    def __init__(
        self,
        rate_limit: float = 0.25,
        max_retries: int = 6,
        backoff_factor: float = 1,
        status_forcelist: list[int] | None = None,
    ):
        status_forcelist = status_forcelist or [500, 502, 503, 504]
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        super().__init__(max_retries=retry)
        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def _wait_time(self, elapsed: float) -> float:
        """Return seconds to wait. Override for custom rate limiting."""
        return max(0, self.rate_limit - elapsed)

    def send(self, request: requests.PreparedRequest, *args, **kwargs):
        with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            wait = self._wait_time(elapsed)
            if wait > 0:
                time.sleep(wait)
            self._last_request_time = time.monotonic()
        return super().send(request, *args, **kwargs)


class PlistsyncSession(requests.Session):
    """A custom session for PlistSync.

    Should be used for all API requests to ensure consistent User-Agent and
    rate limiting across services.

    Features:
    - Rate limiting: Automatically handles rate limits by retrying failed requests.
    - User-Agent: Sets a custom User-Agent header for all requests.
    - Retry on failure: Can be extended to retry on specific HTTP status codes.
    """

    def __init__(
        self,
        rate_limit: float = 0.25,  # 4 requests per second
        **kwargs,
    ):
        super().__init__(**kwargs)  # needed because of multi inheritance
        self.headers["User-Agent"] = (
            f"plistsync/{version('plistsync')} https://docs.plistsync.com/"
        )

        adapter = RateLimitAdapter(rate_limit=rate_limit)
        self.mount("https://", adapter)
        self.mount("http://", adapter)

    def request(self, *args, **kwargs):
        """Execute a request with automatic retries and rate limiting."""
        kwargs.setdefault("timeout", 10)
        r = super().request(*args, **kwargs)
        r.raise_for_status()
        return r
