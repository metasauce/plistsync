from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    PlaylistIDs,
    PlaylistInfo,
)
from plistsync.logger import log

from .api import PlexApi
from .api_types import (
    PlexApiPlaylistResponse,
    PlexApiPlaylistTrackResponse,
)
from .track import PlexTrack

if TYPE_CHECKING:
    from .library import PlexLibrarySectionCollection


class PlexPlaylistCollection(MultiRequestServicePlaylist[PlexTrack]):
    """
    A collection of all tracks in a Plex playlist.

    Notes
    -----
    - Plex playlists DO NOT allow the same track multiple times.
    - Plex playlists are not hard-linked to a particular section_id.
      they can contain tracks from multiple libraries.
    """

    library: PlexLibrarySectionCollection

    data: PlexApiPlaylistResponse
    tracks_data: list[PlexApiPlaylistTrackResponse]

    _tracks: list[PlexTrack] | None = None  # None indicates fetch on access

    def __init__(
        self,
        library: PlexLibrarySectionCollection,
        data: PlexApiPlaylistResponse,
        tracks_data: list[PlexApiPlaylistTrackResponse] | None = None,
    ):
        """Create a new instance of Plex playlist from a given api response."""
        self.library = library
        self.data = data
        self.tracks_data = tracks_data or []

        if len(self.tracks_data) == self.data.get("leafCount", 0):
            self._tracks = [PlexTrack(t) for t in self.tracks_data]

    @property
    def api(self) -> PlexApi:
        """Get the Plex API instance associated with this playlist."""
        return self.library.api

    @property
    def is_smart(self) -> bool:
        """Check if the playlist is a smart playlist.

        Tracks cannot be added to smart playlists.
        """
        return self.data.get("smart", False)

    # ----------------------- Required (Playlist protocol) ----------------------- #

    @property
    def info(self) -> PlaylistInfo:
        """Get basic info about the playlist."""
        info = PlaylistInfo()
        info["name"] = self.data["title"]
        if description := self.data.get("summary"):
            info["description"] = description
        return info

    @info.setter
    def info(self, value: PlaylistInfo):
        self.data["title"] = value.get(
            "name",
            self.data.get("name", ""),  # type: ignore[typeddict-item]
        )
        self.data["summary"] = (
            value.get(
                "description",
                self.data.get("description", ""),  # type: ignore[typeddict-item]
            )
            or ""
        )

    @property
    def tracks(self) -> list[PlexTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._refetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: Sequence[PlexTrack]) -> None:
        self._tracks = list(value)

    @property
    def ids(self) -> PlaylistIDs:
        """Unique identifiers of the playlist."""
        return PlaylistIDs(plex_id=self.id)

    @property
    def id(self) -> int:
        """Get the unique identifier of the playlist (ratingKey)."""
        return int(self.data["ratingKey"])

    # -------------------- Required (ServicePlaylist protocol) ------------------- #

    def _remote_delete(self):
        self.api.playlist.delete(self.id)

    # -------------- Required (MultiRequestServicePlaylist protocol) ------------- #

    def _remote_insert_track(
        self,
        idx: int,
        track: PlexTrack | list[PlexTrack],
        tracks_before: list[PlexTrack],
    ) -> None:
        if not isinstance(track, list):
            track = [track]

        self.api.playlist.add_tracks(
            playlist_id=self.id, item_ids=[t.id for t in track]
        )
        self._refetch_tracks()

        if idx != len(tracks_before):
            # we always insert at the end, move to the right spot
            for i, t in enumerate(track):
                self._remote_move_track(-1 - i, idx, t, tracks_before)

    def _remote_delete_track(
        self,
        idx: int,
        track: PlexTrack | list[PlexTrack],
        tracks_before: list[PlexTrack],
    ):
        """
        Delete Track from playlists.

        Plex does not allow duplicate items in playlists.
        """
        if not isinstance(track, list):
            track = [track]

        for t in track:
            t_data = None
            for td in self.tracks_data:
                if td.get("ratingKey") == t.id:
                    t_data = td
                    break

            if t_data is None:
                log.warning(
                    f"Could not find track data for track id {t.id} in playlist. "
                    "This should not happen, please consider opening an issue."
                )
                continue

            pl_item_id = t_data.get("playlistItemID", -1)

            self.api.playlist.remove_track(self.id, pl_item_id)
        self._refetch_tracks()

    def _remote_move_track(
        self,
        old_idx: int,
        new_idx: int,
        track: PlexTrack,
        tracks_before: list[PlexTrack],
    ) -> None:
        """
        Move track in a playlist.

        Plex does not allow duplicate items in playlists.
        Therefore, old_idx is ignored.
        """
        log.debug(f"Moving track {track.id} to idx {new_idx}")

        if new_idx == 0 or len(self) == 1:
            after_id = None
        else:
            after_id = self.tracks_data[new_idx - 1].get("playlistItemID", -1)

        pl_item_id = self.tracks_data[old_idx].get("playlistItemID", -1)
        if self.tracks_data[old_idx].get("ratingKey", -1) != track.id:
            raise ValueError(f"Key mismatch for {old_idx=} vs {track=}")

        self.api.playlist.move_track(self.id, pl_item_id, after_id)
        self._refetch_tracks()

    def _remote_update_metadata(self, new_name=None, new_description=None):
        self.api.playlist.update(
            self.id,
            new_name,
            new_description,
        )

    @staticmethod
    def _track_key(track: PlexTrack):
        return track.id

    # ---------------------------- Track lazy loading ---------------------------- #

    def _refetch_tracks(self) -> list[PlexTrack]:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        self.tracks_data = self.api.playlist.get_items(self.id)
        self._tracks = [PlexTrack(item) for item in self.tracks_data]
        return self._tracks
