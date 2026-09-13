"""Tests for the core authentication abstraction."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest

from plistsync.config import ServiceConfig
from plistsync.core.auth import AuthProvider, OAuth2Provider
from plistsync.utils.auth.bearer_token import Token

if TYPE_CHECKING:
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
    """In-memory implementation of the Interaction protocol."""

    def __init__(self) -> None:
        self.opened_urls: list[str] = []

    def open_url(self, url: str) -> None:
        self.opened_urls.append(url)

    def show(self, message: str) -> None:
        pass

    def ask(self, message: str) -> str:
        return ""

    def capture_redirect(self, redirect_uri: str) -> str | None:
        return None


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
