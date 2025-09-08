from typing import Iterable

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import GlobalLookup, LibraryCollection

from .track import SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> SpotifyTrack | None:
        raise NotImplementedError("SpotifyLibraryCollection is not implemented yet")

    @property
    def playlists(self) -> Iterable["SpotifyPlaylistCollection"]:
        raise NotImplementedError("SpotifyLibraryCollection is not implemented yet")


class SpotifyPlaylistCollection(LibraryCollection):
    """A collection representing a spotify playlist."""

    def add(self, track: SpotifyTrack) -> None:
        raise NotImplementedError("SpotifyPlaylistCollection is not implemented yet")

    def remove(self, track: SpotifyTrack) -> None:
        raise NotImplementedError("SpotifyPlaylistCollection is not implemented yet")
