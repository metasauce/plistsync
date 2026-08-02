from dataclasses import dataclass, field
from typing import Annotated

from plistsync.config import ServiceConfig


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
