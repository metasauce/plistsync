from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from functools import cached_property
from pathlib import Path, PurePath
from typing import Any

from plistsync.core import Collection, LibraryCollection
from plistsync.core.collection import TrackStream
from plistsync.services.plex.api_types import (
    PlexApiPlaylistResponse,
    PlexApiTrackResponse,
)

from .api import PlexApi
from .track import PlexTrack


class PlexLibrarySectionCollection(LibraryCollection):
    """A collection of all tracks in a Plex library section.

    `section` is the term plex use in the backend, this aligns in the plex frontend
    this is often called `library`.

    Notes
    -----
    - Plex Collections are lazy loaded, but once loaded (by iterate) they are cached.
    - To refresh the state from the server, you need to recreate the collection
    instance.
    """

    section_id: int
    api: PlexApi

    def __init__(
        self,
        section_id: str | int,
        server_url: str | None = None,
        server_name: str | None = None,
    ):
        """Initialize the PlexLibraryCollection from plex given a section id.

        Parameters
        ----------
        section_id : str | int
            The Name or ID of the Plex library section to fetch.
        server_url : str, optional
            The server for this collection. If not specified, loaded from config.
        """
        self.api = PlexApi(server_url=server_url, server_name=server_name)
        self.section_id = self.api.converts.section_name_to_id(section_id)

    def preload(self) -> None:
        """Preload the collection data.

        This ensures that the collection is fully loaded locally in memory
        and can be iterated over without additional API calls.
        """
        _ = list(self)

    @property
    def playlists(self) -> Iterator[PlexPlaylistCollection]:
        """Get all playlists in the library as PlexPlaylistCollection objects."""

        for pl_data in self.api.playlist.fetch_playlists():
            # we might also want to filter: smart=False
            if pl_data.get("playlistType") != "audio":
                continue
            pl = PlexPlaylistCollection(
                library_collection=self,
                playlist_name_id_or_data=pl_data,
            )
            yield pl

    def get_playlist(
        self, name: Path | str, allow_name=True
    ) -> PlexPlaylistCollection | None:
        if isinstance(name, Path):
            raise ValueError("Playlist name cannot be a Path")

        for pl in self.playlists:
            if pl.playlist_id == name or (allow_name) and pl.name == name:
                return pl

        return None

    @cached_property
    def locations(self) -> list[Path]:
        """To locations (on disk) of the section."""
        sections = self.api.sections()
        paths: list[Path] = []
        for section in sections["MediaContainer"].get("Directory", []):
            if int(section.get("key")) == int(self.section_id):
                locations = section.get("Location", [{}])
                for loc in locations:
                    if "path" in loc:
                        paths.append(Path(loc.get("path")))

        return paths

    # ------------------------------- Protocols ------------------------------ #

    _tracks: Sequence[PlexTrack] | None = None
    _page_size: int = 5000
    _fetched: bool = False

    def __iter__(self) -> Generator[PlexTrack, None, None]:
        """Iterate over the tracks in the collection."""

        if self._tracks is None or not self._fetched:
            self._tracks = []
            tracks_iter = map(
                lambda item: PlexTrack(item),
                self.api.track.fetch_tracks(
                    section_id=self.section_id,
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


class PlexPlaylistCollection(Collection, TrackStream):
    """
    A collection of all tracks in a Plex playlist.

    # TODO: PS 2025-08-17: I think we should make the
    # libraray_collection mandatory, and match the `create=True`
    # behavior that we use in Traktor. I dont see a Scenario where
    # we would want to create a playlist without a library collection.

    Notes
    -----
    - Plex Playlist Collections are loaded once during initialization.
    - To refresh the state from the server, you need to recreate
    - the collection instance.
    - Plex Playlists do not seem to be linked to a particular section_id
    - they can contain tracks from multiple libraries.
    """

    # parent library for adding tracks
    library_collection: PlexLibrarySectionCollection

    # Requested data from Plex API
    _playlist_data: PlexApiPlaylistResponse
    _items_data: list[PlexApiTrackResponse]

    def __init__(
        self,
        library_collection: PlexLibrarySectionCollection,
        playlist_name_id_or_data: str | int | PlexApiPlaylistResponse,
        create: bool = False,
    ):
        """Initialize the PlexPlaylistCollection from plex given a playlist id.

        Parameters
        ----------
        library_collection : PlexLibrarySectionCollection
            The Plex library collection in which the playlist lives.
        playlist_id : str | int | PlexApiPlaylistResponse
            The Name or ID of the Plex playlist to fetch, or the playlist data itself.
        create : bool, optional
            Whether to create the playlist if it does not exist. Default is False.
        """

        if create:
            raise NotImplementedError("Creating playlists is not yet implemented.")

        self.library_collection = library_collection

        if isinstance(playlist_name_id_or_data, (str, int)):
            playlist_id = self.api.converts.section_name_to_id(playlist_name_id_or_data)
            self._playlist_data = self.api.playlist.fetch_playlist(playlist_id)
        else:
            self._playlist_data = playlist_name_id_or_data

        # TODO: maybe fetch on access, not init?
        self._items_data = self.api.playlist.fetch_playlist_items(self.playlist_id)

    def refresh(self) -> None:
        """Refresh the playlist data from the Plex server."""
        self._playlist_data = self.api.playlist.fetch_playlist(self.playlist_id)
        self._items_data = self.api.playlist.fetch_playlist_items(self.playlist_id)

    def _add_item_local(self, track_id: str | int) -> None:
        """Add an item to the internal playlist data representation.

        Parameters
        ----------
        track_id : str | int
            The track data to add to the playlist.
        """
        self._items_data.append(self.api.track.fetch_track(track_id))

    @property
    def playlist_id(self) -> int:
        """Get the unique identifier of the playlist (ratingKey)."""
        return int(self._playlist_data["ratingKey"])

    @property
    def api(self) -> PlexApi:
        """Get the Plex API instance associated with this playlist."""
        return self.library_collection.api

    @property
    def is_smart(self) -> bool:
        """Check if the playlist is a smart playlist.

        Tracks cannot be added to smart playlists.
        """
        return self._playlist_data.get("smart", False)

    @property
    def name(self) -> str:
        """Get the name of the playlist."""
        name = self._playlist_data.get("title")
        if name is None:
            raise ValueError("Playlist name not found in plex_playlist_data.")
        return name

    def insert(self, track: Any) -> None:
        """
        PS 2025-08-16: thoughts on `insert` methods.

        I think PlaylistCollections should implement a general `insert` method
        that delegates to the appropriate sub-methods.

        Those sub-methods depend on the service,
        but likely scenarios:
        - insert_by_path
        - insert_by_id (service specific id)

        """
        raise NotImplementedError()

    def insert_by_path(
        self,
        path: PurePath | str,
        library_collection: PlexLibrarySectionCollection | None = None,
    ):
        """
        Insert a track into the playlist by its file path.

        To find the track, this needs a plex library to search,
        either already linked to the playlist, or passed as an argument.

        """
        if self.is_smart:
            raise ValueError("Cannot insert tracks into a smart playlist.")

        library_collection = library_collection or self.library_collection
        path = Path(path)

        # Find the track in the library collection
        track = next((t for t in library_collection if t.path == path), None)
        if track is None:
            raise ValueError(f"Track with path {path} not found in library collection.")

        self.api.playlist.insert_item_into_playlist(
            item_id=track.plex_id,
            playlist_id=self.playlist_id,
            machine_id=self.api.machine_id,
        )
        self._add_item_local(track.plex_id)

    def insert_by_id(self, item_id: str | int):
        """Insert a track into the playlist by its Plex ID."""
        if self.is_smart:
            raise ValueError("Cannot insert tracks into a smart playlist.")

        self.api.playlist.insert_item_into_playlist(
            item_id=item_id,
            playlist_id=self.playlist_id,
            machine_id=self.api.machine_id,
        )
        self._add_item_local(item_id)

    def __repr__(self) -> str:
        return (
            f"PlexPlaylistCollection {self.playlist_id} "
            f'["{self.name}", {len(self._items_data)} tracks]'
        )

    # --------------------------------- Protocols -------------------------------- #

    def __iter__(self) -> Iterator[PlexTrack]:
        """Iterate over the tracks in the collection.

        Returns
        -------
        Generator[Track, None, None]
            A generator yielding PlexTrack objects.
        """
        for item in self._items_data:
            yield PlexTrack(item)
