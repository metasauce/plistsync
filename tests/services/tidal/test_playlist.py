from __future__ import annotations
from unittest.mock import Mock

import pytest
from plistsync.services.tidal.playlist import TidalPlaylist, TidalPlaylistID
from tests.abc.playlist import TestMultiRequestServicePlaylistBase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plistsync.services.tidal.api_types import PlaylistResource


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
            (
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            # URI format
            (
                "tidal:playlist:33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            # URL formats with protocol
            (
                "https://listen.tidal.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            (
                "http://listen.tidal.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            # URL formats without protocol
            (
                "listen.tidal.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            # Alternate browse URL
            (
                "https://tidal.com/browse/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            # URLs with query parameters / fragments
            (
                "https://listen.tidal.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157?foo=bar",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            (
                "https://listen.tidal.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157#section",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
            (
                "https://tidal.com/browse/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157?x=1#y",
                "33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            ),
        ],
    )
    def test_valid_inputs(self, input_str, expected_id):
        """Test extracting ID from valid TIDAL inputs."""
        assert TidalPlaylistID.parse(input_str).id == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong type
            "tidal:track:33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            "tidal:album:33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            # Wrong domain / service
            "https://open.spotify.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            "https://music.apple.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            "https://youtube.com/playlist/33f585f7-3da8-4e4a-a7f9-403ac9cdd157",
            # Malformed
            "tidal:playlist:",  # no id
            "listen.tidal.com/playlist/",  # no id
            "https://listen.tidal.com/playlist/",  # no id
            # Non-numeric id
            "abcdefg",
            "tidal:playlist:non_hex_chars",
            # Garbage
            "just a random string",
            "",
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            TidalPlaylistID.parse(invalid_input)
