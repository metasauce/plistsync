from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import SecretStr

from plistsync.core.config import DataIO, ServiceConfig

from .api import PlexToken

_DEFAULT_SECTION = "Music"
_DEFAULT_REDIRECT_PORT = 20556


@dataclass
class PlexConfig(ServiceConfig):
    """Configuration for the Plex service."""

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

    section_name_or_id: Annotated[
        str | int,
        "The name or ID of the Plex library section to use by default.",
    ] = field(default=_DEFAULT_SECTION)

    redirect_port: Annotated[
        int,
        "The port to use for the local redirect server when authenticating.",
    ] = field(default=_DEFAULT_REDIRECT_PORT)

    token: DataIO[PlexToken] | PlexToken | None = field(default=None)

    @property
    def app_name(self) -> str:
        return "plistsync"

    @property
    def client_identifier(self) -> str:
        # Random generated UUID, we could generate this for each
        # user but it is not strictly necessary and one global
        # id might allow us profiling across installs in the future.
        return "510457cfb15e4bf48d34563d0e4f1de1"

    def __init__(
        self,
        server_url: str | None = None,
        server_name: str | None = None,
        section_name_or_id: str | int = _DEFAULT_SECTION,
        redirect_port: int = _DEFAULT_REDIRECT_PORT,
        token: DataIO[PlexToken] | PlexToken | str | None = None,
    ) -> None:
        """Initialize the config, normalizing the token.

        ``token`` may be a ``str`` (parsed into a :class:`PlexToken`), a
        :class:`DataIO` (used as the token source), or a :class:`PlexToken`.
        """
        self.server_url = server_url
        self.server_name = server_name
        self.section_name_or_id = section_name_or_id
        self.redirect_port = redirect_port
        if isinstance(token, str):
            token = PlexToken(x_plex_token=SecretStr(token))
        # Set the raw field: a DataIO is kept as-is instead of being routed
        # through DataIO.__set__ (which would treat it as token data).
        object.__setattr__(self, "token", token)
