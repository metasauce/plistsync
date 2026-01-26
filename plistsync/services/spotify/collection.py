from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Self

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.core.playlist import PlaylistCollection
from plistsync.logger import log
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponse

from .api import SpotifyApi
from .track import SpotifyPlaylistTrack, SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    def __init__(self) -> None:
        self.api = SpotifyApi()

    @property
    def playlists(self) -> Iterable[SpotifyPlaylistCollection]:
        """Get all playlists of the current user.

        This can take quite some time, as it fetches all playlists and their tracks.
        """
        return [
            SpotifyPlaylistCollection(playlist)
            for playlist in self.api.user.get_playlists()
        ]

    def get_playlist(
        self, name: str | Path, allow_name=True
    ) -> SpotifyPlaylistCollection | None:
        """Get a specific playlist by its ID."""

        if isinstance(name, Path):
            raise ValueError("Playlist name cannot be a Path")

        plist_identifier: str = name

        # We fetch all playlists by the user and check if the name matches
        if allow_name:
            plists = self.api.user.get_playlists(True)
            for plist in plists:
                if plist["name"] == plist_identifier:
                    plist_identifier = plist["id"]
                    break

        try:
            return SpotifyPlaylistCollection(self.api.playlist.get(plist_identifier))
        except Exception as e:
            log.debug(f"Could not fetch playlist {name}: {e}")
            return None

    # ------------------------------- global lookup ------------------------------ #

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> SpotifyTrack | None:
        """Find a track by its global ID.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        """
        if spotify_id := global_ids.get("spotify_id"):
            try:
                return SpotifyTrack(self.api.track.get(spotify_id))
            except Exception as e:
                log.debug(f"Could not find track by spotify ID {spotify_id}: {e}")

        if isrc := global_ids.get("isrc"):
            try:
                return SpotifyTrack(self.api.track.get_by_isrc(isrc))
            except Exception as e:
                log.debug(f"Could not find track by ISRC {isrc}: {e}")

        return None

    def find_many_by_global_ids(
        self, global_ids_list: list[GlobalTrackIDs]
    ) -> Iterable[SpotifyTrack | None]:
        """Find many tracks by their global IDs.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        Performs batch lookup for all tracks with spotify_id if possible.
        """
        found_tracks: dict[int, SpotifyTrack] = {}

        # Get all with spotify id for batch lookup
        idxes = []
        spotify_ids: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if "spotify_id" in gids:
                idxes.append(idx)
                spotify_ids.append(gids["spotify_id"])

        if spotify_ids:
            tracks = self.api.track.get_many(spotify_ids)

            if len(spotify_ids) != len(tracks):
                log.warning(
                    f"Expected {len(spotify_ids)} tracks but received {len(tracks)} "
                    "tracks as result from spotify batch lookup."
                )

            for idx, track in zip(idxes, tracks):
                found_tracks[idx] = SpotifyTrack(track)

        # Individual lookup for all missing tracks
        for idx, gids in enumerate(global_ids_list):
            if idx in found_tracks:
                yield found_tracks[idx]
            else:
                yield self.find_by_global_ids(gids)


class SpotifyPlaylistCollection(PlaylistCollection[SpotifyPlaylistTrack]):
    """A collection representing a spotify playlist."""

    data: SpotifyApiPlaylistResponse
    api: SpotifyApi

    def __init__(self, data: SpotifyApiPlaylistResponse):
        """Initialize a SpotifyPlaylistCollection from the given data.

        Expected data comes from the spotify API, e.g. from
        `GET /playlists/{playlist_id}`.
        """

        if data.get("type") != "playlist":
            raise ValueError(
                f"Data is not a Spotify playlist object, got type {data.get('type')}"
            )

        self.data = data

    @classmethod
    def create_new(cls, name: str, description: str | None = None) -> Self:
        """Create a new empty Spotify playlist with the given name and description.

        Parameters
        ----------
        name : str
            The name of the new playlist.
        description : str | None
            The description of the new playlist.

        Returns
        -------
        SpotifyPlaylistCollection
            The created SpotifyPlaylistCollection.

        Raises
        ------
        ValueError
            If the playlist could not be created.
        """

        return cls(
            SpotifyApi().playlist.create(
                name,
                description or "Created by 'plistsync'",
            )
        )

    @classmethod
    def from_id(cls, playlist_id: str) -> Self:
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
        return cls(SpotifyApi().playlist.get(playlist_id))

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self.data["name"]

    @name.setter
    def name(self, value: str):
        raise NotImplementedError("Setter not implemented")

    @property
    def id(self) -> str:
        """The spotify ID of the playlist."""
        return self.data["id"]

    def tracks(self) -> Iterator[SpotifyPlaylistTrack]:
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
                    f"Skipping non-track item in playlist "
                    f"'{self.name}': {item['track']['type']}"
                )

    def __len__(self) -> int:
        return len(self.data.get("tracks", {}).get("items", []))

    def __getitem__(self, index: int) -> SpotifyPlaylistTrack:
        items = self.data.get("tracks", {}).get("items", [])
        item = items[index]
        if item["track"]["type"] == "track":
            return SpotifyPlaylistTrack(item)
        else:
            raise ValueError(
                f"Item at index {index} is not a track, but {item['track']['type']}"
            )

    def _remote_insert_track(self, idx: int, track: SpotifyPlaylistTrack) -> None:
        raise NotImplementedError("Insert not implemented")

    def _remote_delete_track(self, idx: int, track: SpotifyPlaylistTrack):
        raise NotImplementedError("Delete not implemented")

    def _remote_update_metadata(self, new_name=None, new_description=None):
        raise NotImplementedError("Update not implemented")

    @staticmethod
    def _track_key(track):
        return track.id
