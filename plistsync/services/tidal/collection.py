from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Self, overload

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LibraryCollection,
    TrackStream,
)
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo
from plistsync.logger import log

from .api import LookupDict, TidalApi, extract_tidal_playlist_id
from .api_types import PlaylistResource, PlaylistsItemsResourceIdentifier, TrackResource
from .track import TidalPlaylistTrack, TidalTrack


class TidalLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection of Tidal library items."""

    api: TidalApi

    def __init__(self) -> None:
        super().__init__()
        self.api = TidalApi()

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[TidalPlaylistCollection]:
        playlists, lookup = self.api.playlist.get_many_by_user(self.api.user.me()["id"])
        return [TidalPlaylistCollection(pl, lookup) for pl in playlists]

    @overload
    def get_playlist(self, *, name: str) -> TidalPlaylistCollection | None: ...

    @overload
    def get_playlist(self, *, id: str) -> TidalPlaylistCollection: ...

    @overload
    def get_playlist(self, *, url: str) -> TidalPlaylistCollection: ...

    def get_playlist(
        self,
        name: str | None = None,
        id: str | None = None,
        url: str | None = None,
    ) -> TidalPlaylistCollection | None:
        """Get a specific playlist.

        One of the kwargs must be given. Either search
        by name or get by id/url.

        Will raise on id/url not found but return None if
        search by name not found.
        """
        if sum(arg is not None for arg in [name, id, url]) != 1:
            raise ValueError("Exactly one of name, id, or url must be provided")

        if url is not None:
            id = extract_tidal_playlist_id(url)

        # We fetch all playlists by the user and check if the name matches
        # Resolve name to id
        if name is not None:
            playlists, _ = self.api.playlist.get_many_by_user(
                self.api.user.me()["id"], include=[]
            )
            for plist in playlists:
                if plist["attributes"]["name"] == name:
                    id = plist["id"]
                    break

            if id is None:
                log.debug(f"Could not find playlist with name {name}")
                return None

        # This should never realistically happen -> assert instead of error
        assert id is not None, "ID must be set after resolving name/url"
        return TidalPlaylistCollection(*self.api.playlist.get(id))

    def has_playlist(self, name: str) -> bool:
        """Check if a playlist with the given name exists in the user's library."""
        for pl in self.api.playlist.get_many_by_user(
            self.api.user.me()["id"], include=[]
        )[0]:
            if pl["attributes"]["name"] == name:
                return True
        return False

    # --------------------------- GlobalLookup protocol -------------------------- #

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

        found_tracks: dict[int, TidalTrack] = {}

        # Get all tidal ids for batch lookup
        idxes = []
        tidal_ids: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if "tidal_id" in gids:
                idxes.append(idx)
                tidal_ids.append(gids["tidal_id"])

        # Tidal ids batch lookup
        if tidal_ids:
            tracks, lookup = self.api.tracks.get_many(tidal_ids)

            for idx, track in zip(idxes, tracks):
                if not track:
                    log.debug(f"Track with tidal_id '{tidal_ids[idx]}' not found")
                else:
                    found_tracks[idx] = TidalTrack(track, lookup)

        # ISRC batch lookup for remaining ids
        idxes = []
        isrcs: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if idx in found_tracks:
                continue
            if "isrc" in gids:
                idxes.append(idx)
                isrcs.append(gids["isrc"])

        if isrcs:
            tracks, lookup = self.api.tracks.get_many_by_isrc(isrcs)

            for idx, track in zip(idxes, tracks):
                if not track:
                    log.debug(f"Track with isrc '{isrcs[idx]}' not found")
                else:
                    found_tracks[idx] = TidalTrack(track, lookup)

        for idx, gids in enumerate(global_ids_list):
            yield found_tracks.get(idx, None)


class TidalPlaylistCollection(PlaylistCollection[TidalPlaylistTrack]):
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
    def id(self) -> str:
        """The tidal ID of the playlist."""
        return self.data["id"]

    @property
    def info(self) -> PlaylistInfo:
        """Get basic info about the playlist."""
        return PlaylistInfo(
            name=self.data["attributes"]["name"],
            description=self.data["attributes"].get("description", ""),
        )

    @info.setter
    def info(self, value: PlaylistInfo) -> None:
        """Set basic info about the playlist."""
        self.data["attributes"]["name"] = value.get("name", self.name)
        self.data["attributes"]["description"] = value.get("description") or ""

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

    def tracks(self) -> Iterator[TidalPlaylistTrack]:
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
