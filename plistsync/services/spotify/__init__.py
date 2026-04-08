from plistsync.errors import check_imports

check_imports(
    service="spotify",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import SpotifyLibrary
from .playlist import SpotifyPlaylist
from .track import SpotifyPlaylistTrack, SpotifyTrack

__all__ = [
    "api",
    "SpotifyLibrary",
    "SpotifyPlaylist",
    "SpotifyPlaylistTrack",
    "SpotifyTrack",
]
