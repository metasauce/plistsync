from collections.abc import Iterable
from typing import overload

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.logger import log

from .api import TidalApi, extract_tidal_playlist_id
from .playlist import TidalPlaylistCollection
from .track import TidalTrack


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
        return [
            TidalPlaylistCollection.from_response_data(self, pl, lookup)
            for pl in playlists
        ]

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
            found = [p for p in playlists if p["attributes"]["name"] == name]
            if len(found) == 0:
                log.info(f"Could not find playlist with name {name}")
                return None

            id = found[0]["id"]
            if len(found) > 1:
                log.info(f"Found more than one playlist with name {name}, using {id}")

        # This should never realistically happen -> assert instead of error
        assert id is not None, "ID must be set after resolving name/url"
        return TidalPlaylistCollection.from_response_data(
            self, *self.api.playlist.get(id)
        )

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

        Prioritizes isrc lookups over tidal_id lookups.
        """
        return list(self.find_many_by_global_ids([global_ids]))[0]

    def find_many_by_global_ids(
        self, global_ids_list: Iterable[GlobalTrackIDs]
    ) -> Iterable[TidalTrack | None]:
        """Find many tracks by their global IDs.

        Prioritizes isrc lookups over tidal_id lookups.
        """

        found_tracks: dict[int, TidalTrack] = {}

        # avoid consuming this, we iterate twice.
        global_ids_list = list(global_ids_list)

        # Tidal ids batch lookup
        idxes = []
        tidal_ids: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if "tidal_id" in gids:
                idxes.append(idx)
                tidal_ids.append(gids["tidal_id"])

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
