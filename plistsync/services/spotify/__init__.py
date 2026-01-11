from plistsync.errors import check_imports

check_imports(
    service="spotify",
    required_packages=["nest_asyncio", "requests_oauth2client"],
)

from .collection import SpotifyLibraryCollection, SpotifyPlaylistCollection
from .track import SpotifyPlaylistTrack, SpotifyTrack

__all__ = [
    "SpotifyLibraryCollection",
    "SpotifyPlaylistCollection",
    "SpotifyPlaylistTrack",
    "SpotifyTrack",
]
