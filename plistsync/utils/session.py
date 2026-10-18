from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from importlib.metadata import version
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

import requests
from requests.sessions import HTTPAdapter
from urllib3.util.retry import Retry

from plistsync.core.auth import Token

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests.structures import CaseInsensitiveDict


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


T = TypeVar("T", bound=Token)


class TokenSession(Generic[T], requests.Session, ABC):
    """A request session configured to use a bearer token.

    This session manages authentication for API requests by automatically
    attaching bearer tokens to outgoing requests and handling token
    refresh when expired or rejected by the server.
    """

    token: T
    """The current token used for authentication."""

    status_codes_expired: ClassVar[list[int]] = []
    """HTTP status codes indicating an expired/invalid token."""

    status_codes_rate_limit: ClassVar[list[int]] = []
    """HTTP status codes indicating rate limiting."""

    on_refresh: Callable[[T], None] | None = None
    """Called with the token after a refresh, e.g. to persist it."""

    def __init__(self, token: T, **kwargs: Any) -> None:
        """Initialize the session with a token."""
        super().__init__(**kwargs)

        self.token = token

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        """Send a request with token authentication.

        Automatically handles token expiration and server-side token
        rejection by refreshing and retrying once per failure mode.
        """

        if self.token.is_expired:
            self.refresh_token()

        # Always use token in auth
        kwargs["auth"] = self.token

        # Calling requests again can in theory
        # create a infinite recursion but
        # should not happen in practice (fingers crossed)
        # we can add some max retry logic if this ever
        # is an issue
        res = super().request(
            method,
            url,
            *args,
            **kwargs,
        )

        if res.status_code in self.status_codes_expired:
            self.refresh_token()
            return self.request(method, url, *args, **kwargs)
        elif res.status_code in self.status_codes_rate_limit:
            self._handle_rate_limit(res.headers)
            return self.request(method, url, *args, **kwargs)

        return res

    @abstractmethod
    def _handle_rate_limit(self, headers: CaseInsensitiveDict) -> None:
        """Handle a rate limit response from the server."""
        ...

    @abstractmethod
    def _refresh_token(self) -> None:
        """Fetch a new token from the API.

        Implementations should update the token inplace.
        """
        ...

    def refresh_token(self) -> None:
        """Refresh the token and hand it to :attr:`on_refresh`."""
        self._refresh_token()
        if self.on_refresh is not None:
            self.on_refresh(self.token)


__all__ = [
    "PlistsyncSession",
    "RateLimitAdapter",
    "TokenSession",
]
