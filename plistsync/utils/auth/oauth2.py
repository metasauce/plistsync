"""OAuth2 authorization-code flow with PKCE and the associated token type."""

from __future__ import annotations

import base64
import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from pydantic import (
    BaseModel,
    ConfigDict,
    SecretStr,
    field_serializer,
    model_validator,
)

from plistsync.core.auth import AuthProvider, Token
from plistsync.errors import AuthenticationError, InvalidTokenError
from plistsync.logger import log
from plistsync.utils.session import PlistsyncSession

if TYPE_CHECKING:
    from plistsync.core.auth import Interaction


@dataclass(kw_only=True, frozen=True)
class OAuth2Request:
    """Flow state for an OAuth2 authorization-code exchange."""

    url: str
    """Authorization URL to open in the browser by the user."""

    redirect_uri: str
    """Redirect URI to capture the callback on."""

    state: str
    """Random string to prevent CSRF attacks."""

    code_verifier: str
    """PKCE (S256) verifier for the token exchange."""


class OAuth2Token(BaseModel, Token):
    """An OAuth2 access token with an optional refresh token and expiry."""

    model_config = ConfigDict(
        hide_input_in_errors=True,  # Allows to hide secret strings in output
    )

    access_token: SecretStr
    token_type: str = "Bearer"
    refresh_token: SecretStr | None = None
    expires_at: datetime | None = None
    scope: str | None = None

    EXPIRY_LEEWAY: ClassVar[int] = 10
    """Seconds before the actual expiry at which the token is considered stale."""

    @model_validator(mode="before")
    @classmethod
    def _apply_expires_in(cls, data: Any) -> Any:
        """Translate a relative ``expires_in`` into an absolute ``expires_at``."""
        if isinstance(data, dict) and data.get("expires_in") is not None:
            return {
                **data,
                "expires_at": datetime.now(UTC)
                + timedelta(seconds=int(data["expires_in"])),
            }
        return data

    @field_serializer("access_token", "refresh_token", when_used="always")
    def _reveal_secrets(self, value: SecretStr | None) -> str | None:
        """Expose the plaintext on serialization so tokens can be persisted."""
        return value.get_secret_value() if value is not None else None

    @property
    def is_expired(self) -> bool:
        """Whether the access token is expired (with a small leeway)."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at - timedelta(
            seconds=self.EXPIRY_LEEWAY
        )

    def update(self, token_data: dict[str, Any]) -> None:
        """Update this token in place from a token-endpoint response."""
        merged = {
            **self.model_dump(mode="json", exclude_none=True),
            **{key: value for key, value in token_data.items() if value is not None},
        }
        refreshed = type(self).model_validate(merged)
        for name in type(self).model_fields:
            setattr(self, name, getattr(refreshed, name))

    def refresh(
        self,
        *,
        token_endpoint: str,
        client_id: str,
        session: requests.Session | None = None,
        timeout: float = 30,
    ) -> None:
        """Exchange the refresh token for a fresh access token, in place."""
        if not self.refresh_token:
            raise InvalidTokenError(self)

        session = session or PlistsyncSession()
        try:
            response = session.post(
                token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": self.refresh_token.get_secret_value(),
                },
                timeout=timeout,
            )
        except requests.RequestException as e:
            raise InvalidTokenError(self) from e

        self.update(response.json())

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        """Attach the access token as an ``Authorization`` header."""
        request.headers["Authorization"] = (
            f"{self.token_type} {self.access_token.get_secret_value()}"
        )
        return request


class OAuth2Provider(AuthProvider[OAuth2Request, str | None, OAuth2Token], ABC):
    """Authenticate via OAuth2 authorization code flow with PKCE.

    To use this provider, implement the abstract methods and classvars.
    """

    authorize_endpoint: ClassVar[str]
    """OAuth2 authorization endpoint, e.g. ``https://accounts.spotify.com/authorize``."""

    token_endpoint: ClassVar[str]
    """OAuth2 token endpoint used to exchange the callback code for a token."""

    scopes: ClassVar[str]
    """Scopes to request for the service."""

    @abstractmethod
    def client_id(self) -> str:
        """Client ID for the service."""

    @abstractmethod
    def redirect_uri(self) -> str:
        """Redirect URI to capture the callback on."""

    @property
    def extra_authorize_params(self) -> dict[str, str]:
        """Additional query parameters for the authorization URL."""
        return {}

    def build_request(self) -> OAuth2Request:
        """Build the authorization URL with a fresh PKCE verifier."""
        code_verifier, code_challenge = self._generate_pkce()
        state = secrets.token_urlsafe(32)
        redirect_uri = self.redirect_uri()
        params = {
            "response_type": "code",
            "client_id": self.client_id(),
            "redirect_uri": redirect_uri,
            "scope": self.scopes,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            **self.extra_authorize_params,
        }
        return OAuth2Request(
            url=f"{self.authorize_endpoint}?{urlencode(params)}",
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier,
        )

    def collect_response(
        self, interaction: Interaction, request: OAuth2Request
    ) -> str | None:
        """Open the URL and serve the redirect."""
        interaction.open_url(request.url)
        return interaction.capture_redirect(request.redirect_uri)

    def obtain_token(self, request: OAuth2Request, response: str | None) -> OAuth2Token:
        """Exchange the callback code for a token."""
        if not response:
            raise AuthenticationError("No callback received.")

        query = parse_qs(urlparse(response).query)

        error = query.get("error", [None])[0]
        if error:
            description = query.get("error_description", [error])[0] or error
            raise AuthenticationError(description)

        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]
        if not code or not state:
            raise AuthenticationError("Missing 'code' or 'state' in callback URL.")
        if state != request.state:
            raise AuthenticationError("OAuth state mismatch; aborting authentication.")

        token_data = self._exchange_code(
            code, request.redirect_uri, request.code_verifier
        )
        return OAuth2Token.model_validate(token_data)

    def check_auth(self) -> bool:
        """Non-interactively check the current authentication status.

        Loads the persisted token and refreshes it if it has expired. A token
        that cannot be loaded or refreshed is considered not authenticated.
        """
        try:
            token = getattr(self.config, "token", None)
            if not isinstance(token, OAuth2Token):
                return False
            if token.is_expired:
                token.refresh(
                    token_endpoint=self.token_endpoint,
                    client_id=self.client_id(),
                )
                setattr(self.config, "token", token)
        except (InvalidTokenError, KeyError, TypeError, ValueError) as e:
            log.debug("Authentication check failed for %s: %s", type(self).__name__, e)
            return False

        return True

    def _exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str
    ) -> dict[str, Any]:
        """Exchange an authorization code for a token payload."""
        try:
            response = PlistsyncSession().post(
                self.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.client_id(),
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
                timeout=30,
            )
        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to obtain token: {e}") from e
        return response.json()

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        """Generate a PKCE code verifier and its S256 challenge."""
        verifier = secrets.token_urlsafe(32)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        return verifier, challenge


__all__ = [
    "OAuth2Provider",
    "OAuth2Request",
    "OAuth2Token",
]
