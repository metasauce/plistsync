from unittest.mock import Mock
import pytest
from plistsync.services.plex.api_types import (
    PlexApiPlaylistResponse,
    PlexApiPlaylistTrackResponse,
)
from plistsync.services.plex.playlist import PlexPlaylist
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestPlexPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the plex playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(
        self,
        playlist_data: PlexApiPlaylistResponse,
        playlist_track_data: PlexApiPlaylistTrackResponse,
    ):
        self.playlist_data = playlist_data
        self.playlist_track_data = playlist_track_data

    def create_playlist(self) -> PlexPlaylist:
        self.playlist_data["leafCount"] = 1
        return PlexPlaylist(Mock(), self.playlist_data, [self.playlist_track_data])

    # TODO: Add tests for remote_method implementations
