from dataclasses import dataclass, field
from typing import Annotated

from plistsync.config import Config, ServiceConfig
from plistsync.utils.auth.bearer_token import Oauth2Token


@dataclass
class TidalConfig(ServiceConfig):
    client_id: Annotated[
        str,
        "The client ID for talking to the Tidal API. You can use the buildin one or"
        "obtain a new client ID by registering an Devleloper application.",
    ] = field(default="XhEgdcjkjfqTqw1y")

    client_secret: Annotated[
        str | None,
        "The client secret for talking to the Tidal API. Not required unless you want"
        "to use your own client.",
    ] = None

    country_code: Annotated[
        str,
        "The country code for the Tidal API. This is required for some endpoints. It"
        "influences track availability slightly.",
    ] = field(default="US")

    def load_token(self) -> Oauth2Token:
        """Get a previously saved token for a user from the config directory.

        Use cli to authenticate a user and save the token to the config directory.
        """

        # TODO: We should be able to add multi user support
        # here somehow ;)
        return Oauth2Token.from_file(
            Config.get_dir() / "tidal_token.json",
        )
