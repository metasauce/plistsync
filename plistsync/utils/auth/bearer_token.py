"""Bearer token handling.

This module provides functionality to manage Bearer tokens, including loading, saving to
json.
"""

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Generic,
    Self,
    TypeVar,
)

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import BearerToken as BearerTokenOauth2Client
from requests_oauth2client.tokens import ExpiredAccessToken


class Token(ABC):
    """Abstract base class for bearer tokens."""

    file_path: Path | None
    """Path where the token should be persisted. None for memory-only tokens."""

    def __init__(self, file_path: Path | None) -> None:
        self.file_path = file_path

    @abstractmethod
    def as_dict(self) -> dict[str, Any]:
        """Get the token data as a dictionary."""
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, token_dict: dict[str, Any]) -> Self:
        """Create token from dict."""
        ...

    @abstractmethod
    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        """Prepare the request to use the authentication."""
        ...

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return False

    @classmethod
    def from_file(cls, file_path: str | Path) -> Self:
        """Create token instance from file."""
        try:
            with open(file_path) as f:
                token_dict = json.load(f)
            token = cls.from_dict(token_dict)
            token.file_path = Path(file_path)
            return token
        except Exception as e:
            raise InvalidTokenError(None) from e

    def save(self):
        """Persist token to :attr:`file_path`. Raises if file_path is None."""
        if self.file_path is None:
            raise ValueError("Cannot save token: file_path is None")
        with open(self.file_path, "w") as f:
            json.dump(self.as_dict(), f)


class Oauth2Token(Token):
    """Handles serialization and deserialization of token data."""

    client: BearerTokenOauth2Client

    def __init__(
        self,
        client: BearerTokenOauth2Client,
        file_path: Path | None,
    ) -> None:
        super().__init__(file_path)
        self.client = client

    @staticmethod
    def deserialize_dict(token_dict: dict[str, Any]) -> dict[str, Any]:
        if "expires_at" in token_dict:
            expires_at = token_dict.pop("expires_at")
            # Convert to datetime if it's a string
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            token_dict["expires_at"] = expires_at
        return token_dict

    def as_dict(self) -> dict[str, Any]:
        """Get the token data as a dictionary."""
        d = self.client.as_dict()
        if self.client.expires_at is not None:
            d["expires_at"] = self.client.expires_at.isoformat()
        d.pop("expires_in", None)
        return d

    @classmethod
    def from_dict(cls, token_dict: dict[str, Any]) -> Self:
        """Create a BearerToken instance from a dictionary."""
        return cls(BearerTokenOauth2Client(cls.deserialize_dict(token_dict)), None)

    def update(self, token_data: dict[str, Any]) -> None:
        """Update the token data in place."""
        self.client = BearerTokenOauth2Client(**{**self.client.as_dict(), **token_data})

    def __call__(self, *args, **kwargs):
        return self.client(*args, **kwargs)

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

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        expires_at = self.client.as_dict().get("expires_at")
        if expires_at is None:
            return False
        # Convert expires_at to datetime if it's a timestamp
        if isinstance(expires_at, (int, float)):
            expires_at = datetime.fromtimestamp(expires_at, tz=UTC)
        return datetime.now(tz=UTC) >= expires_at


class InvalidTokenError(Exception):
    def __init__(self, token: Token | None):
        if token:
            self.message = f"Invalid token: {token}"
        else:
            self.message = "Token not found. Have you created a token?"
        super().__init__(self.message)


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

    def __init__(
        self,
        token: T,
    ) -> None:
        """Initialize the session with a token or token file."""
        super().__init__()

        self.token = token

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
        if self.token.file_path is not None:
            self.token.save()


__all__ = [
    "Token",
    "Oauth2Token",
    "TokenSession",
    "InvalidTokenError",
]
