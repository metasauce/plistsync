from unittest.mock import Mock
from plistsync.services.tidal.playlist import TidalPlaylistCollection
from tests.abc.playlist import TestMultiRequestPlaylistCollection


class TestsTidalPlaylist(TestMultiRequestPlaylistCollection):
    """Unit tests for the spotify playlist collection."""

    Playlist = TidalPlaylistCollection

    def create_playlist(self) -> TidalPlaylistCollection:
        pl = TidalPlaylistCollection(Mock(), "A name", "some description")
        pl._refetch_tracks = Mock()
        return pl

    # TODO: Add tests for remote_method implementations
