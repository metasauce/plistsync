from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="spotify",
    required_packages=["requests_oauth2client"],
)

from . import api
from .library import SpotifyLibrary
from .playlist import SpotifyPlaylist, SpotifyPlaylistID
from .track import SpotifyPlaylistTrack, SpotifyTrack


class SpotifyService(Service):
    library_cls = SpotifyLibrary
    track_cls = SpotifyTrack
    playlist_cls = SpotifyPlaylist
    playlist_id_cls = SpotifyPlaylistID


__all__ = [
    "SpotifyLibrary",
    "SpotifyPlaylist",
    "SpotifyPlaylistID",
    "SpotifyPlaylistTrack",
    "SpotifyService",
    "SpotifyTrack",
    "api",
]
