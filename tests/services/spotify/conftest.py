import pytest
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponseFull


@pytest.fixture
def playlist_data() -> SpotifyApiPlaylistResponseFull:
    playlist_data: SpotifyApiPlaylistResponseFull = {
        "collaborative": False,
        "description": "My favorite rock songs from the 80s",
        "external_urls": {
            "spotify": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        },
        "href": "https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M",
        "id": "37i9dQZF1DXcBWIGoYBM5M",
        "images": [
            {
                "url": "https://i.scdn.co/image/ab67616d00001e02",
                "width": 640,
                "height": 640,
            }
        ],
        "name": "Rock Classics",
        "owner": {
            "external_urls": {"spotify": "https://open.spotify.com/user/spotify"},
            "href": "https://api.spotify.com/v1/users/spotify",
            "id": "spotify",
            "type": "user",
            "uri": "spotify:user:spotify",
            "display_name": "Spotify",
        },
        "public": True,
        "snapshot_id": "MTMsMDAwMDAwMDAsMDAwMDAwMDAwMDAwMDAwMDA=",
        "type": "playlist",
        "uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
        "items": {
            "href": "https://api.spotify.com/v1/playlists/37i9dQZF1DXcBWIGoYBM5M/tracks",
            "total": 1,
            "next": None,
            "items": [
                {
                    "added_at": "2024-01-15T10:30:00Z",
                    "added_by": {
                        "external_urls": {
                            "spotify": "https://open.spotify.com/user/123456"
                        },
                        "href": "https://api.spotify.com/v1/users/123456",
                        "id": "123456",
                        "type": "user",
                        "uri": "spotify:user:123456",
                    },
                    "is_local": False,
                    "primary_color": None,
                    "track": {
                        "preview_url": "https://p.scdn.co/mp3-preview/preview.mp3",
                        "available_markets": ["US", "GB", "DE"],
                        "explicit": False,
                        "type": "track",
                        "episode": False,
                        "track": True,
                        "album": {
                            "available_markets": ["US", "GB", "DE"],
                            "type": "album",
                            "album_type": "album",
                            "href": "https://api.spotify.com/v1/albums/4aawyAB9vmqN3uQEFFjwkQ",
                            "id": "4aawyAB9vmqN3uQEFFjwkQ",
                            "images": [
                                {
                                    "url": "https://i.scdn.co/image/ab67616d00001e02",
                                    "width": 640,
                                    "height": 640,
                                }
                            ],
                            "name": "Back in Black",
                            "release_date": "1980-07-25",
                            "release_date_precision": "day",
                            "uri": "spotify:album:4aawyAB9vmqN3uQEFFjwkQ",
                            "artists": [
                                {
                                    "external_urls": {
                                        "spotify": "https://open.spotify.com/artist/7mnBLXK823vNxN3UWB7Gfz"
                                    },
                                    "href": "https://api.spotify.com/v1/artists/7mnBLXK823vNxN3UWB7Gfz",
                                    "id": "7mnBLXK823vNxN3UWB7Gfz",
                                    "name": "AC/DC",
                                    "type": "artist",
                                    "uri": "spotify:artist:7mnBLXK823vNxN3UWB7Gfz",
                                }
                            ],
                            "external_urls": {
                                "spotify": "https://open.spotify.com/album/4aawyAB9vmqN3uQEFFjwkQ"
                            },
                            "total_tracks": 10,
                        },
                        "artists": [
                            {
                                "external_urls": {
                                    "spotify": "https://open.spotify.com/artist/7mnBLXK823vNxN3UWB7Gfz"
                                },
                                "href": "https://api.spotify.com/v1/artists/7mnBLXK823vNxN3UWB7Gfz",
                                "id": "7mnBLXK823vNxN3UWB7Gfz",
                                "name": "AC/DC",
                                "type": "artist",
                                "uri": "spotify:artist:7mnBLXK823vNxN3UWB7Gfz",
                            }
                        ],
                        "disc_number": 1,
                        "track_number": 1,
                        "duration_ms": 255000,
                        "external_ids": {"isrc": "USCDC1871234"},
                        "external_urls": {
                            "spotify": "https://open.spotify.com/track/0nJW01T7XtvIA1nKoMMuHJ"
                        },
                        "href": "https://api.spotify.com/v1/tracks/0nJW01T7XtvIA1nKoMMuHJ",
                        "id": "0nJW01T7XtvIA1nKoMMuHJ",
                        "name": "Back in Black",
                        "popularity": 85,
                        "uri": "spotify:track:0nJW01T7XtvIA1nKoMMuHJ",
                        "is_local": False,
                    },
                    "video_thumbnail": {"url": None},
                }
            ],
        },
    }
    return playlist_data
