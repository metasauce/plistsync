from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="tidal",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import TidalLibrary
from .playlist import TidalPlaylist, TidalPlaylistID
from .track import TidalPlaylistTrack, TidalTrack, TidalTrackID


class TidalService(Service):
    pass


__all__ = [
    "TidalLibrary",
    "TidalPlaylist",
    "TidalPlaylistID",
    "TidalPlaylistTrack",
    "TidalService",
    "TidalTrack",
    "TidalTrackID",
    "api",
]
