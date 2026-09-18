from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from plistsync.services.spotify.auth import SpotifyAuth
from plistsync.services.spotify.config import SpotifyConfig


class TestSpotifyAuth:
    """Spotify uses the generic OAuth2 provider with a custom redirect port."""

    @pytest.fixture
    def auth(self) -> SpotifyAuth:
        return SpotifyAuth(SpotifyConfig(client_id="my-client", redirect_port=5001))

    def test_registered_with_service(self, auth: SpotifyAuth) -> None:
        from plistsync.services.spotify import SpotifyService

        assert SpotifyService().auth() is SpotifyAuth

    def test_client_id_and_redirect_uri_come_from_config(
        self, auth: SpotifyAuth
    ) -> None:
        assert auth.client_id() == "my-client"
        assert auth.redirect_uri() == "http://127.0.0.1:5001"

    def test_build_request_targets_spotify(self, auth: SpotifyAuth) -> None:
        request = auth.build_request()

        assert request.url.startswith(SpotifyAuth.authorize_endpoint)
        params = parse_qs(urlparse(request.url).query)
        assert params["client_id"] == ["my-client"]
        assert params["scope"] == [SpotifyAuth.scopes]
        assert params["code_challenge_method"] == ["S256"]
        assert params["show_dialog"] == ["true"]

    def test_token_endpoint(self, auth: SpotifyAuth) -> None:
        assert auth.token_endpoint == "https://accounts.spotify.com/api/token"
