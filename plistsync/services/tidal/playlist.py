from __future__ import annotations

from collections.abc import Hashable, Sequence
from typing import TYPE_CHECKING, cast

from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    PlaylistIDs,
    PlaylistInfo,
    Snapshot,
)
from plistsync.logger import log

from .api import LookupDict
from .api_types import PlaylistResource
from .track import TidalPlaylistTrack, TidalTrack

if TYPE_CHECKING:
    from .library import TidalLibrary


class TidalPlaylist(MultiRequestServicePlaylist[TidalPlaylistTrack]):
    library: TidalLibrary

    data: PlaylistResource

    _tracks: None | list[TidalPlaylistTrack] = None  # None indicates fetch on access

    def __init__(
        self,
        library: TidalLibrary,
        data: PlaylistResource,
        data_lookup: LookupDict,
    ):
        """Create a TidalPlaylist from a PlaylistResource response."""
        self.library = library
        self.data = data  # now self.online_data and len is available
        self.lookup = data_lookup

        # we might have track data provided
        tracks: list[TidalPlaylistTrack] = []
        for item in data.get("relationships", {}).get("items", {}).get("data", []):
            if track_data := data_lookup.get((item["type"], item["id"])):
                tracks.append(
                    TidalPlaylistTrack(
                        track_data,
                        data_lookup=data_lookup,
                        meta=item.get("meta", {}),
                    )
                )
            else:
                log.warning(
                    f"Track with id '{item['id']}' not found in cached"
                    " tracks of playlist '{data['attributes']['name']}'"
                )

        expected_length = 0
        # Use numberOfItems attribute if available
        if "numberOfItems" in self.data["attributes"]:
            expected_length = self.data["attributes"]["numberOfItems"]
        # Fallback to relationship data length (always present)
        else:
            expected_length = len(
                self.data.get("relationships", {}).get("items", {}).get("data", [])
            )

        if len(tracks) == expected_length:
            # consistent: use provided track data
            self._tracks = tracks
        else:
            self._tracks = None

    @property
    def api(self):
        return self.library.api

    # ----------------------- Required (Playlist protocol) ----------------------- #

    @property
    def info(self) -> PlaylistInfo:
        """Get basic info about the playlist."""
        return PlaylistInfo(
            name=self.data["attributes"]["name"],
            description=self.data["attributes"].get("description", None) or None,
        )

    @info.setter
    def info(self, value: PlaylistInfo) -> None:
        """Set basic info about the playlist."""
        self.data["attributes"]["name"] = value.get("name", self.name)
        self.data["attributes"]["description"] = value.get("description") or ""

    @property
    def tracks(self) -> list[TidalPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._refetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: Sequence[TidalTrack]) -> None:
        def convert(t: TidalPlaylistTrack | TidalTrack):
            # convert tracks to playlist tracks
            if isinstance(t, TidalPlaylistTrack):
                return t
            else:
                return TidalPlaylistTrack(t)

        self._tracks = list(map(convert, value))

    @property
    def ids(self) -> PlaylistIDs:
        """Unique identifiers of the playlist."""
        return PlaylistIDs(tidal_id=self.data["id"])

    @property
    def id(self) -> str:
        """Tidal Playlist ID."""
        return self.data["id"]

    # -------------------- Required (ServicePlaylist protocol) ------------------- #

    def _remote_delete(self):
        self.api.playlist.delete(self.id)

    # -------------- Required (MultiRequestServicePlaylist protocol) ------------- #

    def _remote_insert_track(
        self,
        idx: int,
        track: TidalPlaylistTrack | list[TidalPlaylistTrack],
        tracks_before: list[TidalPlaylistTrack],
    ) -> None:
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

    # ---------------------------- Track lazy loading ---------------------------- #

    def __len__(self) -> int:
        if self._tracks is None:
            return self.data["attributes"].get("numberOfItems", -1)
        return len(self._tracks)

    def _refetch_tracks(self) -> list[TidalPlaylistTrack]:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """

        items, items_lookup = self.api.playlist.get_items(self.data["id"])
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
