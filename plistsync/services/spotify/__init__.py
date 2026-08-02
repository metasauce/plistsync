from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="spotify",
    required_packages=["requests_oauth2client"],
)

from . import api
from .config import SpotifyConfig
from .library import SpotifyLibrary
from .playlist import SpotifyPlaylist, SpotifyPlaylistID
from .track import SpotifyPlaylistTrack, SpotifyTrack, SpotifyTrackID


class SpotifyService(Service):
    pass


__all__ = [
    "SpotifyConfig",
    "SpotifyLibrary",
    "SpotifyPlaylist",
    "SpotifyPlaylistID",
    "SpotifyPlaylistTrack",
    "SpotifyService",
    "SpotifyTrack",
    "SpotifyTrackID",
    "api",
]
