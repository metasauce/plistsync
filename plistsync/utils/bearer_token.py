"""Bearer token handling.

This module provides functionality to manage Bearer tokens, including loading, saving to json.
"""

import json
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Self,
)

from requests_oauth2client import BearerToken as BearerTokenOauth2Client

from plistsync.config import Config
from plistsync.errors import ConfigurationError


class BearerToken:
    """Handles serialization and deserialization of token data."""

    def __init__(self, token: BearerTokenOauth2Client):
        self.token = token

    @classmethod
    def from_dict(cls, token_dict: Dict[str, Any]) -> Self:
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
        with open(file_path, "r") as f:
            token_dict = json.load(f)
        return cls.from_dict(token_dict)

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
        res = "BearerToken("
        res += ", ".join([f"{k}={v}" for k, v in self.as_dict().items()])
        return res + ")"

    def as_dict(self) -> Dict[str, Any]:
        """Get the token data as a dictionary."""
        d = self.token.as_dict()
        if self.token.expires_at is not None:
            d["expires_at"] = self.token.expires_at.isoformat()
        d.pop("expires_in", None)
        return d

    def update(self, token_data: Dict[str, Any]) -> None:
        """Update the token data in place."""
        self.token = BearerTokenOauth2Client(**token_data)

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        expires_at = self.token.as_dict().get("expires_at")
        if expires_at is None:
            return False
        # Convert expires_at to datetime if it's a timestamp
        if isinstance(expires_at, (int, float)):
            expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        return datetime.now(tz=timezone.utc) >= expires_at


class InvalidToken(Exception):
    def __init__(self, token: BearerToken | None):
        if token:
            self.message = f"Invalid token: {token}"
        else:
            self.message = "Token not found. Have you created a token?"
        super().__init__(self.message)


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
            token = await get_bearer_token(config_key)
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
            token = await get_bearer_token()
            # Pass the token as a keyword argument
            async for res in func(*args, token=token, **kwargs):
                yield res

        return wrapper

    return decorator


async def get_bearer_token(config_key: str = "tidal") -> BearerToken:
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
            f"{config_key.capitalize()} config not available or {config_key} integration disabled!",
            config_key,
        )

    token_file = os.path.join(config.get_dir(), f"{config_key}_token.json")
    try:
        token = BearerToken.from_file(token_file)
    except Exception as e:
        raise InvalidToken(None) from e

    return token


__all__ = [
    "BearerToken",
    "requires_bearer_token",
    "requires_bearer_token_generator",
    "get_bearer_token",
]
