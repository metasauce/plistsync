from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="traktor",
    required_packages=["lxml"],
)

from .library import NMLLibrary
from .path import NMLPath
from .playlist import NMLPlaylist, NMLPlaylistID
from .track import NMLPlaylistTrack, NMLTrack


class TraktorService(Service):
    library_cls = NMLLibrary
    playlist_cls = NMLPlaylist
    track_cls = NMLTrack
    playlist_id_cls = NMLPlaylistID


__all__ = [
    "NMLLibrary",
    "NMLPath",
    "NMLPlaylist",
    "NMLPlaylistID",
    "NMLPlaylistTrack",
    "NMLTrack",
    "TraktorService",
]
