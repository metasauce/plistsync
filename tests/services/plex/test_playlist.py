from unittest.mock import Mock
from plistsync.services.plex.playlist import PlexPlaylistCollection
from tests.abc.playlist import TestMultiRequestPlaylistCollection


class TestSpotifyPlaylist(TestMultiRequestPlaylistCollection):
    """Unit tests for the spotify playlist collection."""

    Playlist = PlexPlaylistCollection

    def create_playlist(self) -> PlexPlaylistCollection:
        return PlexPlaylistCollection(Mock(), "A name", "some description")

    # TODO: Add tests for remote_method implementations
