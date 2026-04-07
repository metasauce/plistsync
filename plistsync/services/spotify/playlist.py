from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    PlaylistIDs,
    PlaylistInfo,
)

from .api_types import (
    PlaylistTracksBase,
    SpotifyApiPlaylistResponseBase,
    SpotifyApiPlaylistResponseFull,
    SpotifyApiPlaylistResponseSimplified,
    SpotifyApiPlaylistTrack,
)
from .track import SpotifyPlaylistTrack, SpotifyTrack

if TYPE_CHECKING:
    from .library import SpotifyLibraryCollection


class SpotifyPlaylistCollection(MultiRequestServicePlaylist[SpotifyPlaylistTrack]):
    """A collection representing a spotify playlist."""

    library: SpotifyLibraryCollection
    data: SpotifyApiPlaylistResponseBase
    tracks_data: PlaylistTracksBase

    _tracks: None | list[SpotifyPlaylistTrack] = None  # None indicates fetch on access

    def __init__(
        self,
        library: SpotifyLibraryCollection,
        data: SpotifyApiPlaylistResponseSimplified | SpotifyApiPlaylistResponseFull,
    ):
        """
        Create a new instance of Spotify playlist from a given api response.

        The resulting instance will have id and we consider it is available online.
        """

        # Split playlist & track data to allow lazy loading
        # tracks data includes a cursor to fetch the data
        self.data = data
        self.tracks_data = data.get("tracks", {})
        self.library = library

        tracks_data_items: list[SpotifyApiPlaylistTrack] = self.tracks_data.get(
            "items", []
        )

        # Build tracks if track data exists
        if len(tracks_data_items) == self.tracks_data.get("total", 0):
            self.tracks = [SpotifyPlaylistTrack(item) for item in tracks_data_items]

        if self.tracks_data.get("items", None) is not None:
            # PlaylistTracksBase has no items normally
            # we remove them here as they are parsed already
            # SBM: might be an over optimization
            del self.tracks_data["items"]  # type: ignore

    @property
    def api(self):
        return self.library.api

    # ----------------------- Required (Playlist protocol) ----------------------- #

    @property
    def info(self) -> PlaylistInfo:
        info = PlaylistInfo()
        info["name"] = self.data["name"]
        if description := self.data.get("description"):
            info["description"] = description
        return info

    @info.setter
    def info(self, value: PlaylistInfo):
        self.data["name"] = value.get(
            "name",
            self.data.get("name", ""),
        )
        self.data["description"] = value.get(
            "description",
            self.data.get("description", None),
        )

    @property
    def tracks(self) -> list[SpotifyPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._refetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: Sequence[SpotifyTrack]) -> None:
        def convert(t: SpotifyPlaylistTrack | SpotifyTrack):
            # convert tracks to playlist tracks
            if isinstance(t, SpotifyPlaylistTrack):
                return t
            else:
                return SpotifyPlaylistTrack(t)

        self._tracks = list(map(convert, value))

    @property
    def ids(self) -> PlaylistIDs:
        """Unique identifiers of the playlist."""
        return PlaylistIDs(spotify_id=self.data["id"])

    @property
    def id(self) -> str:
        return self.data["id"]

    # -------------------- Required (ServicePlaylist protocol) ------------------- #

    def _remote_delete(self):
        self.api.playlist.delete(self.id)

    # -------------- Required (MultiRequestServicePlaylist protocol) ------------- #

    def _remote_insert_track(
        self,
        idx: int,
        track: SpotifyPlaylistTrack | list[SpotifyPlaylistTrack],
        tracks_before: list[SpotifyPlaylistTrack],
    ) -> None:
        track_uris = [t.uri for t in track] if isinstance(track, list) else [track.uri]
        self.api.playlist.add_tracks(self.id, track_uris, idx)

    def _remote_delete_track(
        self,
        idx: int,
        track: SpotifyPlaylistTrack | list[SpotifyPlaylistTrack],
        tracks_before: list[SpotifyPlaylistTrack],
    ):
        track_uris = [t.uri for t in track] if isinstance(track, list) else [track.uri]
        self.api.playlist.remove_tracks(
            self.id, track_uris, [i for i in range(idx, idx - len(track_uris), -1)]
        )

    def _remote_move_track(
        self,
        old_idx: int,
        new_idx: int,
        track: SpotifyPlaylistTrack,
        tracks_before: list[SpotifyPlaylistTrack],
    ) -> None:
        self.api.playlist.reorder_tracks(
            playlist_id=self.id,
            range_start=old_idx,
            range_length=1,
            insert_before=new_idx,
        )

    def _remote_update_metadata(
        self,
        new_name=None,
        new_description=None,
    ):
        self.api.playlist.update(
            self.id,
            new_name,
            new_description,
        )

    @staticmethod
    def _track_key(track: SpotifyPlaylistTrack):
        return track.id

    # ---------------------------- Track lazy loading ---------------------------- #

    def __len__(self) -> int:
        """If tracks are not fetched yet, use length from minimal response."""
        if self._tracks is None:
            return self.tracks_data.get("total", -1)
        return len(self._tracks)

    def _refetch_tracks(self) -> list[SpotifyPlaylistTrack]:
        """Refetch the tracks from the online playlist."""

        self._tracks = [
            SpotifyPlaylistTrack(item)
            for item in self.api.playlist._load_tracks(self.tracks_data)
        ]
        return self._tracks
