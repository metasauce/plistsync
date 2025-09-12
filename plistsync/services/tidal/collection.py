from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, Iterator, Self

import nest_asyncio

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LibraryCollection,
    TrackStream,
)
from plistsync.logger import log

from .api import get_playlist

nest_asyncio.apply()

class TidalLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection of Tidal library items."""

    @property
    def playlists(self) -> Iterable[TidalPlaylistCollection]:
        raise NotImplementedError("Tidal playlists not implemented yet")


class TidalPlaylistCollection(Collection, TrackStream):

    data: dict

    def __init__(self, data: dict):
        """Initialize the TidalPlaylistCollection from a Tidal API playlist object.

        Expects data from
        /userCollections/{user_id}/relationships/playlists
        """

        if data.get("type") != "playlists":
            raise ValueError(
                f"Data is not a Tidal playlist object, got type {data.get('type')}"
            )

        self.data = data

    @classmethod
    async def from_id(cls, playlist_id: str) -> Self:
        """Create a TidalPlaylistCollection from a tidal playlist ID.

        Parameters
        ----------
        playlist_id : str
            The playlist ID.

        Returns
        -------
        TidalPlaylistCollection
            The created TidalPlaylistCollection.

        Raises
        ------
        ValueError
            If the playlist ID is invalid or not found.
        """
        data = await get_playlist(playlist_id)
        return cls(data)

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self.data["attributes"]["name"]

    @property
    def id(self) -> str:
        """The tidal ID of the playlist."""
        return self.data["id"]

    def __iter__(self) -> Iterator[TidalPlaylistTrack]:
        """Iterate over all tracks in the playlist.

        This does not include non-track items, which are skipped.
        """
        items = self.data.get("tracks", {}).get("items", [])
        for item in items:
            # It is possible to add episodes or other non-track items to a playlist
            # We add a placeholder to keep the order
            if item["track"]["type"] == "track":
                yield TidalPlaylistTrack(item)
            else:
                log.debug(
                    f"Skipping non-track item in playlist '{self.name}': {item['track']['type']}"
                )
