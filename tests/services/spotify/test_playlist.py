from unittest.mock import Mock

import pytest
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponseFull
from plistsync.services.spotify.playlist import SpotifyPlaylist
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestSpotifyPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(self, playlist_data: SpotifyApiPlaylistResponseFull):
        self.playlist_data = playlist_data

    def create_playlist(self) -> SpotifyPlaylist:
        return SpotifyPlaylist(Mock(), self.playlist_data)

    # TODO: Add tests for remote_methods
