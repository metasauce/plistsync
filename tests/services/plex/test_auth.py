from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from plistsync.errors import AuthenticationError
from plistsync.services.plex.api import PlexToken
from plistsync.services.plex.auth import PlexAuth, PlexAuthRequest
from plistsync.services.plex.config import PlexConfig

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


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


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


class TestPlexAuth:
    """Plex authenticates via a pin the user confirms in the browser."""

    @pytest.fixture
    def auth(self) -> PlexAuth:
        return PlexAuth(PlexConfig(server_url="http://localhost:32400"))

    @pytest.fixture
    def session(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        session = MagicMock()
        monkeypatch.setattr(
            "plistsync.services.plex.auth.PlistsyncSession",
            lambda *args, **kwargs: session,
        )
        return session

    @pytest.fixture
    def auth_request(self) -> PlexAuthRequest:
        return PlexAuthRequest(
            url="https://app.plex.tv/auth#?code=pin-code",
            pin_id=42,
            redirect_uri="http://127.0.0.1:5001/",
        )

    def test_registered_with_service(self, auth: PlexAuth) -> None:
        from plistsync.services.plex import PlexService

        assert PlexService().auth() is PlexAuth

    def test_redirect_uri_uses_config_port(self, auth: PlexAuth) -> None:
        assert auth.redirect_uri() == "http://127.0.0.1:5001/"

    def test_build_request_creates_pin_and_auth_url(
        self, auth: PlexAuth, session: MagicMock
    ) -> None:
        session.post.return_value = _response({"id": 42, "code": "pin-code"})

        request = auth.build_request()

        assert session.post.call_args.args[0] == PlexAuth.pins_endpoint
        assert session.post.call_args.kwargs["json"] == {"strong": True}
        headers = session.post.call_args.kwargs["headers"]
        assert headers["X-Plex-Client-Identifier"] == auth.config.client_identifier
        assert headers["X-Plex-Product"] == auth.config.app_name

        assert request.pin_id == 42
        assert request.redirect_uri == auth.redirect_uri()
        params = parse_qs(urlparse(request.url).fragment.lstrip("?"))
        assert params["code"] == ["pin-code"]
        assert params["clientID"] == [auth.config.client_identifier]
        assert params["context[device][product]"] == [auth.config.app_name]
        assert params["forwardUrl"] == [auth.redirect_uri()]

    def test_build_request_wraps_request_errors(
        self, auth: PlexAuth, session: MagicMock
    ) -> None:
        session.post.side_effect = requests.RequestException("boom")

        with pytest.raises(AuthenticationError, match="Failed to create Plex pin"):
            auth.build_request()

    def test_collect_response_opens_url_and_captures_redirect(
        self, auth: PlexAuth, auth_request: PlexAuthRequest
    ) -> None:
        interaction = FakeInteraction(redirect="http://127.0.0.1:5001/?done")

        response = auth.collect_response(interaction, auth_request)

        assert response == "http://127.0.0.1:5001/?done"
        assert interaction.opened_urls == [auth_request.url]
        assert interaction.captured_uris == [auth_request.redirect_uri]
        assert interaction.messages == []

    def test_collect_response_without_redirect_shows_waiting_message(
        self, auth: PlexAuth, auth_request: PlexAuthRequest
    ) -> None:
        interaction = FakeInteraction(redirect=None)

        assert auth.collect_response(interaction, auth_request) is None
        assert interaction.messages != []

    def test_obtain_token_polls_until_token_is_available(
        self,
        auth: PlexAuth,
        session: MagicMock,
        auth_request: PlexAuthRequest,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(PlexAuth, "poll_interval", 0)
        session.get.side_effect = [
            _response({"id": 42}),
            _response({"id": 42, "authToken": "plex-auth-token"}),
        ]

        token = auth.obtain_token(auth_request, None)

        assert isinstance(token, PlexToken)
        assert token.x_plex_token == "plex-auth-token"
        assert session.get.call_count == 2
        assert session.get.call_args.args[0] == f"{PlexAuth.pins_endpoint}/42"
        headers = session.get.call_args.kwargs["headers"]
        assert headers["X-Plex-Client-Identifier"] == auth.config.client_identifier

    def test_obtain_token_raises_on_timeout(
        self,
        auth: PlexAuth,
        session: MagicMock,
        auth_request: PlexAuthRequest,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(PlexAuth, "poll_timeout", -1)
        session.get.return_value = _response({"id": 42})

        with pytest.raises(AuthenticationError, match="Timed out"):
            auth.obtain_token(auth_request, None)

    def test_obtain_token_wraps_request_errors(
        self, auth: PlexAuth, session: MagicMock, auth_request: PlexAuthRequest
    ) -> None:
        session.get.side_effect = requests.RequestException("boom")

        with pytest.raises(AuthenticationError, match="Failed to poll Plex pin"):
            auth.obtain_token(auth_request, None)

    def test_authenticate_runs_the_full_flow(
        self,
        auth: PlexAuth,
        session: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(PlexAuth, "poll_interval", 0)
        session.post.return_value = _response({"id": 42, "code": "pin-code"})
        session.get.return_value = _response({"authToken": "plex-auth-token"})
        interaction = FakeInteraction(redirect="http://127.0.0.1:5001/?done")

        token = auth.authenticate(interaction)

        assert token.x_plex_token == "plex-auth-token"
        assert interaction.opened_urls != []

    @pytest.mark.parametrize(("ok", "expected"), [(True, True), (False, False)])
    def test_check_auth(
        self,
        auth: PlexAuth,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        ok: bool,
        expected: bool,
    ) -> None:
        """Loads the persisted token and validates it against plex.tv."""
        token_file = tmp_path / "plex_token.json"
        token_file.write_text(json.dumps({"X-Plex-Token": "plex-auth-token"}))
        monkeypatch.setattr(PlexConfig, "token_path", property(lambda self: token_file))
        session = MagicMock()
        monkeypatch.setattr(
            "plistsync.services.plex.api.PlistsyncSession",
            lambda *args, **kwargs: session,
        )
        session.get.return_value = MagicMock(ok=ok)

        assert auth.check_auth() is expected
