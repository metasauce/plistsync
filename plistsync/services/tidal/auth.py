from __future__ import annotations

from typing import TYPE_CHECKING

from plistsync.core.auth import OAuth2Provider

if TYPE_CHECKING:
    from .config import TidalConfig


class TidalAuth(OAuth2Provider):
    """Obtain an initial Tidal access/refresh token via PKCE."""

    config: TidalConfig
    authorize_endpoint = "https://login.tidal.com/authorize"
    token_endpoint = "https://auth.tidal.com/v1/oauth2/token"
    scopes = " ".join(
        [
            "playlists.read",
            "playlists.write",
            "search.read",
            "collection.read",
            "collection.write",
            "user.read",
        ]
    )

    def client_id(self) -> str:
        return self.config.client_id

    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.config.redirect_port}"
