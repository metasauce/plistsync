from __future__ import annotations
from unittest.mock import Mock
import pytest
from plistsync.services.plex.playlist import PlexPlaylist, PlexPlaylistID
from tests.abc.playlist import TestMultiRequestServicePlaylistBase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plistsync.services.plex.api_types import (
        PlexApiPlaylistResponse,
        PlexApiPlaylistTrackResponse,
    )


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


class TestPlexPlaylistID:
    @pytest.mark.parametrize(
        "input_value, expected_id",
        [
            # Integer ID (primary Plex format)
            (12345, 12345),
            # String integer
            ("12345", 12345),
            # ratingKey (common Plex identifier)
            ("ratingKey=12345", 12345),
            # Plex web URL
            ("https://app.plex.tv/web/app#!/playlist/12345", 12345),
            ("http://127.0.0.1:32400/playlists/12345", 12345),
            # Plex protocol URL
            ("plex://playlist/12345", 12345),
            # Library section URLs
            ("/playlists/12345", 12345),
            ("plex://localhost:32400/playlists/12345", 12345),
            # Common uri
            ("plex:playlist:12345", 12345),
        ],
    )
    def test_valid_inputs(self, input_value: str | int, expected_id: int) -> None:
        """Test PlexPlaylistID.parse() extracts correct integer ID."""
        result = PlexPlaylistID.parse(input_value)
        assert result.id == expected_id
        assert isinstance(result, PlexPlaylistID)

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong Plex types
            "ratingKey=abc123",  # non-numeric
            "playlist=12345",  # wrong prefix
            # Other services
            "spotify:playlist:abc123",
            "https://open.spotify.com/playlist/abc123",
            # Spotify ID starting with a digit must not match the numeric
            # plex patterns (regression: 'playlist/(\d+)' matched '2WDLy...').
            "https://open.spotify.com/playlist/2WDLyDwK2feBaApAG8AnVI",
            "tidal:playlist:12345678",
            # Malformed/missing ID
            "https://app.plex.tv/web/app#!/playlist/",
            "plex://playlist/",
            "ratingKey=",
            "",
            # Non-Plex URLs
            "https://youtube.com/playlist?v=abc123",
            # Random garbage
            "not a plex id",
            "123.45",  # float
        ],
    )
    def test_invalid_inputs(self, invalid_input: str | int) -> None:
        """Test invalid inputs raise ValueError."""
        with pytest.raises(ValueError, match="Invalid Plex playlist ID"):
            PlexPlaylistID.parse(invalid_input)
