"""Tests for the core authentication abstraction."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from requests_oauth2client import BearerToken

from plistsync.config import ServiceConfig
from plistsync.core.auth import AuthProvider, OAuth2Provider
from plistsync.errors import AuthenticationError
from plistsync.utils.auth.bearer_token import Oauth2Token, Token

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from plistsync.core.auth import Interaction


class FakeToken(Token):
    """Minimal token for testing the provider flow."""

    def __init__(self) -> None:
        super().__init__(None)

    def as_dict(self) -> dict:
        return {"token": "secret"}

    @classmethod
    def from_dict(cls, token_dict: dict) -> FakeToken:
        return cls()

    def __call__(self, request):
        return request


class FakeInteraction:
    """In-memory implementation of the auth interaction protocol.

    Parameters
    ----------
    redirect:
        Value returned by :meth:`capture_redirect`: a fixed callback URL,
        ``None``, or a callable receiving this interaction and the redirect
        URI (e.g. to echo the ``state`` from the URL a provider opened).
    """

    def __init__(
        self,
        redirect: str | None | Callable[[FakeInteraction, str], str | None] = None,
    ) -> None:
        self.redirect = redirect
        self.opened_urls: list[str] = []
        self.captured_uris: list[str] = []
        self.messages: list[str] = []

    def open_url(self, url: str) -> None:
        self.opened_urls.append(url)

    def show(self, message: str) -> None:
        self.messages.append(message)

    def ask(self, message: str) -> str:
        return ""

    def capture_redirect(self, redirect_uri: str) -> str | None:
        self.captured_uris.append(redirect_uri)
        if callable(self.redirect):
            return self.redirect(self, redirect_uri)
        return self.redirect


def _oauth2_callback(interaction: FakeInteraction, redirect_uri: str) -> str:
    """Echo the state from the last opened URL into the OAuth2 callback."""
    state = parse_qs(urlparse(interaction.opened_urls[-1]).query)["state"][0]
    return f"{redirect_uri}?code=auth-code&state={state}"


class RecordingProvider(AuthProvider[str, str, FakeToken], service="_test_auth_flow"):
    """Provider recording the order in which the flow steps run."""

    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(config)
        self.calls: list[str] = []

    def build_request(self) -> str:
        self.calls.append("build_request")
        return "request"

    def collect_response(self, interaction: Interaction, request: str) -> str:
        self.calls.append("collect_response")
        interaction.open_url("https://example.com/login")
        return "response"

    def obtain_token(self, request: str, response: str) -> FakeToken:
        self.calls.append("obtain_token")
        assert (request, response) == ("request", "response")
        return FakeToken()

    def check_auth(self) -> bool:
        self.calls.append("check_auth")
        return False


class FakeOAuth2Provider(OAuth2Provider, service="_test_core_auth"):
    """Minimal concrete OAuth2 provider for testing the base flow."""

    authorize_endpoint = "https://example.com/authorize"
    token_endpoint = "https://example.com/token"
    scopes = "read write"

    def client_id(self) -> str:
        return "client-id"

    def redirect_uri(self) -> str:
        return "http://127.0.0.1:1234/callback"


def test_build_request_uses_configured_redirect_uri() -> None:
    provider = FakeOAuth2Provider(ServiceConfig())

    request = provider.build_request()

    params = parse_qs(urlparse(request.url).query)
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == ["http://127.0.0.1:1234/callback"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["read write"]
    assert request.redirect_uri == "http://127.0.0.1:1234/callback"
    assert request.state
    assert request.code_verifier


class TestAuthProvider:
    """The generic flow: build_request → collect_response → obtain_token."""

    def test_authenticate_runs_steps_in_order_and_returns_token(self) -> None:
        provider = RecordingProvider(ServiceConfig())
        interaction = FakeInteraction()

        token = provider.authenticate(interaction)

        assert isinstance(token, FakeToken)
        assert provider.calls == ["build_request", "collect_response", "obtain_token"]
        assert interaction.opened_urls == ["https://example.com/login"]

    def test_config_is_stored(self) -> None:
        config = ServiceConfig()

        assert RecordingProvider(config).config is config

    def test_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            AuthProvider(ServiceConfig())  # type: ignore[abstract]

    def test_concrete_provider_registers_under_service_name(self) -> None:
        assert RecordingProvider in AuthProvider.registry().get("_test_auth_flow", [])

    def test_abstract_subclass_uses_auth_provider_registry(self) -> None:
        assert OAuth2Provider.registry() is AuthProvider.registry()


class TestInteraction:
    """The Interaction protocol is structural: the four primitives suffice."""

    def test_in_memory_interaction_satisfies_protocol(self) -> None:
        interaction: Interaction = FakeInteraction()

        interaction.open_url("https://example.com")

        assert interaction.opened_urls == ["https://example.com"]


class TestOAuth2Provider:
    """The PKCE authorization-code flow, end to end."""

    def test_authenticate_exchanges_code_for_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = FakeOAuth2Provider(ServiceConfig())
        interaction = FakeInteraction(redirect=_oauth2_callback)
        session = MagicMock()
        session.post.return_value.json.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        monkeypatch.setattr(
            "plistsync.core.auth.PlistsyncSession", lambda *args, **kwargs: session
        )

        token = provider.authenticate(interaction)

        assert token.as_dict()["access_token"] == "access"

        assert session.post.call_args.args[0] == provider.token_endpoint
        data = session.post.call_args.kwargs["data"]
        assert data["grant_type"] == "authorization_code"
        assert data["client_id"] == "client-id"
        assert data["code"] == "auth-code"
        assert data["redirect_uri"] == provider.redirect_uri()

        # The verifier sent to the token endpoint matches the challenge that
        # was advertised in the authorization URL (PKCE S256).
        challenge = parse_qs(urlparse(interaction.opened_urls[-1]).query)[
            "code_challenge"
        ][0]
        expected_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(data["code_verifier"].encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        assert challenge == expected_challenge

    def test_authenticate_wraps_exchange_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = FakeOAuth2Provider(ServiceConfig())
        session = MagicMock()
        session.post.side_effect = requests.RequestException("boom")
        monkeypatch.setattr(
            "plistsync.core.auth.PlistsyncSession", lambda *args, **kwargs: session
        )

        with pytest.raises(AuthenticationError, match="Failed to obtain token"):
            provider.authenticate(FakeInteraction(redirect=_oauth2_callback))

    @pytest.mark.parametrize(
        ("callback", "match"),
        [
            (None, "No callback received"),
            (
                "http://127.0.0.1/cb?error=access_denied&error_description=User+said+no",
                "User said no",
            ),
            ("http://127.0.0.1/cb?state=some-state", "Missing 'code' or 'state'"),
            ("http://127.0.0.1/cb?code=some-code&state=wrong", "state mismatch"),
        ],
    )
    def test_obtain_token_rejects_bad_callbacks(
        self, callback: str | None, match: str
    ) -> None:
        provider = FakeOAuth2Provider(ServiceConfig())
        request = provider.build_request()

        with pytest.raises(AuthenticationError, match=match):
            provider.obtain_token(request, callback)


def _write_oauth2_token(
    path: Path, *, expired: bool = False, refresh_token: str | None = None
) -> None:
    """Write a real Oauth2Token with an expiry hint in the past or future."""
    expires_at = datetime.now(UTC) + timedelta(hours=-1 if expired else 1)
    token = Oauth2Token(
        BearerToken(
            access_token="access",
            expires_at=expires_at,
            refresh_token=refresh_token,
        ),
        path,
    )
    token.save()


class TestAuthCheck:
    """Non-interactive authentication status checks."""

    @pytest.fixture
    def token_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        path = tmp_path / "token.json"
        monkeypatch.setattr(ServiceConfig, "token_path", property(lambda self: path))
        return path

    def test_missing_token(self, token_path: Path) -> None:
        assert FakeOAuth2Provider(ServiceConfig()).check_auth() is False

    def test_valid_token(self, token_path: Path) -> None:
        _write_oauth2_token(token_path)

        assert FakeOAuth2Provider(ServiceConfig()).check_auth() is True

    def test_expired_token_is_refreshed(
        self, token_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_oauth2_token(token_path, expired=True, refresh_token="refresh")
        oauth2_client = MagicMock()
        oauth2_client.return_value.refresh_token.return_value = BearerToken(
            access_token="new-access",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        monkeypatch.setattr("plistsync.core.auth.OAuth2Client", oauth2_client)

        assert FakeOAuth2Provider(ServiceConfig()).check_auth() is True
        assert Oauth2Token.from_file(token_path).as_dict()["access_token"] == (
            "new-access"
        )

    def test_failed_refresh(
        self, token_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_oauth2_token(token_path, expired=True, refresh_token="refresh")
        oauth2_client = MagicMock()
        oauth2_client.return_value.refresh_token.side_effect = (
            requests.RequestException("boom")
        )
        monkeypatch.setattr("plistsync.core.auth.OAuth2Client", oauth2_client)

        assert FakeOAuth2Provider(ServiceConfig()).check_auth() is False
