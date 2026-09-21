from __future__ import annotations

from typing import TYPE_CHECKING

from plistsync.core.auth import OAuth2Provider

if TYPE_CHECKING:
    from .config import SpotifyConfig


class SpotifyAuth(OAuth2Provider):
    """Obtain an initial Spotify access/refresh token via PKCE."""

    config: SpotifyConfig
    authorize_endpoint = "https://accounts.spotify.com/authorize"
    token_endpoint = "https://accounts.spotify.com/api/token"
    scopes = " ".join(
        [
            "playlist-read-private",
            "playlist-read-collaborative",
            "playlist-modify-private",
            "playlist-modify-public",
        ]
    )

    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.config.redirect_port}"

    def client_id(self) -> str:
        return self.config.client_id

    @property
    def extra_authorize_params(self) -> dict[str, str]:
        return {"show_dialog": "true"}
