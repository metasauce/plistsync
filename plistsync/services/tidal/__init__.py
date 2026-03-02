from plistsync.errors import check_imports

check_imports(
    service="tidal",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import TidalLibraryCollection
from .playlist import TidalPlaylistCollection
from .track import TidalPlaylistTrack, TidalTrack

__all__ = [
    "api",
    "TidalTrack",
    "TidalPlaylistTrack",
    "TidalLibraryCollection",
    "TidalPlaylistCollection",
]
