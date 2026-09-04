from dataclasses import dataclass, field
from typing import Annotated

from plistsync.config import Config, ServiceConfig
from plistsync.utils.auth.bearer_token import Oauth2Token


@dataclass
class SpotifyConfig(ServiceConfig):
    """Configuration for the Spotify service."""

    client_id: Annotated[
        str,
        "The client ID for talking to the Spotify API. You can use the buildin one or"
        " obtain a new client ID by registering an Devleloper application.",
    ] = field(default="3b408bca2c3344dfa1cda1c7fa9adde4")

    client_secret: Annotated[
        str | None,
        "The client secret for talking to the Spotify API. Not required unless you want"
        " to use your own client.",
    ] = None

    def load_token(self) -> Oauth2Token:
        """Get a previously saved token for a user from the config directory.

        Use cli to authenticate a user and save the token to the config directory.
        """

        # TODO: We should be able to add multi user support
        # here somehow ;)
        return Oauth2Token.from_file(
            Config.get_dir() / "spotify_token.json",
        )
