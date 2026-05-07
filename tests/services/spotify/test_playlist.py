from unittest.mock import Mock

import pytest
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponseFull
from plistsync.services.spotify.playlist import SpotifyPlaylist, SpotifyPlaylistID
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestSpotifyPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(self, playlist_data: SpotifyApiPlaylistResponseFull):
        self.playlist_data = playlist_data

    def create_playlist(self) -> SpotifyPlaylist:
        return SpotifyPlaylist(Mock(), self.playlist_data)

    # TODO: Add tests for remote_methods


class TestSpotifyPlaylistID:
    @pytest.mark.parametrize(
        "input_str, expected_id",
        [
            # ID only
            ("37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"),
            # Short URI format
            ("spotify:37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"),
            # URI formats
            ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"),
            # URL formats with protocol
            (
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            (
                "http://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            # URL formats without protocol
            (
                "open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            # URLs with query parameters
            (
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            # URLs with fragments
            (
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M#section",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
            (
                "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc123#section",
                "37i9dQZF1DXcBWIGoYBM5M",
            ),
        ],
    )
    def test_valid_inputs(self, input_str, expected_id):
        """Test extracting ID from valid Spotify URIs and URLs."""
        assert SpotifyPlaylistID.parse(input_str).id == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong format
            "spotify:track:37i9dQZF1DXcBWIGoYBM5M",  # Wrong type (track instead of playlist)
            "spotify:artist:37i9dQZF1DXcBWIGoYBM5M",  # Wrong type (artist)
            "spotify:album:37i9dQZF1DXcBWIGoYBM5M",  # Wrong type (album)
            # Wrong domain
            "https://open.spotify.com/track/37i9dQZF1DXcBWIGoYBM5M",  # Track URL
            "https://music.apple.com/playlist/37i9dQZF1DXcBWIGoYBM5M",  # Wrong service
            "https://youtube.com/playlist/37i9dQZF1DXcBWIGoYBM5M",  # Wrong service
            # Malformed
            "spotify:playlist:",  # No ID
            "open.spotify.com/playlist/",  # No ID
            "https://open.spotify.com/playlist/",  # No ID
            "just a random string",
            "",
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            SpotifyPlaylistID.parse(invalid_input)
