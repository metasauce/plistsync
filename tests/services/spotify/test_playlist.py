from unittest.mock import Mock

import pytest
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponseFull
from plistsync.services.spotify.playlist import SpotifyPlaylistCollection
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestSpotifyPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(self, playlist_data: SpotifyApiPlaylistResponseFull):
        self.playlist_data = playlist_data

    def create_playlist(self) -> SpotifyPlaylistCollection:
        return SpotifyPlaylistCollection(Mock(), self.playlist_data)

    # TODO: Add tests for remote_methods
