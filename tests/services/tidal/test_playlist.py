from unittest.mock import Mock
from plistsync.services.tidal.playlist import TidalPlaylistCollection
from tests.abc.playlist import TestMultiRequestPlaylistCollection


class TestsTidalPlaylist(TestMultiRequestPlaylistCollection):
    """Unit tests for the spotify playlist collection."""

    Playlist = TidalPlaylistCollection

    def create_playlist(self) -> TidalPlaylistCollection:
        return TidalPlaylistCollection(Mock(), "A name", "some description")

    # TODO: Add tests for remote_methods
