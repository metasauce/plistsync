from __future__ import annotations

from collections.abc import Generator, Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePath
from typing import Any, Self, overload, override

from plistsync.core import GlobalTrackIDs, LibraryCollection, PathRewrite
from plistsync.core.collection import GlobalLookup, LocalLookup, TrackStream
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo, Snapshot
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log
from plistsync.services.local.track import FileCache
from plistsync.services.plex.api_types import (
    PlexApiPlaylistResponse,
    PlexApiTrackResponse,
)

from .api import PlexApi
from .track import PlexTrack


class PlexLibrarySectionCollection(
    LibraryCollection, LocalLookup, GlobalLookup, TrackStream[PlexTrack]
):
    """A collection of all tracks in a Plex library section.

    `section` is the term plex use in the backend, this aligns in the plex frontend
    this is often called `library`.

    Notes
    -----
    - Plex Collections are lazy loaded, but once loaded (by iterate) they are cached.
    - To refresh the state from the server, you need to recreate the collection
    instance.
    """

    id: int
    api: PlexApi

    def __init__(
        self,
        section_name_or_id: str | int,
        server_url: str | None = None,
        server_name: str | None = None,
    ):
        """Initialize the PlexLibraryCollection from plex given a section id.

        Parameters
        ----------
        section_name_or_id : str | int
            The Name or ID of the Plex library section to fetch.
        server_url : str, optional
            The server for this collection. If not specified, loaded from config.
        """
        self.api = PlexApi(server_url=server_url, server_name=server_name)
        self.id = self.api.converts.section_name_to_id(section_name_or_id)

    def preload(self, force_reload=False) -> None:
        """Preload the collections tracks.

        This ensures that, for each track in the collection, all plex data is in memory
        and can be iterated over without additional API calls.

        Note: This does not include file-based metadata.
        """
        if force_reload:
            self._fetched = False
        _ = list(self.tracks)

    @property
    def playlists(self) -> Iterable[PlexPlaylistCollection]:
        """Get all playlists in the library as PlexPlaylistCollection objects."""
        playlists: list[PlexPlaylistCollection] = []
        for pl_data in self.api.playlist.all():
            # we might also want to filter: smart=False
            if pl_data.get("playlistType") != "audio":
                continue
            playlists.append(
                PlexPlaylistCollection.from_response_data(
                    library=self,
                    playlist_data=pl_data,
                    tracks_data=[],  # fetch later
                )
            )
        playlists = sorted(playlists, key=lambda p: p.name.lower())
        return playlists

    @overload
    def get_playlist(self, *, name: str) -> PlexPlaylistCollection | None: ...

    @overload
    def get_playlist(self, *, id: int) -> PlexPlaylistCollection: ...

    @override
    def get_playlist(
        self,
        name: str | None = None,
        id: int | None = None,
    ) -> PlexPlaylistCollection | None:
        """Get a specific playlist.

        One of the kwargs must be given. Either search
        by name or get by id (rating_key).

        Will raise on id not found but return None if
        search by name not found.

        Tracks are fetched eagerly.
        """
        if sum(arg is not None for arg in [name, id]) != 1:
            raise ValueError("Exactly one of name or id must be provided")

        if name is not None:
            id = self.api.converts.playlist_name_to_id(name)

        if id is None:
            # For searches we want to return None if not found
            log.debug(f"Could not find playlist with name '{name}'")
            return None

        plist = PlexPlaylistCollection.from_response_data(
            library=self,
            playlist_data=self.api.playlist.get(id),
            tracks_data=self.api.playlist.get_items(id),
        )

        return plist

    @cached_property
    def locations(self) -> list[Path]:
        """To locations (on disk) of the section."""
        sections = self.api.sections()
        paths: list[Path] = []
        for section in sections["MediaContainer"].get("Directory", []):
            if int(section.get("key")) == int(self.id):
                locations = section.get("Location", [{}])
                for loc in locations:
                    if "path" in loc:
                        paths.append(Path(loc.get("path")))

        return paths

    # -------------------------- TrackStream Protocl ------------------------- #

    _tracks: Sequence[PlexTrack] | None = None
    _page_size: int = 5000
    _fetched: bool = False

    @property
    def tracks(self) -> Generator[PlexTrack, Any, None]:
        """Iterate over the tracks in the collection."""

        if self._tracks is None or not self._fetched:
            self._tracks = []
            tracks_iter = map(
                lambda item: PlexTrack(item),
                self.api.track.fetch_tracks(
                    section_id=self.id,
                    page_size=self._page_size,
                ),
            )
            for track in tracks_iter:
                yield track
                self._tracks.append(track)
        else:
            for track in self._tracks:
                yield track

        self._fetched = True

    # --------------------------- Lookup Protocols --------------------------- #

    def find_by_global_ids(
        self,
        global_ids: GlobalTrackIDs,
        path_rewrite: PathRewrite | None = None,
        file_cache: FileCache | None = None,
    ):
        """Find a plex track via isrc.

        Note: Since isrc is not part of Plex's internal metadata, we have to do file
        lookups. This will be slow, and requires you to mount the volume that holds
        the actual tracks on your server.

        Parameters
        ----------
        global_ids : GlobalTrackIDs
            Needs to hold "isrc", otherwise no search is performed.
        path_rewrite: PathRewrite
            Rewrite rule to apply on the tracks, before metadata is looked up.
            Set this if you run plistsync from another machine than your Plex server.
            In the PathRewrite, "old" would be the Plex server, "new" the local mount.
        file_cache: FileCache
            Store the results of costly metadata lookups.
        """
        isrc = global_ids.get("isrc")
        if isrc is None:
            return None

        for track in self.tracks:
            local_track = track.get_local_track(
                path_rewrite=path_rewrite,
                file_cache=file_cache,
            )
            if local_track.global_ids.get("isrc") == isrc:
                # TODO: PS 2026-02-13 this needs better abstraction.
                # -> we want the isrc in the PlexTrack, too.
                # We should have a library level cache.
                # It can be auto-generated, preloaded, or gets filled as we fetch here.
                track.global_ids["isrc"] = isrc
                return track

    def find_by_local_ids(
        self, local_ids: LocalTrackIDs, path_rewrite: PathRewrite | None = None
    ):
        """Find a track by its plex ID (rating key) or file path.

        Plex id is prioritized.

        Parameters
        ----------
        local_ids : LocalTrackIDs
            may contain plex_id and/pr file_path
        path_rewrite: PathRewrite
            Rewrite rule to apply on the tracks, before they are compared to local_ids.
            Set this if you run plistsync from another machine than your Plex server.
            In the PathRewrite, "old" would be the Plex server, "new" the local mount.
        """

        plex_id = local_ids.get("plex_id")
        file_path = local_ids.get("file_path")

        if path_rewrite is not None and file_path is not None:
            file_path = path_rewrite.invert.apply(file_path)

        for track in self.tracks:
            if plex_id and track.id == plex_id:
                return track
            if file_path and track.path and file_path == track.path:
                return track


