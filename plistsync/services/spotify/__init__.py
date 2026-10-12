from plistsync.services import Service

from . import api
from .auth import SpotifyAuth
from .config import SpotifyConfig
from .library import SpotifyLibrary
from .playlist import SpotifyPlaylist, SpotifyPlaylistID
from .track import SpotifyPlaylistTrack, SpotifyTrack, SpotifyTrackID


class SpotifyService(Service):
    pass


__all__ = [
    "SpotifyAuth",
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
