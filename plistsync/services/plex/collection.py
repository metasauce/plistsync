import itertools
from functools import cached_property
from pathlib import Path
from pprint import pprint
from typing import Any, Generator, Iterator, Sequence

from plistsync.core import Collection, GlobalTrackIDs, PathRewrite, Track
from plistsync.core.collection import TrackStream
from plistsync.logger import log
from plistsync.services.plex.api_types import (
    PlexApiPlaylistResponse,
    PlexApiTrackResponse,
)

from .api import (
    fetch_playlist,
    fetch_playlist_items,
    fetch_playlists,
    fetch_section_root_path,
    fetch_tracks,
    insert_track_into_playlist_by_id,
    resolve_playlist_id,
    resolve_section_id,
)
from .track import PlexTrack


class PlexLibrarySectionCollection(Collection):
    """A collection of all tracks in a Plex library section.

    (Section is the API term they use, in the frontend, this would typically be a music library.)

    Notes
    -----
    - Plex Collections are lazy loaded, but once loaded (by iterate) they are cached.
    - To refresh the state from the server, you need to recreate the collection instance.
    """

    section_id: int

    def __init__(
        self,
        section_id: str | int,
    ):
        """Initialize the PlexLibraryCollection from plex given a section id.

        Parameters
        ----------
        section_id : str | int
            The Name or ID of the Plex library section to fetch.
        """
        self.section_id = resolve_section_id(section_id)

    def preload(self) -> None:
        """Preload the collection data.

        This ensures that the collection is fully loaded locally in memory
        and can be iterated over without additional API calls.
        """
        _ = list(self)

    @property
    def playlists(self) -> Iterator["PlexPlaylistCollection"]:
        """Get all playlists in the library as PlexPlaylistCollection objects."""

        all_playlists = fetch_playlists()
        for pl_data in all_playlists:
            # we might also want to filter: smart=False
            if pl_data.get("playlistType") != "audio":
                continue
            pl = PlexPlaylistCollection(
                pl_data,
                library_collection=self,
            )
            yield pl

    @cached_property
    def locations(self) -> list[Path]:
        """To locations (on disk) of the section."""
        return fetch_section_root_path(self.section_id)

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
                fetch_tracks(
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
    - To refresh the state from the server, you need to recreate the collection instance.
    - Plex Playlists do not seem to be linked to a particular section_id - they can contain tracks from multiple libraries.
    """

    playlist_id: int

    # Requested data from Plex API
    plex_playlist_data: PlexApiPlaylistResponse
    plex_items_data: list[PlexApiTrackResponse]

    # parent library for adding tracks
    library_collection: PlexLibrarySectionCollection | None = None

    def __init__(
        self,
        playlist_name_id_or_data: str | int | PlexApiPlaylistResponse,
        library_collection: PlexLibrarySectionCollection | None = None,
    ):
        """Initialize the PlexPlaylistCollection from plex given a playlist id.

        Parameters
        ----------
        playlist_id : str | int
            The Name or ID of the Plex playlist to fetch.
        library_collection : PlexLibrarySectionCollection | None
            The Plex library collection in which the playlist lives.
            Without a library, no tracks can be added to the playlist.
        """

        if isinstance(playlist_name_id_or_data, (str, int)):
            self.playlist_id = resolve_playlist_id(playlist_name_id_or_data)
            self.plex_playlist_data = fetch_playlist(self.playlist_id)
        else:
            self.plex_playlist_data = playlist_name_id_or_data
            self.playlist_id = int(self.plex_playlist_data["ratingKey"])

        # TODO: maybe fetch on access, not init?
        self.plex_items_data = fetch_playlist_items(self.playlist_id)
        self.library_collection = library_collection

    @property
    def is_smart(self) -> bool:
        """Check if the playlist is a smart playlist.

        Tracks cannot be added to smart playlists.
        """
        return self.plex_playlist_data.get("smart", False)

    @property
    def name(self) -> str:
        """Get the name of the playlist."""
        name = self.plex_playlist_data.get("title")
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
        path: Path | str,
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
        if library_collection is None:
            raise ValueError("Library collection needs to be set to insert by path.")

        path = Path(path)

        # Find the track in the library collection
        track = next((t for t in library_collection if t.path == path), None)
        if track is None:
            raise ValueError(f"Track with path {path} not found in library collection.")

        return insert_track_into_playlist_by_id(
            track_id=track.plex_id, playlist_id=self.playlist_id
        )

    def insert_by_id(self, track_id: str | int):
        """Insert a track into the playlist by its Plex ID."""
        if self.is_smart:
            raise ValueError("Cannot insert tracks into a smart playlist.")

        return insert_track_into_playlist_by_id(
            track_id=track_id, playlist_id=self.playlist_id
        )

    def __repr__(self) -> str:
        return (
            f"PlexPlaylistCollection {self.playlist_id} "
            + f'["{self.name}", {len(self.plex_items_data)} tracks]'
        )

    # --------------------------------- Protocols -------------------------------- #

    def __iter__(self) -> Iterator[PlexTrack]:
        """Iterate over the tracks in the collection.

        Returns
        -------
        Generator[Track, None, None]
            A generator yielding PlexTrack objects.
        """
        for item in self.plex_items_data:
            yield PlexTrack(item)
