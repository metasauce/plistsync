from dataclasses import dataclass, field
from typing import Annotated

from plistsync.core.config import ServiceConfig


@dataclass
class TidalConfig(ServiceConfig):
    client_id: Annotated[
        str,
        "The client ID for talking to the Tidal API. You can use the buildin one or"
        "obtain a new client ID by registering an Devleloper application.",
    ] = field(default="XhEgdcjkjfqTqw1y")

    redirect_port: Annotated[
        int,
        "The port to use for the local redirect server when authenticating. If using "
        "the default Tidal client ID, this must be 20556, as is the port whitelisted by"
        "our public client.",
    ] = field(default=20556)

    country_code: Annotated[
        str,
        "The country code for the Tidal API. This is required for some endpoints. It"
        "influences track availability slightly.",
    ] = field(default="US")
