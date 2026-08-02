from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated

from plistsync.config import Config, ServiceConfig

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class PlexConfig(ServiceConfig):
    server_url: Annotated[
        str | None,
        "The URL of the Plex server to connect to by default.",
        "E.g. 'http://localhost:32400' or 'https://plex.mydomain.com'",
    ] = field(default=None)

    server_name: Annotated[
        str | None,
        "Instead of the server url, you can specify its name and we look it up online ",
        "via plex.tv. In this case, we try local routes first.",
        "E.g. 'my_plex_server'",
    ] = field(default=None)

    @property
    def app_name(self) -> str:
        return "plistsync-local"

    @property
    def client_identifier(self) -> str:
        # Random generated UUID, we could generate this for each
        # user but it is not strictly necessary and one global
        # id might allow us profiling across installs in the future.
        return "510457cfb15e4bf48d34563d0e4f1de1"

    @property
    def token_path(self) -> Path:
        return Config.get_dir() / "plex_token.json"
