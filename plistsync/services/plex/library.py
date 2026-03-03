from collections.abc import Generator, Iterable, Sequence
from functools import cached_property
from pathlib import Path
from typing import Any, overload

from typing_extensions import override

from plistsync.core import GlobalTrackIDs, LibraryCollection, PathRewrite
from plistsync.core.collection import GlobalLookup, LocalLookup, TrackStream
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log
from plistsync.services.local.track import FileCache
from plistsync.services.plex.playlist import PlexPlaylistCollection

from .api import PlexApi
from .track import PlexTrack


class PlexLibrarySectionCollection(
    LibraryCollection[PlexTrack], LocalLookup, GlobalLookup, TrackStream[PlexTrack]
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
