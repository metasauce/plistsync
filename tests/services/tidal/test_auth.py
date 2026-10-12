from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from plistsync.services.tidal.auth import TidalAuth
from plistsync.services.tidal.config import TidalConfig


class TestTidalAuth:
    """Tidal uses the generic OAuth2 provider."""

    @pytest.fixture
    def auth(self) -> TidalAuth:
        return TidalAuth(TidalConfig(client_id="my-client", redirect_port=5001))

    def test_registered_with_service(self, auth: TidalAuth) -> None:
        from plistsync.services.tidal import TidalService

        assert TidalService().auth() is TidalAuth

    def test_client_id_and_redirect_uri(self, auth: TidalAuth) -> None:
        assert auth.client_id() == "my-client"
        assert auth.redirect_uri() == "http://127.0.0.1:5001"

    def test_build_request_targets_tidal(self, auth: TidalAuth) -> None:
        request = auth.build_request()

        assert request.url.startswith(TidalAuth.authorize_endpoint)
        params = parse_qs(urlparse(request.url).query)
        assert params["client_id"] == ["my-client"]
        assert params["scope"] == [TidalAuth.scopes]
        assert params["code_challenge_method"] == ["S256"]
        assert "show_dialog" not in params

    def test_token_endpoint(self, auth: TidalAuth) -> None:
        assert auth.token_endpoint == "https://auth.tidal.com/v1/oauth2/token"
