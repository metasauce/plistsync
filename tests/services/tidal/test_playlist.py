from unittest.mock import Mock

import pytest
from plistsync.services.tidal.api_types import PlaylistResource
from plistsync.services.tidal.playlist import TidalPlaylist
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestsTidalPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(self, playlist_resource: PlaylistResource, items_lookup):
        self.playlist_data = playlist_resource
        self.items_lookup = items_lookup

    def create_playlist(self) -> TidalPlaylist:
        self.playlist_data["attributes"]["numberOfItems"] = 1
        pl = TidalPlaylist(Mock(), self.playlist_data, self.items_lookup)
        pl._refetch_tracks = Mock()
        return pl

    # TODO: Add tests for remote_method implementations
