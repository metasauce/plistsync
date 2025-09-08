from __future__ import annotations

from typing import Iterable, Self

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import Collection, GlobalLookup, LibraryCollection

from .api import get_playlist
from .track import SpotifyPlaylistTrack, SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> SpotifyTrack | None:
        raise NotImplementedError("SpotifyLibraryCollection is not implemented yet")

    @property
    def playlists(self) -> Iterable[SpotifyPlaylistCollection]:
        raise NotImplementedError("SpotifyLibraryCollection is not implemented yet")


class SpotifyPlaylistCollection(Collection):
    """A collection representing a spotify playlist."""

    tracks: list[SpotifyPlaylistTrack] = []

    def __init__(self, data: dict):
        """Initialize a SpotifyPlaylistCollection from the given data.

        Expected data comes from the spotify API, e.g. from
        `GET /playlists/{playlist_id}`.
        """
        items = data.get("tracks", {}).get("items", [])
        self.tracks = [SpotifyPlaylistTrack(item) for item in items]

    @classmethod
    async def from_id(cls, playlist_id: str) -> Self:
        """Create a SpotifyPlaylistCollection from a spotify playlist ID.

        Parameters
        ----------
        playlist_id : str
            The spotify playlist ID.

        Returns
        -------
        SpotifyPlaylistCollection
            The created SpotifyPlaylistCollection.

        Raises
        ------
        ValueError
            If the playlist ID is invalid or not found.
        """
        data = await get_playlist(playlist_id)
        return cls(data)
