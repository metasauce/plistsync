from dataclasses import dataclass, field
from typing import Annotated

from plistsync.core.config import ServiceConfig


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
