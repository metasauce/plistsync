from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, Self, cast

from plistsync.core.playlist import (
    MultiRequestPlaylistCollection,
    PlaylistInfo,
    Snapshot,
)
from plistsync.logger import log

from .api import LookupDict
from .api_types import PlaylistResource
from .track import TidalPlaylistTrack

if TYPE_CHECKING:
    from .library import TidalLibraryCollection


class TidalPlaylistCollection(MultiRequestPlaylistCollection[TidalPlaylistTrack]):
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
        self._tracks = tracks or []  # do not set to None, we do not want to fetch!
        self.data = PlaylistInfo(name=name, description=description or "")

    @classmethod
    def from_response_data(
        cls,
        library: TidalLibraryCollection,
        data: PlaylistResource,
        data_lookup: LookupDict,
    ) -> Self:
        """Create a TidalPlaylistCollection from a PlaylistResource response."""
        plist = cls(library, name=data["attributes"]["name"])
        plist.data = (data, data_lookup)  # now self.online_data and len is available

        # we might have track data provided
        tracks: list[TidalPlaylistTrack] = []
        for item in data.get("relationships", {}).get("items", {}).get("data", []):
            if track_data := data_lookup.get((item["type"], item["id"])):
                tracks.append(
                    TidalPlaylistTrack(
                        track_data[0],
                        data_lookup=track_data[1],
                        meta=item.get("meta", {}),
                    )
                )
            else:
                log.warning(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{data['attributes']['name']}'"
                )

        if len(tracks) == len(plist):
            plist._tracks = tracks  # consistent, use provided track data.
        else:
            plist._tracks = None  # will fetch on first access to .tracks

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
                description=plist_data["attributes"].get("description", None),
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
            self.data["description"] = value.get("description")

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

    def _refetch_tracks(self) -> list[TidalPlaylistTrack]:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        if not self.online_data:
            raise ValueError("Cannot refetch tracks for offline playlist")

        items, items_lookup = self.api.playlist.get_items(self.online_data[0]["id"])
        tracks = []
        for item in items:
            # item is PlaylistsItemsResourceIdentifier
            if track_resource := items_lookup.get((item["type"], item["id"])):
                tracks.append(
                    TidalPlaylistTrack(
                        track_resource,
                        data_lookup=items_lookup,
                        meta=item.get("meta", {}),
                    )
                )
            else:
                log.warning(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{data['attributes']['name']}'"
                )
        self._tracks = tracks
        return self._tracks

    @property
    def tracks(self) -> list[TidalPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._refetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[TidalPlaylistTrack]) -> None:
        self._tracks = value

    def __len__(self) -> int:
        """Return the number of tracks in the playlist."""
        if self.online_data:
            # Use numberOfItems attribute if available
            attrs = self.online_data[0]["attributes"]
            if "numberOfItems" in attrs:
                return attrs["numberOfItems"]
            # Fallback to relationship data length (always present)
            return len(
                self.online_data[0]
                .get("relationships", {})
                .get("items", {})
                .get("data", [])
            )
        return len(self._tracks or [])

    # ----------------------------- Remote operations ---------------------------- #

    @property
    def remote_associated(self):
        return self.online_data is not None

    def _remote_create(self):
        self.data = self.api.playlist.create(self.name, self.description or "")
        if self._tracks:
            self.api.playlist.add_items(
                self.data[0]["id"],  # type: ignore[literal-required]
                ids=[t.id for t in self._tracks],
            )
        self._refetch_tracks()

    def _remote_delete(self):
        if self.id is None:
            raise ValueError("Playlist must be online to call remote delete!")
        self.api.playlist.delete(self.id)
        self.data = self.info

    def _remote_insert_track(
        self,
        idx: int,
        track: TidalPlaylistTrack | list[TidalPlaylistTrack],
        tracks_before: list[TidalPlaylistTrack],
    ) -> None:
        if not self.id:
            raise ValueError("Id must be set to call remote insert!")
        track_ids = [t.id for t in track] if isinstance(track, list) else [track.id]
        if idx >= len(tracks_before):
            self.api.playlist.add_items(
                playlist_id=self.id,
                ids=track_ids,
            )
        else:
            self.api.playlist.add_items(
                playlist_id=self.id,
                ids=track_ids,
                position_before=tracks_before[idx].item_id,
            )

    def _remote_delete_track(
        self,
        idx: int,
        track: TidalPlaylistTrack | list[TidalPlaylistTrack],
        tracks_before: list[TidalPlaylistTrack],
    ) -> None:
        if not self.id:
            raise ValueError("Id must be set to call remote delete!")

        if not isinstance(track, list):
            track = [track]

        # Realistically this should never be unset if we want to remove the track
        if not all(t.item_id for t in track):
            raise ValueError("ItemID must be set in every track we want to remove!")

        # Deletion is done via itemId (unique in playlist)
        self.api.playlist.remove_items(
            playlist_id=self.id,
            item_ids=[(t.id, cast(str, t.item_id)) for t in track],
        )

    def _remote_update_metadata(
        self,
        new_name: str | None = None,
        new_description: str | None = None,
    ) -> None:
        if not self.id:
            raise ValueError("Id must be set to call remote delete!")

        self.api.playlist.update(
            id=self.id,
            name=new_name,
            description=new_description,
        )

    def _remote_commit(
        self,
        before: Snapshot[TidalPlaylistTrack],
        after: Snapshot[TidalPlaylistTrack],
    ) -> None:
        super()._remote_commit(before, after)
        # After edit we refetch all tracks as their is no other
        # easy way to get the new item ids
        self._refetch_tracks()

    @staticmethod
    def _track_key(track: TidalPlaylistTrack) -> Hashable:
        return track.id  # Maybe we want item_id here
