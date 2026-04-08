from plistsync.errors import check_imports

check_imports(
    service="tidal",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import TidalLibrary
from .playlist import TidalPlaylist
from .track import TidalPlaylistTrack, TidalTrack

__all__ = [
    "api",
    "TidalTrack",
    "TidalPlaylistTrack",
    "TidalLibrary",
    "TidalPlaylist",
]
