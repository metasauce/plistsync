from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="traktor",
    required_packages=["lxml"],
)

from .config import TraktorConfig
from .library import NMLLibrary
from .path import NMLPath
from .playlist import NMLPlaylist, NMLPlaylistID
from .track import NMLPlaylistTrack, NMLTrack


class TraktorService(Service):
    pass


__all__ = [
    "NMLLibrary",
    "NMLPath",
    "NMLPlaylist",
    "NMLPlaylistID",
    "NMLPlaylistTrack",
    "NMLTrack",
    "TraktorConfig",
    "TraktorService",
]
