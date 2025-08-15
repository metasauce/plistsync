import itertools
from functools import cached_property
from pathlib import Path
from pprint import pprint
from typing import Generator, Sequence

from plistsync.core import Collection, Track, TrackIdentifiers
from plistsync.logger import log
from plistsync.services.plex.api_types import (
    PlexApiPlaylistResponse,
    PlexApiTrackResponse,
)

from .api import (
    fetch_playlist,
    fetch_playlist_items,
    fetch_section_root_path,
    fetch_tracks,
    resolve_playlist_id,
    resolve_section_id,
)
from .track import PathRewrite, PlexTrack


class PlexLibrarySectionCollection(Collection):
    """A collection of all tracks in a Plex library section.

    (Section is the API term they use, in the frontend, this would typically be a music library.)

    Notes
    -----
    - Plex Collections are lazy loaded, but once loaded (by iterate) they are cached.
    - To refresh the state from the server, you need to recreate the collection instance.
    """

    section_id: int

    path_rewrite: None | PathRewrite = None

    def __init__(
        self,
        section_id: str | int,
        path_rewrite: None | PathRewrite = None,
    ):
        """Initialize the PlexLibraryCollection from plex given a section id.

        Parameters
        ----------
        section_id : str | int
            The Name or ID of the Plex library section to fetch.
        """
        self.section_id = resolve_section_id(section_id)
        self.path_rewrite = path_rewrite

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

    def is_iterable(self) -> bool:
        return True

    def preload(self) -> None:
        """Preload the collection data.

        This ensures that the collection is fully loaded locally in memory
        and can be iterated over without additional API calls.
        """
        _ = list(self)

    @cached_property
    def locations(self) -> list[Path]:
        """To locations (on disk) of the section."""
        return fetch_section_root_path(self.section_id)


class PlexPlaylistCollection(Collection):
    """
    A collection of all tracks in a Plex playlist.

    Notes
    -----
    - Plex Playlist Collections are loaded once during initialization.
    - To refresh the state from the server, you need to recreate the collection instance.
    """

    playlist_id: int

    # Requested data from Plex API
    plex_playlist_data: PlexApiPlaylistResponse
    plex_items_data: list[PlexApiTrackResponse]

    path_rewrite: None | PathRewrite = None

    def __init__(
        self,
        playlist_name_or_id: str | int,
        path_rewrite: None | PathRewrite = None,
    ):
        """Initialize the PlexPlaylistCollection from plex given a playlist id.

        Parameters
        ----------
        playlist_id : str | int
            The Name or ID of the Plex playlist to fetch.
        """

        self.playlist_id = resolve_playlist_id(playlist_name_or_id)
        self.path_rewrite = path_rewrite

        # TODO: maybe fetch on access, not init?
        self.plex_playlist_data = fetch_playlist(self.playlist_id)
        self.plex_items_data = fetch_playlist_items(self.playlist_id)

    def find_by_identifiers(self, identifiers: TrackIdentifiers) -> Track | None:
        return super().find_by_identifiers(identifiers)

    def __iter__(self) -> Generator[Track, None, None]:
        """Iterate over the tracks in the collection.

        Returns
        -------
        Generator[Track, None, None]
            A generator yielding PlexTrack objects.
        """
        # log.warning(self.plex_items_data)
        for item in self.plex_items_data:
            yield PlexTrack(item, path_rewrite=self.path_rewrite)

    @property
    def name(self) -> str:
        """Get the name of the playlist."""
        name = self.plex_playlist_data.get("title")
        if name is None:
            raise ValueError("Playlist name not found in plex_playlist_data.")
        return name
