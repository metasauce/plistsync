from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Self

import nest_asyncio

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LibraryCollection,
    TrackStream,
)
from plistsync.logger import log

from .api import (
    LookupDict,
    add_tracks_to_playlist,
    create_playlist,
    get_playlist,
    get_tracks,
    get_tracks_by_isrc,
    get_user_playlists,
)
from .track import TidalPlaylistTrack, TidalTrack

nest_asyncio.apply()


class TidalLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection of Tidal library items."""

    @property
    def playlists(self) -> Iterable[TidalPlaylistCollection]:
        return [
            TidalPlaylistCollection(pl, lookup)
            for pl, lookup in asyncio.run(get_user_playlists())
        ]

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
            for pl, lookup in asyncio.run(get_user_playlists(include_items=False)):
                if pl["attributes"]["name"] == name:
                    plist_identifier = pl["id"]
                    break

        try:
            return asyncio.run(TidalPlaylistCollection.from_id(plist_identifier))
        except Exception as e:
            log.debug(f"Could not fetch playlist {name}: {e}")
            return None

    def has_playlist(self, name: str) -> bool:
        """Check if a playlist with the given name exists in the user's library."""
        for pl, _ in asyncio.run(get_user_playlists(include_items=False)):
            if pl["attributes"]["name"] == name:
                return True
        return False

    def create_playlist(
        self, name: str, description: str = ""
    ) -> TidalPlaylistCollection:
        """Create a new playlist in the user's library."""
        try:
            data, included = asyncio.run(create_playlist(name, description=description))
            return TidalPlaylistCollection(data, included)
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
        found_tracks: dict[int, tuple[dict, LookupDict]] = {}
        global_ids_list = list(global_ids_list)

        # Get all ids/isrcs for batch lookup
        idxes: list[int] = []
        tidal_ids: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if tidal_id := gids.get("tidal_id"):
                idxes.append(idx)
                tidal_ids.append(tidal_id)

        for track_data, track_lookup in asyncio.run(get_tracks(tidal_ids=tidal_ids)):
            track_id = str(track_data["id"])
            try:
                idx = tidal_ids.index(track_id)
                found_tracks[idxes[idx]] = (track_data, track_lookup)
            except ValueError:
                log.debug(f"Received unknown track id from Tidal API: {track_id}")

        # Resolve isrcs if no tidal_id was found
        idxes = []
        isrcs: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if idx in found_tracks:
                continue
            if isrc := gids.get("isrc"):
                idxes.append(idx)
                isrcs.append(isrc)

        for track_data, track_lookup in asyncio.run(get_tracks_by_isrc(isrcs=isrcs)):
            if track_isrc := track_data.get("attributes", {}).get("isrc"):
                try:
                    idx = isrcs.index(track_isrc)
                    found_tracks[idxes[idx]] = (track_data, track_lookup)
                except ValueError:
                    log.debug(
                        f"Received unknown track isrc from Tidal API: {track_isrc}"
                    )

        for idx in range(len(global_ids_list)):
            if idx in found_tracks:
                yield TidalTrack(found_tracks[idx][0], data_lookup=found_tracks[idx][1])
            else:
                yield None


class TidalPlaylistCollection(Collection, TrackStream):
    data: dict
    data_lookup: LookupDict

    def __init__(self, data: dict, data_lookup: LookupDict | None = None):
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

    def add_tracks(self, tracks: Iterable[TidalTrack]) -> None:
        """Add tracks to the playlist.

        Note: This does not update the local playlist object. You need to fetch
        the playlist again to see the changes.

        Parameters
        ----------
        tracks : Iterable[TidalTrack]
            The tracks to add to the playlist.
        """
        track_ids = [
            str(t.global_ids["tidal_id"]) for t in tracks if "tidal_id" in t.global_ids
        ]
        if not track_ids:
            log.warning("No valid Tidal IDs found for tracks to add to playlist.")
            return

        try:
            asyncio.run(add_tracks_to_playlist(self.id, track_ids=track_ids))
            log.info(f"Added {len(track_ids)} tracks to playlist '{self.name}'")
        except Exception as e:
            log.debug(f"Could not add tracks to playlist {self.name}: {e}")
            raise
        finally:
            # Update the local data
            try:
                self.data, self.data_lookup = asyncio.run(get_playlist(self.id))
            except Exception as e:
                log.debug(
                    f"Could not refresh playlist data after adding tracks to"
                    f"{self.name}: {e}"
                )

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
        data, included = await get_playlist(playlist_id)
        return cls(data, data_lookup=included)

    # ---------------------------------------------------------------------------- #
    #                        Helper methods (tidal specific)                       #
    # ---------------------------------------------------------------------------- #

    @property
    def _items_raw(self) -> list[dict]:
        return [
            item
            for item in self.data.get("relationships", {})
            .get("items", {})
            .get("data", [])
        ]

    def _track_data_included(self, track_id: str) -> tuple[dict, LookupDict] | None:
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
                    "Skipping non-track item in playlist"
                    f"'{self.name}': {item['track']['type']}"
                )
                continue

            if track_data := self._track_data_included(item["id"]):
                yield TidalPlaylistTrack(
                    track_data[0],
                    data_lookup=track_data[1],
                    added_at=item["meta"]["addedAt"],
                )
            else:
                log.debug(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{self.name}'"
                )

    def __len__(self) -> int:
        """Return the number of tracks in the playlist."""
        return len(self._items_raw)
