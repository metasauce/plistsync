from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, Self

import nest_asyncio

from plistsync.core.collection import Collection, LibraryCollection
from plistsync.logger import log

from .api import get_playlist, get_user_playlists_full, get_user_playlists_simplified
from .track import SpotifyPlaylistPlaceholder, SpotifyPlaylistTrack

nest_asyncio.apply()


class SpotifyLibraryCollection(LibraryCollection):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    @property
    def playlists(self) -> Iterable[SpotifyPlaylistCollection]:
        """Get all playlists of the current user.

        This can take quite some time, as it fetches all playlists and their tracks.
        """
        return [
            SpotifyPlaylistCollection(playlist)
            for playlist in asyncio.run(get_user_playlists_full())
        ]

    def get_playlist(
        self, name: str | Path, allow_name=True
    ) -> SpotifyPlaylistCollection | None:
        """Get a specific playlist by its ID."""

        if isinstance(name, Path):
            raise ValueError("Playlist name cannot be a Path")

        plist_identifier: str = name

        # We want to be able to resolve names of playlists without fetching all playlists
        # We fetch all playlists by the user and check if the name matches first
        if allow_name:
            plists = asyncio.run(get_user_playlists_simplified())
            for plist in plists:
                if plist["name"] == plist_identifier:
                    plist_identifier = plist["id"]
                    break

        try:
            return asyncio.run(SpotifyPlaylistCollection.from_id(plist_identifier))
        except Exception as e:
            log.debug(f"Could not fetch playlist {name}: {e}")
            return None


class SpotifyPlaylistCollection(Collection):
    """A collection representing a spotify playlist."""

    data: dict

    tracks: list[SpotifyPlaylistTrack | SpotifyPlaylistPlaceholder] = []

    def __init__(self, data: dict):
        """Initialize a SpotifyPlaylistCollection from the given data.

        Expected data comes from the spotify API, e.g. from
        `GET /playlists/{playlist_id}`.
        """

        if data.get("type") != "playlist":
            raise ValueError(
                f"Data is not a Spotify playlist object, got type {data.get('type')}"
            )

        self.data = data

        items = data.get("tracks", {}).get("items", [])
        tracks = []
        for item in items:
            # It is possible to add episodes or other non-track items to a playlist
            # We add a placeholder to keep the order
            if item["track"]["type"] == "track":
                tracks.append(SpotifyPlaylistTrack(item))
            else:
                tracks.append(SpotifyPlaylistPlaceholder(item))

        self.tracks = tracks

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

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self.data["name"]

    @property
    def id(self) -> str:
        """The spotify ID of the playlist."""
        return self.data["id"]

    def __iter__(self) -> Iterable[SpotifyPlaylistTrack]:
        """Iterate over all tracks in the playlist.

        This does not include non-track items, which are skipped.
        """
        items = self.data.get("tracks", {}).get("items", [])
        for item in items:
            # It is possible to add episodes or other non-track items to a playlist
            # We add a placeholder to keep the order
            if item["track"]["type"] == "track":
                yield SpotifyPlaylistTrack(item)
            else:
                log.debug(
                    f"Skipping non-track item in playlist '{self.name}': {item['track']['type']}"
                )