@dataclass(frozen=True)
class PlexPlaylistOnlineData:
    playlist_data: PlexApiPlaylistResponse
    tracks_data: list[PlexApiTrackResponse]


class PlexPlaylistCollection(PlaylistCollection[PlexTrack]):
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
        self._tracks = tracks or []
        self.data = PlaylistInfo(name=name, description=description or "")

    @classmethod
    def from_response_data(
        cls,
        library: PlexLibrarySectionCollection,
        playlist_data: PlexApiPlaylistResponse,
        tracks_data: list[PlexApiTrackResponse] | None = None,
    ) -> Self:
        """
        Create a new instance of Plex playlist from a given api response.

        The resulting instance will have id and we consider it is available online.
        """
        tracks_data = tracks_data or []
        plist = cls(
            library,
            name=playlist_data["title"],
            description=playlist_data.get("summary"),
        )
        plist.data = PlexPlaylistOnlineData(playlist_data, tracks_data)
        plist._tracks = [PlexTrack(t) for t in tracks_data]
        return plist

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
                data.get("name", ""),
            )
            data["summary"] = (
                value.get(
                    "description",
                    data.get("description", ""),
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

    def _refetch_tracks(self) -> None:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        if not self.online_data:
            raise ValueError("Cannot refetch tracks for offline playlist")

        self._tracks = [PlexTrack(t) for t in self.online_data.tracks_data]

    @property
    def tracks(self) -> list[PlexTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            self._refetch_tracks()

        return self._tracks or []

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
        pl_data = self.api.playlist.create(name=self.name)
        pl_id = int(pl_data["ratingKey"])
        if self.description is not None and self.description != "":
            self.api.playlist.update(pl_id, description=self.description)

        self.data = PlexPlaylistOnlineData(pl_data, [])
        if self._tracks:
            self.api.playlist.add_tracks(pl_id, [t.id for t in self._tracks])
        self._refetch_tracks()

    def _remote_insert_track(
        self,
        idx: int,
        track: PlexTrack,
        live_list: list[PlexTrack],
    ) -> None:
        if self.id is None:
            raise ValueError("Playlist must be online to call remote insert!")

        self.api.playlist.add_tracks(playlist_id=self.id, item_ids=[track.id])

        # TODO: reordering needs its own api call.

    def _remote_delete_track(
        self,
        idx: int,
        track: PlexTrack,
        live_list: list[PlexTrack],
    ):
        """
        Delete Track from playlists.

        Plex does not allow duplicate items in playlists.
        Therefore, idx is ignored.
        """
        if self.id is None:
            raise ValueError("Playlist must be online to call remote delete!")
        self.api.playlist.remove_track(self.id, track.id)

    def _remote_move_track(
        self,
        old_idx: int,
        new_idx: int,
        track: PlexTrack,
        live_list: list[PlexTrack],
    ) -> None:
        """
        Move track in a playlist.

        Plex does not allow duplicate items in playlists.
        Therefore, old_idx is ignored.
        """
        if self.id is None:
            raise ValueError("Playlist must be online to call remote move!")

        if new_idx == 0 or len(self) == 1:
            after_id = None
        else:
            after_id = self.tracks[new_idx - 1].id
        self.api.playlist.move_track(self.id, track.id, after_id)

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
