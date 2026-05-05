from unittest.mock import Mock

import pytest
from plistsync.services.tidal.api_types import PlaylistResource
from plistsync.services.tidal.playlist import TidalPlaylist, TidalPlaylistID
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestsTidalPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the tidal playlist collection."""

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


class TestTidalPlaylistID:
    @pytest.mark.parametrize(
        "input_str, expected_id",
        [
            # ID only (numeric)
            ("12345678", "12345678"),
            # URI format
            ("tidal:playlist:12345678", "12345678"),
            # URL formats with protocol
            ("https://listen.tidal.com/playlist/12345678", "12345678"),
            ("http://listen.tidal.com/playlist/12345678", "12345678"),
            # URL formats without protocol
            ("listen.tidal.com/playlist/12345678", "12345678"),
            # Alternate browse URL
            ("https://tidal.com/browse/playlist/12345678", "12345678"),
            # URLs with query parameters / fragments
            ("https://listen.tidal.com/playlist/12345678?foo=bar", "12345678"),
            ("https://listen.tidal.com/playlist/12345678#section", "12345678"),
            ("https://tidal.com/browse/playlist/12345678?x=1#y", "12345678"),
        ],
    )
    def test_valid_inputs(self, input_str, expected_id):
        """Test extracting ID from valid TIDAL inputs."""
        assert TidalPlaylistID.parse(input_str).id == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong type
            "tidal:track:12345678",
            "tidal:album:12345678",
            # Wrong domain / service
            "https://open.spotify.com/playlist/12345678",
            "https://music.apple.com/playlist/12345678",
            "https://youtube.com/playlist/12345678",
            # Malformed
            "tidal:playlist:",  # no id
            "listen.tidal.com/playlist/",  # no id
            "https://listen.tidal.com/playlist/",  # no id
            # Non-numeric id
            "abcdefg",
            "tidal:playlist:abc123",
            # Garbage
            "just a random string",
            "",
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            TidalPlaylistID.parse(invalid_input)
