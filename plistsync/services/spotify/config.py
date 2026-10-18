from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import SecretStr

from plistsync.core.config import DataIO, ServiceConfig
from plistsync.utils.auth.oauth2 import OAuth2Token

_DEFAULT_CLIENT_ID = "3b408bca2c3344dfa1cda1c7fa9adde4"
_DEFAULT_REDIRECT_PORT = 20556


@dataclass(init=False)
class SpotifyConfig(ServiceConfig):
    """Configuration for the Spotify service."""

    client_id: Annotated[
        str,
        "The client ID for talking to the Spotify API. You can use the buildin one or"
        " obtain a new client ID by registering an Devleloper application.",
    ] = field(default=_DEFAULT_CLIENT_ID)

    redirect_port: Annotated[
        int,
        "The port to use for the local redirect server when authenticating. If using "
        "the default Spotify client ID, this must be 20556, as is the port whitelisted"
        "by the app.",
    ] = field(default=_DEFAULT_REDIRECT_PORT)

    token: DataIO[OAuth2Token] | OAuth2Token | None = field(default=None)

    def __init__(
        self,
        client_id: str = _DEFAULT_CLIENT_ID,
        redirect_port: int = _DEFAULT_REDIRECT_PORT,
        token: DataIO[OAuth2Token] | OAuth2Token | str | None = None,
    ) -> None:
        """Initialize the config, normalizing the token."""
        self.client_id = client_id
        self.redirect_port = redirect_port
        if isinstance(token, str):
            token = OAuth2Token(access_token=SecretStr(token))
        # Store the raw field: a DataIO is kept as-is instead of using token.__set__
        object.__setattr__(self, "token", token)
