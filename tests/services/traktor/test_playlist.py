from unittest.mock import Mock
from plistsync.services.traktor.playlist import NMLPlaylistCollection
from tests.abc.playlist import (
    TestPlaylistCollection,
)


class TestsTidalPlaylist(TestPlaylistCollection):
    """Unit tests for the spotify playlist collection."""

    Playlist = NMLPlaylistCollection
    supports_description = False

    def create_playlist(self) -> NMLPlaylistCollection:
        return NMLPlaylistCollection(Mock(), "A name")

    # TODO: Migrate tests from test_collection!
