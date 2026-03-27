from unittest.mock import Mock
from plistsync.services.spotify.playlist import SpotifyPlaylistCollection
from tests.abc.playlist import TestMultiRequestPlaylistCollection


class TestSpotifyPlaylist(TestMultiRequestPlaylistCollection):
    """Unit tests for the spotify playlist collection."""

    Playlist = SpotifyPlaylistCollection

    def create_playlist(self) -> SpotifyPlaylistCollection:
        return SpotifyPlaylistCollection(Mock(), "A name", "some description")

    # TODO: Add tests for remote_methods
