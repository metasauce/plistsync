import pytest

from plistsync.services.spotify import SpotifyTrackID


class TestSpotifyTrackID:
    @pytest.mark.parametrize(
        "input_str, expected_id",
        [
            # ID only
            ("3n3Ppam7vgaVa1iaRUc9Lp", "3n3Ppam7vgaVa1iaRUc9Lp"),
            # Short URI format
            ("spotify:3n3Ppam7vgaVa1iaRUc9Lp", "3n3Ppam7vgaVa1iaRUc9Lp"),
            # URI formats
            ("spotify:track:3n3Ppam7vgaVa1iaRUc9Lp", "3n3Ppam7vgaVa1iaRUc9Lp"),
            # URL formats with protocol
            (
                "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
            (
                "http://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
            # URL formats without protocol
            (
                "open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
            # URLs with query parameters
            (
                "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp?si=abc123",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
            # URLs with fragments
            (
                "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp#section",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
            (
                "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp?si=abc123#section",
                "3n3Ppam7vgaVa1iaRUc9Lp",
            ),
        ],
    )
    def test_valid_inputs(self, input_str, expected_id):
        """Test extracting ID from valid Spotify URIs and URLs."""
        assert SpotifyTrackID.parse(input_str).id == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong format
            "spotify:playlist:3n3Ppam7vgaVa1iaRUc9Lp",  # Wrong type (playlist instead of track)
            "spotify:artist:3n3Ppam7vgaVa1iaRUc9Lp",  # Wrong type (artist)
            "spotify:album:3n3Ppam7vgaVa1iaRUc9Lp",  # Wrong type (album)
            # Wrong domain
            "https://open.spotify.com/playlist/3n3Ppam7vgaVa1iaRUc9Lp",  # Playlist URL
            "https://music.apple.com/track/3n3Ppam7vgaVa1iaRUc9Lp",  # Wrong service
            "https://youtube.com/track/3n3Ppam7vgaVa1iaRUc9Lp",  # Wrong service
            # Malformed
            "spotify:track:",  # No ID
            "open.spotify.com/track/",  # No ID
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test that invalid Spotify track URIs and URLs raise ValueError."""
        with pytest.raises(ValueError):
            SpotifyTrackID.parse(invalid_input)
