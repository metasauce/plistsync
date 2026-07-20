from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, overload

from requests import HTTPError

from plistsync.core import Library
from plistsync.core.collection import IDLookup, TrackStream
from plistsync.core.ids import ISRC, FilePath, PlaylistID
from plistsync.logger import log
from plistsync.services.plex.playlist import PlexPlaylist, PlexPlaylistID

from .api import PlexApi
from .track import PlexTrack, PlexTrackID

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from plistsync.core import PathRewrite, TrackID
    from plistsync.services.local.track import FileCache


class PlexLibrary(
    Library[PlexTrack, PlexPlaylist],
    TrackStream[PlexTrack],
    IDLookup[PlexTrack],
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

    def __init__(self, section_name_or_id: str | int = "Music"):
        """Initialize the PlexLibrary from plex given a section id.

        Parameters
        ----------
        section_name_or_id : str | int
            The Name or ID of the Plex library section to fetch.
        """
        self.api = PlexApi()
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
    def playlists(self) -> Iterable[PlexPlaylist]:
        """Get all playlists in the library as PlexPlaylist objects."""
        playlists: list[PlexPlaylist] = []
        for pl_data in self.api.playlist.all():
            # we might also want to filter: smart=False
            if pl_data.get("playlistType") != "audio":
                continue
            playlists.append(
                PlexPlaylist(
                    library=self,
                    data=pl_data,
                )
            )
        playlists = sorted(playlists, key=lambda p: p.name.lower())
        return playlists

    @overload
    def get_playlist(self, *, name: str | None = None) -> PlexPlaylist | None: ...
    @overload
    def get_playlist(
        self, *, id: PlaylistID | str | int | None = None
    ) -> PlexPlaylist | None: ...

    def get_playlist(
        self,
        *,
        name: str | None = None,
        id: PlaylistID | str | int | None = None,
    ) -> PlexPlaylist | None:
        """Get a specific playlist.

        Exactly one of the kwargs must be given. Either search
        by name or by id (rating_key, url...).

        Will return None if not found.

        Tracks are fetched eagerly.
        """
        if sum(arg is not None for arg in [name, id]) != 1:
            raise ValueError("Exactly one of name, ids or id must be provided")

        if name is not None:
            id = self.api.converts.playlist_name_to_id(name)
            if id is None:
                log.debug(f"No playlist found for name={name!r}")
                return None

        # normalize into PlaylistID
        if isinstance(id, PlaylistID):
            playlist_id = id
        else:
            try:
                playlist_id = PlexPlaylistID.parse(id)  # type: ignore[arg-type]
            except ValueError:
                log.warning(f"Invalid playlist id format: {id!r}")
                return None

        # enforce plex boundary
        if not isinstance(playlist_id, PlexPlaylistID):
            raise TypeError(
                f"Expected PlexPlaylistID, got {type(playlist_id).__name__}"
            )

        try:
            return PlexPlaylist(
                library=self,
                data=self.api.playlist.get(int(playlist_id)),
                tracks_data=self.api.playlist.get_items(int(playlist_id)),
            )
        except HTTPError as e:
            log.debug(
                f"Failed to get playlist for {playlist_id=}, likely invalid id: {e}"
            )
            return None

    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: Sequence[PlexTrack] | None = None,
    ):
        pl = PlexPlaylist(
            self,
            self.api.playlist.create(name),
        )

        with pl.edit():
            pl.description = description
            if tracks:
                pl.tracks = tracks

        return pl

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
    def tracks(self) -> Iterable[PlexTrack]:
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

    # --------------------------- IDLookup protocol ------------------------------ #

    def find_by_ids(
        self,
        ids: Iterable[TrackID],
        path_rewrite: PathRewrite | None = None,
        file_cache: FileCache | None = None,
    ) -> PlexTrack | None:
        """Find a track by its identifiers.

        Prioritizes PlexTrackID, then FilePath, then ISRC (via file metadata).
        """
        # Extract known ID types
        plex_id: str | None = None
        file_paths: list[FilePath] = []
        isrc: str | None = None
        for tid in ids:
            if isinstance(tid, PlexTrackID):
                plex_id = str(tid)
            elif isinstance(tid, FilePath):
                file_paths.append(tid)
            elif isinstance(tid, ISRC):
                isrc = str(tid)

        for track in self.tracks:
            if plex_id and track.id == plex_id:
                return track
            for fp in file_paths:
                if track.path and fp.path == track.path:
                    return track
            if isrc:
                local_track = track.get_local_track(
                    path_rewrite=path_rewrite,
                    file_cache=file_cache,
                )
                if local_track.isrc == isrc:
                    return track

        return None
