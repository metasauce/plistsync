from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Self

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LibraryCollection,
    TrackStream,
)
from plistsync.logger import log

from .api import LookupDict, TidalApi
from .api_types import PlaylistResource, PlaylistsItemsResourceIdentifier, TrackResource
from .track import TidalPlaylistTrack, TidalTrack


class TidalLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection of Tidal library items."""

    api: TidalApi

    def __init__(self) -> None:
        super().__init__()
        self.api = TidalApi()

    @property
    def playlists(self) -> Iterable[TidalPlaylistCollection]:
        playlists, lookup = self.api.playlist.get_many_by_user(self.api.user.me()["id"])
        return [TidalPlaylistCollection(pl, lookup) for pl in playlists]

    def get_playlist(
        self, name: str | Path, allow_name=True
    ) -> TidalPlaylistCollection | None:
        """Get a specific playlist by its ID.

        If name is given and allow_name is True, the name will be resolved to an ID
        by fetching all playlists of the user and checking if the name matches.
        """

        if isinstance(name, Path):
            raise ValueError("Playlist name cannot be a Path")

        plist_identifier: str = name

        # We fetch all playlists by the user and check if the name matches
        if allow_name:
            playlists, _ = self.api.playlist.get_many_by_user(
                self.api.user.me()["id"], include=[]
            )
            for pl in playlists:
                if pl["attributes"]["name"] == name:
                    plist_identifier = pl["id"]
                    break

        try:
            return TidalPlaylistCollection(*self.api.playlist.get(plist_identifier))
        except Exception as e:
            log.debug(f"Could not fetch playlist {name}: {e}")
            return None

    def has_playlist(self, name: str) -> bool:
        """Check if a playlist with the given name exists in the user's library."""
        for pl in self.api.playlist.get_many_by_user(
            self.api.user.me()["id"], include=[]
        )[0]:
            if pl["attributes"]["name"] == name:
                return True
        return False

    def create_playlist(
        self, name: str, description: str | None = None
    ) -> TidalPlaylistCollection:
        """Create a new playlist in the user's library."""
        try:
            return TidalPlaylistCollection(*self.api.playlist.create(name, description))
        except Exception as e:
            log.debug(f"Could not create playlist {name}: {e}")
            raise

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> TidalTrack | None:
        """Find a track by its global IDs.

        Prioritizes isrc lookups over spotify_id lookups.
        """
        return list(self.find_many_by_global_ids([global_ids]))[0]

    def find_many_by_global_ids(
        self, global_ids_list: Iterable[GlobalTrackIDs]
    ) -> Iterable[TidalTrack | None]:
        """Find many tracks by their global IDs.

        Prioritizes isrc lookups over spotify_id lookups.
        """
        global_ids_list = list(global_ids_list)
        found_tracks: dict[int, TidalTrack] = {}

        # Tidal ids lookup (batched)
        idx_tidal_pairs: dict[int, str] = {}
        for idx, gids in enumerate(global_ids_list):
            if tidal_id := gids.get("tidal_id"):
                idx_tidal_pairs[idx] = tidal_id

        if idx_tidal_pairs:
            tracks_data, lookup = self.api.tracks.get_many(
                list(idx_tidal_pairs.values())
            )
            for orig_idx, track_data in zip(idx_tidal_pairs.keys(), tracks_data):
                if track_data:
                    found_tracks[orig_idx] = TidalTrack(track_data, lookup)

        # Isrcs lookup if no tidal_id was found
        idx_isrc_pairs: dict[int, str] = {}
        for idx, gids in enumerate(global_ids_list):
            if idx not in found_tracks and (isrc := gids.get("isrc")):
                idx_isrc_pairs[idx] = isrc

        if idx_isrc_pairs:
            tracks_data, lookup = self.api.tracks.get_many_by_isrc(
                list(idx_isrc_pairs.values())
            )
            for idx, track_data in zip(idx_isrc_pairs.keys(), tracks_data):
                if track_data:
                    found_tracks[idx] = TidalTrack(track_data, lookup)

        for idx in range(len(global_ids_list)):
            yield found_tracks.get(idx)


class TidalPlaylistCollection(Collection, TrackStream):
    data: PlaylistResource
    data_lookup: LookupDict

    def __init__(self, data: PlaylistResource, data_lookup: LookupDict | None = None):
        """Initialize the TidalPlaylistCollection from a Tidal API playlist object.

        Expects data from
        /userCollections/{user_id}/relationships/playlists
        """

        if data.get("type") != "playlists":
            raise ValueError(
                f"Data is not a Tidal playlist object, got type {data.get('type')}"
            )

        self.data = data
        self.data_lookup = data_lookup or {}

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self.data["attributes"]["name"]

    @property
    def id(self) -> str:
        """The tidal ID of the playlist."""
        return self.data["id"]

    @property
    def description(self) -> str | None:
        """The description of the playlist, if available."""
        return self.data["attributes"].get("description")

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
        plist, lookup = TidalApi().playlist.get(playlist_id)
        return cls(plist, lookup)

    # ---------------------------------------------------------------------------- #
    #                        Helper methods (tidal specific)                       #
    # ---------------------------------------------------------------------------- #

    @property
    def _items_raw(self) -> list[PlaylistsItemsResourceIdentifier]:
        return [
            item
            for item in self.data.get("relationships", {})
            .get("items", {})
            .get("data", [])
        ]

    def _track_data_included(
        self, track_id: str
    ) -> tuple[TrackResource, LookupDict] | None:
        lookup = {}
        if track_data := self.data_lookup.get(("tracks", track_id)):
            for type, rel in track_data.get("relationships", {}).items():
                for item in rel.get("data", []):
                    if lookup_data := self.data_lookup.get((type, item["id"])):
                        lookup[(type, item["id"])] = lookup_data
                    else:
                        log.debug(
                            f"Related item of type '{type}' with id '{item['id']}' not"
                            " found in included data of playlist '{self.name}'"
                        )
                        # TODO: trigger a new tech if not in lookup
            return track_data, lookup
        return None

    # ---------------------------------------------------------------------------- #
    #                                 ABC methods                                  #
    # ---------------------------------------------------------------------------- #

    def __iter__(self) -> Iterator[TidalPlaylistTrack]:
        """Iterate over all tracks in the playlist.

        This does not include non-track items, which are skipped.
        """
        for item in self._items_raw:
            # It is possible to add episodes or other non-track items to a playlist
            # We add a placeholder to keep the order
            if item["type"] != "tracks":
                log.debug(
                    f"Skipping non-track item in playlist'{self.name}': {item['type']}"
                )
                continue

            if track_data := self._track_data_included(item["id"]):
                yield TidalPlaylistTrack(
                    track_data[0],
                    data_lookup=track_data[1],
                    added_at=item.get("meta", {}).get("addedAt", ""),
                )
            else:
                log.debug(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{self.name}'"
                )

    def __len__(self) -> int:
        """Return the number of tracks in the playlist."""
        return len(self._items_raw)
