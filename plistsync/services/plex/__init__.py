from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="plex",
    required_packages=["nest_asyncio"],
)

from . import api
from .library import PlexLibrary
from .playlist import PlexPlaylist
from .track import PlexTrack


class PlexService(Service):
    library_cls = PlexLibrary
    track_cls = PlexTrack
    playlist_cls = PlexPlaylist


__all__ = [
    "PlexLibrary",
    "PlexPlaylist",
    "PlexService",
    "PlexTrack",
    "api",
]
