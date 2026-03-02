from plistsync.errors import check_imports

check_imports(
    service="spotify",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import SpotifyLibraryCollection
from .playlist import SpotifyPlaylistCollection
from .track import SpotifyPlaylistTrack, SpotifyTrack

__all__ = [
    "api",
    "SpotifyLibraryCollection",
    "SpotifyPlaylistCollection",
    "SpotifyPlaylistTrack",
    "SpotifyTrack",
]
