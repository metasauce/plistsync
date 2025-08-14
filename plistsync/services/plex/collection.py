from pprint import pprint
from typing import Generator

from plistsync.core import Collection, Track, TrackIdentifiers
from plistsync.logger import log
from plistsync.services.plex.api_types import PlexApiPlaylistResponse

from .api import (
    fetch_playlist,
    fetch_playlist_items,
    playlist_id_or_name,
    resolve_playlist_id,
    resolve_section_id,
)
from .track import PathRewrite, PlexTrack


class PlexLibrarySectionCollection(Collection):
    """A collection of all tracks in a Plex library section.

    (Section is the API term they use, in the frontend, this would be a music library.)
    """

    section_id: int

    # Requested data from Plex API
    plex_data: dict
    plex_items_data: dict

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


class PlexPlaylistCollection(Collection):
    """A collection of all tracks in a Plex playlist."""

    playlist_id: int

    # Requested data from Plex API
    plex_playlist_data: list[PlexApiPlaylistResponse]
    plex_items_data: dict

    path_rewrite: None | PathRewrite = None

    def __init__(
        self,
        playlist_id: str | int,
        path_rewrite: None | PathRewrite = None,
    ):
        """Initialize the PlexPlaylistCollection from plex given a playlist id.

        Parameters
        ----------
        playlist_id : str | int
            The Name or ID of the Plex playlist to fetch.
        """

        self.playlist_id = resolve_playlist_id(playlist_id)
        self.path_rewrite = path_rewrite

        # TODO: maybe fetch on access, not init?
        self.plex_playlist_data = fetch_playlist(playlist_id)
        self.plex_items_data = fetch_playlist_items(playlist_id)

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
        for item in self.plex_items_data["Metadata"]:
            yield PlexTrack(item, path_rewrite=self.path_rewrite)

    @property
    def name(self) -> str:
        """Get the name of the playlist."""
        return self.plex_playlist_data[0]["title"]
