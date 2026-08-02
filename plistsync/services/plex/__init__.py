from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="plex",
    required_packages=["nest_asyncio"],
)

from . import api
from .config import PlexConfig
from .library import PlexLibrary
from .playlist import PlexPlaylist, PlexPlaylistID
from .track import PlexTrack, PlexTrackID


class PlexService(Service):
    pass


__all__ = [
    "PlexConfig",
    "PlexLibrary",
    "PlexPlaylist",
    "PlexPlaylistID",
    "PlexService",
    "PlexTrack",
    "PlexTrackID",
    "api",
]
