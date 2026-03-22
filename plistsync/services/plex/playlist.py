from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, cast

from plistsync.core.playlist import MultiRequestPlaylistCollection, PlaylistInfo
from plistsync.logger import log

from .api import PlexApi
from .api_types import (
    PlexApiPlaylistResponse,
    PlexApiTrackResponse,
)
from .track import PlexTrack

if TYPE_CHECKING:
    from .library import PlexLibrarySectionCollection


@dataclass
class PlexPlaylistOnlineData:
    playlist_data: PlexApiPlaylistResponse
    tracks_data: Sequence[PlexApiTrackResponse]


class PlexPlaylistCollection(MultiRequestPlaylistCollection[PlexTrack]):
    """
    A collection of all tracks in a Plex playlist.

    Notes
    -----
    - Plex playlists DO NOT allow the same track multiple times.
    - Plex playlists are not hard-linked to a particular section_id.
      they can contain tracks from multiple libraries.
    """

    # parent library for adding tracks
    library: PlexLibrarySectionCollection

    # When the playlist is already on the server, we have the response.
    # Otherwise, we have at least a name via PlaylistInfo.
    data: PlexPlaylistOnlineData | PlaylistInfo

    def __init__(
        self,
        library: PlexLibrarySectionCollection,
        name: str,
        description: str | None = None,
        tracks: list[PlexTrack] | None = None,
    ) -> None:
        self.library = library
        self._tracks = tracks or []  # do not set to None, we do not want to fetch!
        self.data = PlaylistInfo(name=name, description=description or "")

    @classmethod
    def from_response_data(
        cls,
        library: PlexLibrarySectionCollection,
        playlist_data: PlexApiPlaylistResponse,
        tracks_data: Sequence[PlexApiTrackResponse] | None = None,
    ) -> Self:
        """
        Create a new instance of Plex playlist from a given api response.

        The resulting instance will have id and we consider it is available online.
        """
        tracks_data = tracks_data or []
        pl = cls(
            library,
            name=playlist_data["title"],
            description=playlist_data.get("summary"),
        )
        pl.data = PlexPlaylistOnlineData(playlist_data, tracks_data)

        if len(tracks_data) == playlist_data.get("leafCount", 0):
            pl._tracks = [PlexTrack(t) for t in tracks_data]
        else:
            pl._tracks = None  # set to None to fetch on access
        return pl

    # ----------------------- Properties and info logic ---------------------- #

    @property
    def online_data(
        self,
    ) -> PlexPlaylistOnlineData | None:
        """
        Indicate if this playlist is associated with it's online version.

        None if created with default constructor, but PlexPlaylistOnlineData
        once we haveresponse data.
        """
        if isinstance(self.data, PlexPlaylistOnlineData):
            return self.data
        return None

    @property
    def id(self) -> int | None:
        """Get the unique identifier of the playlist (ratingKey).

        None if playlist is not associated with an online resource.
        """
        if data := self.online_data:
            return int(data.playlist_data["ratingKey"])
        return None

    @property
    def api(self) -> PlexApi:
        """Get the Plex API instance associated with this playlist."""
        return self.library.api

    @property
    def info(self) -> PlaylistInfo:
        if isinstance(self.data, PlexPlaylistOnlineData):
            data = self.data.playlist_data
            info = PlaylistInfo()
            info["name"] = data["title"]
            if description := data.get("summary"):
                info["description"] = description
            return info
        else:
            return self.data

    @info.setter
    def info(self, value: PlaylistInfo):
        if isinstance(self.data, PlexPlaylistOnlineData):
            data = self.data.playlist_data
            data["title"] = value.get(
                "name",
                data.get("name", ""),  # type: ignore[typeddict-item]
            )
            data["summary"] = (
                value.get(
                    "description",
                    data.get("description", ""),  # type: ignore[typeddict-item]
                )
                or ""
            )
        else:
            self.data = value

    @property
    def is_smart(self) -> bool | None:
        """Check if the playlist is a smart playlist.

        Tracks cannot be added to smart playlists.
        """
        if isinstance(self.data, PlexPlaylistOnlineData):
            return self.data.playlist_data.get("smart", False)
        return None

    # -------------------------------- Tracks -------------------------------- #

    def _refetch_tracks(self) -> list[PlexTrack]:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        log.debug(f"Refetching tracks for playlist {self.name}")
        if self.id is None or not isinstance(self.data, PlexPlaylistOnlineData):
            raise ValueError("Cannot refetch tracks for offline playlist")

        self.data.tracks_data = self.api.playlist.get_items(self.id)
        self._tracks = [PlexTrack(t) for t in self.data.tracks_data]
        return self._tracks

    @property
    def tracks(self) -> list[PlexTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._refetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[PlexTrack]) -> None:
        self._tracks = value

    def __len__(self) -> int:
        """Return the number of tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if data := self.online_data:
            return data.playlist_data.get("leafCount", 0)
        return len(self.tracks)

    # ----------------------------- Remote operations ---------------------------- #

    @property
    def remote_associated(self) -> bool:
        if self.online_data is not None:
            return True
        return False

    def _remote_create(self):
        # check whether a playlist with the same name exists
        # TODO: user config option to set behaviour
        for pl_res in self.api.playlist.all():
            if pl_res["title"] == self.name:
                raise ValueError(f"A playlist with name '{self.name}' already exists.")

        pl_data = self.api.playlist.create(name=self.name)
        pl_id = int(pl_data["ratingKey"])
        if self.description is not None and self.description != "":
            self.api.playlist.update(pl_id, description=self.description)

        self.data = PlexPlaylistOnlineData(pl_data, [])
        if self._tracks:
            self.api.playlist.add_tracks(pl_id, [t.id for t in self._tracks])
        self._refetch_tracks()

    def _remote_delete(self):
        if self.id is None:
            raise ValueError("Playlist must be online to call remote delete!")
        self.api.playlist.delete(self.id)

    def _remote_insert_track(
        self,
        idx: int,
        track: PlexTrack | list[PlexTrack],
        tracks_before: list[PlexTrack],
    ) -> None:
        if self.id is None:
            raise ValueError("Playlist must be online to call remote insert!")

        if not isinstance(track, list):
            track = [track]

        self.api.playlist.add_tracks(
            playlist_id=self.id, item_ids=[t.id for t in track]
        )
        self._refetch_tracks()

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
        if self.id is None or not isinstance(self.data, PlexPlaylistOnlineData):
            raise ValueError("Playlist must be online to call remote delete!")

        if not isinstance(track, list):
            track = [track]

        for t in track:
            t_data = None
            for td in self.data.tracks_data:
                if td.get("ratingKey") == t.id:
                    t_data = td
                    break

            if t_data is None:
                log.warning(
                    f"Could not find track data for track id {t.id} in playlist. "
                    "This should not happen, please consider opening an issue."
                )
                continue

            pl_item_id = cast(int, t_data.get("playlistItemID", -1))
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
        if self.id is None or not isinstance(self.data, PlexPlaylistOnlineData):
            raise ValueError("Playlist must be online to call remote move!")

        if new_idx == 0 or len(self) == 1:
            after_id = None
        else:
            after_id = cast(
                int, self.data.tracks_data[new_idx - 1].get("playlistItemID", -1)
            )

        pl_item_id = cast(int, self.data.tracks_data[old_idx].get("playlistItemID", -1))
        if self.data.tracks_data[old_idx].get("ratingKey", -1) != track.id:
            raise ValueError(f"Key mismatch for {old_idx=} vs {track=}")

        self.api.playlist.move_track(self.id, pl_item_id, after_id)
        self._refetch_tracks()

    def _remote_update_metadata(self, new_name=None, new_description=None):
        if self.id is None:
            raise ValueError("Playlist must be online to call remote update!")
        self.api.playlist.update(
            self.id,
            new_name,
            new_description,
        )

    @staticmethod
    def _track_key(track: PlexTrack):
        return track.id
