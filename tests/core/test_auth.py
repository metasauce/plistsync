"""Tests for the core authentication abstraction."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from pydantic import ValidationError

from plistsync.core.auth import AuthProvider, Token
from plistsync.core.config import JsonFileIO, ServiceConfig
from plistsync.errors import AuthenticationError
from plistsync.utils.auth.oauth2 import OAuth2Provider, OAuth2Token
from tests.core.mock_auth import FakeInteraction

if TYPE_CHECKING:
    from pathlib import Path

    from plistsync.core.auth import Interaction


class FakeToken(Token):
    """Minimal token for testing the provider flow."""

    def __call__(self, request):
        return request


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


@pytest.fixture
def oauth_session(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the HTTP session used by the provider and by token refresh."""
    session = MagicMock()
    monkeypatch.setattr(
        "plistsync.utils.auth.oauth2.PlistsyncSession", lambda *args, **kwargs: session
    )
    return session


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


class TestOAuth2Provider:
    """The PKCE authorization-code flow, end to end."""

    def test_authenticate_exchanges_code_for_token(
        self, oauth_session: MagicMock
    ) -> None:
        provider = FakeOAuth2Provider(ServiceConfig())
        interaction = FakeInteraction(redirect=_oauth2_callback)
        oauth_session.post.return_value.json.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        token = provider.authenticate(interaction)

        assert token.access_token.get_secret_value() == "access"

        assert oauth_session.post.call_args.args[0] == provider.token_endpoint
        data = oauth_session.post.call_args.kwargs["data"]
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

    def test_authenticate_wraps_exchange_errors(self, oauth_session: MagicMock) -> None:
        provider = FakeOAuth2Provider(ServiceConfig())
        oauth_session.post.side_effect = requests.RequestException("boom")

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


def _oauth2_token(
    *, expired: bool = False, refresh_token: str | None = None
) -> OAuth2Token:
    """An OAuth2 token whose expiry lies in the past or the future."""
    return OAuth2Token(
        access_token="access",
        expires_at=datetime.now(UTC) + timedelta(hours=-1 if expired else 1),
        refresh_token=refresh_token,
    )


def _config(tmp_path: Path, *, token: OAuth2Token | None = None) -> ServiceConfig:
    """A config whose ``token`` field persists to ``tmp_path`` as JSON."""
    config = ServiceConfig()
    config.token = JsonFileIO[OAuth2Token](tmp_path / "token.json")
    if token is not None:
        config.token = token
    return config


class TestAuthCheck:
    """Non-interactive authentication status checks."""

    def test_missing_token(self, tmp_path: Path) -> None:
        assert FakeOAuth2Provider(_config(tmp_path)).check_auth() is False

    def test_valid_token(self, tmp_path: Path) -> None:
        config = _config(tmp_path, token=_oauth2_token())

        assert FakeOAuth2Provider(config).check_auth() is True

    def test_expired_token_is_refreshed(
        self, tmp_path: Path, oauth_session: MagicMock
    ) -> None:
        config = _config(
            tmp_path, token=_oauth2_token(expired=True, refresh_token="refresh")
        )
        oauth_session.post.return_value.json.return_value = {
            "access_token": "new-access",
            "expires_in": 3600,
        }

        assert FakeOAuth2Provider(config).check_auth() is True
        assert json.loads((tmp_path / "token.json").read_text())["access_token"] == (
            "new-access"
        )
        assert oauth_session.post.call_args.args[0] == FakeOAuth2Provider.token_endpoint
        assert (
            oauth_session.post.call_args.kwargs["data"]["grant_type"] == "refresh_token"
        )

    def test_failed_refresh(self, tmp_path: Path, oauth_session: MagicMock) -> None:
        config = _config(
            tmp_path, token=_oauth2_token(expired=True, refresh_token="refresh")
        )
        oauth_session.post.side_effect = requests.RequestException("boom")

        assert FakeOAuth2Provider(config).check_auth() is False


class TestOAuth2TokenSecrets:
    """Secret fields are masked in repr/errors but revealed on serialization."""

    @pytest.fixture
    def token(self) -> OAuth2Token:
        return OAuth2Token(access_token="secret-access", refresh_token="secret-refresh")

    def test_repr_masks_secrets(self, token: OAuth2Token) -> None:
        rendered = repr(token)

        assert "secret-access" not in rendered
        assert "secret-refresh" not in rendered

    def test_serialization_reveals_secrets(self, token: OAuth2Token) -> None:
        payload = token.model_dump(mode="json")

        assert payload["access_token"] == "secret-access"
        assert payload["refresh_token"] == "secret-refresh"

    def test_validation_error_does_not_leak_secret(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            OAuth2Token(access_token="secret-access", expires_at="not-a-date")

        assert "secret-access" not in str(excinfo.value)
        assert "secret-access" not in excinfo.value.json()
