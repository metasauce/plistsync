from __future__ import annotations

import base64
import hashlib
import inspect
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, TypeVar
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from plistsync.errors import AuthenticationError
from plistsync.services.registry import Registry
from plistsync.utils.auth.bearer_token import Oauth2Token
from plistsync.utils.session import PlistsyncSession

if TYPE_CHECKING:
    from pathlib import Path

    from plistsync.config import ServiceConfig


class Interaction(Protocol):
    """Primitive user-facing operations, implemented by the caller.

    The provider decides which primitives its flow needs; the interaction
    holds no request, response, service or mode knowledge.
    """

    def open_url(self, url: str) -> None:
        """Open (or print) a URL for the user."""
        ...

    def show(self, message: str) -> None:
        """Display instructions (e.g. a device code)."""
        ...

    def ask(self, message: str) -> str:
        """Ask the user for a value (pasted URL, API key, ...)."""
        ...

    def capture_redirect(self, redirect_uri: str) -> str | None:
        """Wait for the browser callback at ``redirect_uri``; return it raw."""
        ...


class Token(Protocol):
    file_path: Path | None

    def save(self) -> None:
        """Persist the token to disk.

        Path is configured using the config when a token is created.
        """


Req = TypeVar("Req")
Res = TypeVar("Res")
T = TypeVar("T", bound=Token)


class AuthProvider(ABC, Registry, Generic[Req, Res, T]):
    """Initial authentication flow for a service.

    Used to obtain a token for the first time by a user.
    """

    config: ServiceConfig
    """Service configuration this provider is bound to."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Registry makes every abstract subclass a new root. Keep shared
        # abstract providers (e.g. OAuth2Provider) under the AuthProvider root,
        # so concrete services still register against AuthProvider.
        if inspect.isabstract(cls) or ABC in cls.__bases__:
            cls._registry = AuthProvider

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config

    def authenticate(
        self,
        interaction: Interaction,
    ) -> T:
        """Run the flow: build the request, collect the response, obtain the token."""
        request = self.build_request()
        response = self.collect_response(interaction, request)
        return self.obtain_token(request, response)

    @abstractmethod
    def build_request(self) -> Req:
        """Prepare what the user has to act on. No user-facing I/O."""

    @abstractmethod
    def collect_response(self, interaction: Interaction, request: Req) -> Res:
        """Drive the interaction and collect what it returned."""

    @abstractmethod
    def obtain_token(self, request: Req, response: Res) -> T:
        """Interpret the response, obtain a token and return it."""


# ---------------------------------- OAuth2 ---------------------------------- #
# TODO: We should move this into its own lazily loaded file, since it imports some deps
# that are not needed for most providers.


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


class OAuth2Provider(AuthProvider[OAuth2Request, str | None, Oauth2Token], ABC):
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

    def obtain_token(self, request: OAuth2Request, response: str | None) -> Oauth2Token:
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
        return Oauth2Token.from_dict(token_data)

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
