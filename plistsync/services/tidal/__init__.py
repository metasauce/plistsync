from plistsync.errors import check_imports

check_imports(
    service="tidal",
    required_packages=["requests_oauth2client"],
)

from . import api
from .collection import TidalLibraryCollection, TidalPlaylistCollection
from .track import TidalTrack

__all__ = [
    "TidalTrack",
    "api",
    "TidalLibraryCollection",
    "TidalPlaylistCollection",
]
