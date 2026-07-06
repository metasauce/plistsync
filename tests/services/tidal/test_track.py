import pytest

from plistsync.services.tidal.track import TidalTrackID


class TestTidalTrackID:
    @pytest.mark.parametrize(
        "input_str, expected_id",
        [
            # ID only
            ("123456789", "123456789"),
            # URI format
            ("tidal:track:123456789", "123456789"),
            # URL formats with protocol
            (
                "https://listen.tidal.com/track/123456789",
                "123456789",
            ),
            (
                "http://listen.tidal.com/track/123456789",
                "123456789",
            ),
            # URL formats without protocol
            (
                "listen.tidal.com/track/123456789",
                "123456789",
            ),
            # Alternate domain
            (
                "https://tidal.com/track/123456789",
                "123456789",
            ),
            # Browse URL
            (
                "https://tidal.com/browse/track/123456789",
                "123456789",
            ),
            # URLs with query parameters
            (
                "https://listen.tidal.com/track/123456789?foo=bar",
                "123456789",
            ),
            # URLs with fragments
            (
                "https://listen.tidal.com/track/123456789#section",
                "123456789",
            ),
        ],
    )
    def test_valid_inputs(self, input_str, expected_id):
        """Test extracting ID from valid TIDAL URIs and URLs."""
        assert TidalTrackID.parse(input_str).id == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong type
            "tidal:playlist:123456789",  # Wrong type (playlist instead of track)
            "tidal:album:123456789",  # Wrong type (album)
            "tidal:artist:123456789",  # Wrong type (artist)
            # Wrong domain
            "https://tidal.com/playlist/123456789",  # Playlist URL
            "https://music.apple.com/track/123456789",  # Wrong service
            "https://open.spotify.com/track/123456789",  # Wrong service
            # Malformed
            "tidal:track:",  # No ID
            "listen.tidal.com/track/",  # No ID
            "https://listen.tidal.com/track/",  # No ID
            "just a random string$",
            "",
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test that invalid TIDAL track URIs and URLs raise ValueError."""
        with pytest.raises(ValueError):
            TidalTrackID.parse(invalid_input)
