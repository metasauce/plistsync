from __future__ import annotations

from collections.abc import Hashable, Iterable
from typing import overload

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo
from plistsync.logger import log

from .api import LookupDict, TidalApi, extract_tidal_playlist_id
from .api_types import PlaylistResource
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


class TidalPlaylistCollection(PlaylistCollection[TidalPlaylistTrack]):
    library: TidalLibraryCollection

    # When the playlist is associated with an online playlist, we have the response.
    # Otherwise, we have at least a name via PlaylistInfo.
    data: tuple[PlaylistResource, LookupDict] | PlaylistInfo

    def __init__(
        self,
        library: TidalLibraryCollection,
        name: str,
        description: str | None = None,
        tracks: list[TidalPlaylistTrack] | None = None,
    ) -> None:
        self.library = library
        self._tracks = tracks or []
        self.data = PlaylistInfo(name=name, description=description or "")

    @classmethod
    def from_response_data(
        cls,
        data: PlaylistResource,
        data_lookup: LookupDict,
    ) -> TidalPlaylistCollection:
        """Create a TidalPlaylistCollection from a PlaylistResource response."""
        library = TidalLibraryCollection()
        plist = cls(library, name=data["attributes"]["name"])

        tracks: list[TidalPlaylistTrack] = []
        for item in data.get("relationships", {}).get("items", {}).get("data", []):
            if track_data := data_lookup.get((item["type"], item["id"])):
                tracks.append(
                    TidalPlaylistTrack(
                        track_data[0],
                        data_lookup=track_data[1],
                        added_at=item.get("meta", {}).get("addedAt", ""),
                    )
                )
            else:
                log.warning(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{data['attributes']['name']}'"
                )
        plist._tracks = tracks or None
        plist.data = (data, data_lookup)

        return plist

    # ----------------------- Properties and info logic ---------------------- #

    @property
    def api(self):
        return self.library.api

    @property
    def info(self) -> PlaylistInfo:
        """Get basic info about the playlist."""
        if isinstance(self.data, tuple):
            plist_data = self.data[0]
            return PlaylistInfo(
                name=plist_data["attributes"]["name"],
                description=plist_data["attributes"].get("description", ""),
            )
        else:
            return self.data

    @info.setter
    def info(self, value: PlaylistInfo) -> None:
        """Set basic info about the playlist."""
        if isinstance(self.data, tuple):
            self.data[0]["attributes"]["name"] = value.get("name", self.name)
            self.data[0]["attributes"]["description"] = value.get("description") or ""
        else:
            self.data["name"] = value.get("name", self.name)
            self.data["description"] = value.get("description") or ""

    @property
    def id(self) -> str | None:
        """Tidal Playlist ID.

        None if not associated with an online playlist.
        """
        if data := self.online_data:
            return data[0]["id"]
        return None

    # ---------------------------- Track lazy loading ---------------------------- #

    @property
    def online_data(self) -> tuple[PlaylistResource, LookupDict] | None:
        """Get the online playlist data, if available.

        None if this playlist is not associated with playlist online.
        """
        if isinstance(self.data, tuple):
            return self.data
        return None

    def _refetch_tracks(self) -> None:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        if not self.online_data:
            raise ValueError("Cannot refetch tracks for offline playlist")

        raise NotImplementedError("Refetching tracks not implemented yet")

    @property
    def tracks(self) -> list[TidalPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            self._refetch_tracks()
        return self._tracks or []

    @tracks.setter
    def tracks(self, value: list[TidalPlaylistTrack]) -> None:
        self._tracks = value

    def __len__(self) -> int:
        """Return the number of tracks in the playlist."""
        if self.online_data:
            return len(
                self.online_data[0]
                .get("relationships", {})
                .get("items", {})
                .get("data", [])
            )
        return len(self._tracks or [])

    # ----------------------------- Remote operations ---------------------------- #

    def _remote_insert_track(
        self,
        idx: int,
        track: TidalPlaylistTrack,
    ) -> None:
        raise NotImplementedError

    def _remote_delete_track(
        self,
        idx: int,
        track: TidalPlaylistTrack,
    ) -> None:
        raise NotImplementedError

    def _remote_update_metadata(
        self,
        new_name: str | None = None,
        new_description: str | None = None,
    ) -> None:
        raise NotImplementedError

    @staticmethod
    def _track_key(track: TidalPlaylistTrack) -> Hashable:
        raise NotImplementedError
