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

    redirect_port: Annotated[
        int,
        "The port to use for the local redirect server when authenticating. If using "
        "the default Spotify client ID, this must be 20556, as is the port whitelisted"
        "by the app.",
    ] = field(default=20556)

    def load_token(self) -> Oauth2Token:
        """Get a previously saved token for a user from the config directory.

        Use cli to authenticate a user and save the token to the config directory.
        """

        # TODO: We should be able to add multi user support
        # here somehow ;)
        return Oauth2Token.from_file(
            Config.get_dir() / "spotify_token.json",
        )
