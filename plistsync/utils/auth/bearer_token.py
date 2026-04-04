"""Bearer token handling.

This module provides functionality to manage Bearer tokens, including loading, saving to
json.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Self,
)

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import BearerToken as BearerTokenOauth2Client
from requests_oauth2client.tokens import ExpiredAccessToken

from plistsync.config import Config
from plistsync.errors import ConfigurationError


class BearerToken:
    """Handles serialization and deserialization of token data."""

    def __init__(self, token: BearerTokenOauth2Client):
        self.token = token

    @classmethod
    def from_dict(cls, token_dict: dict[str, Any]) -> Self:
        """Create a BearerToken instance from a dictionary."""
        if "expires_at" in token_dict:
            expires_at = token_dict.pop("expires_at")
            # Convert to datetime if it's a string
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            token_dict["expires_at"] = expires_at
        return cls(BearerTokenOauth2Client(**token_dict))

    @classmethod
    def from_file(cls, file_path: str | Path) -> Self:
        """Load token data from a JSON file."""
        try:
            with open(file_path) as f:
                token_dict = json.load(f)
            return cls.from_dict(token_dict)
        except Exception as e:
            raise InvalidTokenError(None) from e

    def save(self, file_path: str | Path):
        """Save token data to a JSON file."""
        with open(file_path, "w") as f:
            json.dump(self.as_dict(), f)

    def __call__(self, *args, **kwargs):
        """Make the instance callable to add the Authorization header.

        Usage:
            token = BearerToken(...)
            response = requests.get(url, auth=token)
        """
        return self.token(*args, **kwargs)

    def __repr__(self):
        def mask(k: str, v: Any):
            if not k.endswith("_token"):
                return v
            try:
                v_str = str(v)
                if len(v_str) < 9:
                    return "***"
                return f"{v_str[:3]}...{v_str[-3:]}"
            except Exception:
                return v

        res = "BearerToken("
        res += ", ".join([f"{k}={mask(k, v)}" for k, v in self.as_dict().items()])
        return res + ")"

    def as_dict(self) -> dict[str, Any]:
        """Get the token data as a dictionary."""
        d = self.token.as_dict()
        if self.token.expires_at is not None:
            d["expires_at"] = self.token.expires_at.isoformat()
        d.pop("expires_in", None)
        return d

    def update(self, token_data: dict[str, Any]) -> None:
        """Update the token data in place."""
        self.token = BearerTokenOauth2Client(**{**self.token.as_dict(), **token_data})

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        expires_at = self.token.as_dict().get("expires_at")
        if expires_at is None:
            return False
        # Convert expires_at to datetime if it's a timestamp
        if isinstance(expires_at, (int, float)):
            expires_at = datetime.fromtimestamp(expires_at, tz=UTC)
        return datetime.now(tz=UTC) >= expires_at


class InvalidTokenError(Exception):
    def __init__(self, token: BearerToken | None):
        if token:
            self.message = f"Invalid token: {token}"
        else:
            self.message = "Token not found. Have you created a token?"
        super().__init__(self.message)


class BearerTokenSession(requests.Session, ABC):
    """A request session configured to use a bearer token.

    This session manages authentication for API requests by automatically
    attaching bearer tokens to outgoing requests and handling token
    refresh when expired or rejected by the server.
    """

    token: BearerToken
    """The current bearer token used for authentication."""

    token_path: Path | None
    """Optional path to persist the token after refresh."""

    status_codes_expired: ClassVar[list[int]] = []
    """HTTP status codes indicating an expired/invalid token."""

    status_codes_rate_limit: ClassVar[list[int]] = []
    """HTTP status codes indicating rate limiting."""

    def __init__(
        self,
        token: BearerToken | None,
        token_path: Path | None,
    ) -> None:
        """Initialize the session with a token or token file."""
        super().__init__()

        if token is None and token_path is not None:
            token = BearerToken.from_file(token_path)
        elif token is not None:
            pass  # Use provided token
        else:
            raise ValueError("Either token or token path must be given!")

        self.token = token
        self.token_path = token_path

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        """Send a request with token authentication.

        Automatically handles token expiration and server-side token
        rejection by refreshing and retrying once per failure mode.
        """

        if self.token.is_expired:
            self._refresh_token()

        # Always use token in auth
        kwargs["auth"] = self.token

        # Calling requests again can in theory
        # create a infinite recursion but
        # should not happen in practice (fingers crossed)
        # we can add some max retry logic if this ever
        # is an issue
        try:
            res = super().request(
                method,
                url,
                *args,
                **kwargs,
            )
        except ExpiredAccessToken:
            self._refresh_token()
            return self.request(method, url, *args, **kwargs)

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
        """Refresh the token and persist it."""
        self._refresh_token()
        if self.token_path is not None:
            self.token.save(self.token_path)


def requires_bearer_token(
    config_key: str = "tidal",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Add tidal token to function.

    This decorator will load the token from the file if it exists. If the token does not
    exist it will throw an error. If the token is expired, it will refresh the token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    Usage
    -----

    .. code-block:: python

        @requires_bearer_token("tidal")
        async def needs_tidal_token(token: BearerToken):
            return token

    Attention
    ---------
    This decorator will not work for generator functions. If you need to use the
    `requires_bearer_token_generator` decorator.

    Note: If you want to use this decorator in a route make sure to catch the
    errors and redirect to the login route.

    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if "token" in kwargs:
                return await func(*args, **kwargs)

            token = get_bearer_token(config_key)
            # Pass the token as a keyword argument
            return await func(*args, token=token, **kwargs)

        return wrapper

    return decorator


def requires_bearer_token_generator(
    config_key: str = "tidal",
) -> Callable[
    [Callable[..., AsyncGenerator[Any, None]]], Callable[..., AsyncGenerator[Any, None]]
]:
    """Add tidal token to generator function.

    This decorator will load the token from the file if it exists. If the token does not
    exist it will throw an error. If the token is expired, it will refresh the token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    Usage
    -----

    ```python
    @requires_bearer_token_generator("tidal")
    async def needs_bearer_token(token: BearerToken):
        return token
    ```

    Attention
    ---------
    This decorator is for generator functions. If you need to use the
    `requires_bearer_token` decorator.

    Note: If you want to use this decorator in a route make sure to catch the
    errors and redirect to the login route.
    """

    def decorator(
        func: Callable[..., AsyncGenerator[Any, None]],
    ) -> Callable[..., AsyncGenerator[Any, None]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            token = get_bearer_token()
            # Pass the token as a keyword argument
            async for res in func(*args, token=token, **kwargs):
                yield res

        return wrapper

    return decorator


def get_bearer_token(config_key: str = "tidal") -> BearerToken:
    """Get the Tidal token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    """

    # Check if the config is available
    config = Config()
    service_config = getattr(config, config_key, None)
    if not service_config or not service_config.enabled:
        raise ConfigurationError(
            f"{config_key.capitalize()} config not available or {config_key}"
            "integration disabled!",
            config_key,
        )

    token_file = config.get_dir() / f"{config_key}_token.json"
    try:
        token = BearerToken.from_file(token_file)
    except Exception as e:
        raise InvalidTokenError(None) from e

    return token


__all__ = [
    "BearerToken",
    "requires_bearer_token",
    "requires_bearer_token_generator",
    "get_bearer_token",
]
