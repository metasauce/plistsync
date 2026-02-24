import pytest
from unittest.mock import MagicMock, Mock
from pathlib import Path
from plistsync.services.plex.api import PlexApi
from plistsync.services.plex.api_types import (
    PlexApiTrackResponse,
    PlexApiPlaylistResponse,
)


def side_effect_section_name_to_id(name):
    if "Unknown" in name:
        return None
    else:
        return 1


@pytest.fixture
def mock_plex_api() -> Mock:
    """Create a mock PlexApi instance for testing."""
    mock_api = Mock(spec=PlexApi)

    # Mock the converts attribute
    mock_api.converts = Mock()
    mock_api.converts.section_name_to_id = MagicMock(
        side_effect=side_effect_section_name_to_id
    )
    mock_api.converts.playlist_name_to_id = MagicMock(
        side_effect=side_effect_section_name_to_id
    )

    # Mock the sections method
    mock_api.sections = Mock(
        return_value={
            "MediaContainer": {
                "Directory": [
                    {"key": "1", "Location": [{"path": "/mock/music/library"}]}
                ]
            }
        }
    )

    # Mock playlist methods
    mock_api.playlist = Mock()
    mock_api.playlist.all = Mock(return_value=[])
    mock_api.playlist.get = Mock(return_value={"title": "Mockplaylist"})
    mock_api.playlist.get_items = Mock(return_value=[])
    mock_api.playlist.update = Mock(return_value=True)
    mock_api.playlist.delete = Mock(return_value=True)
    mock_api.playlist.add_tracks = Mock(return_value=True)

    # Mock track methods
    mock_api.track = Mock()
    mock_api.track.fetch_tracks = Mock(return_value=[])

    # Mock machine_id
    mock_api.machine_id = "mock-machine-id"

    return mock_api


@pytest.fixture
def mock_plex_api_with_data(mock_plex_api: Mock, audio_files: Path) -> Mock:
    """Create a mock PlexApi with sample data."""
    # Create sample track data
    audio_file = next(audio_files.iterdir())

    track_data: PlexApiTrackResponse = {
        "Image": [
            {
                "alt": "Test Track",
                "type": "coverPoster",
                "url": "/library/metadata/1/thumb/1234567890",
            },
        ],
        "Media": [
            {
                "Part": [
                    {
                        "container": "mp3",
                        "duration": 300000,
                        "file": str(audio_file),
                        "hasThumbnail": "1",
                        "id": 1,
                        "key": "/library/parts/1/1234567890/file.mp3",
                        "size": 10000000,
                    }
                ],
                "audioChannels": 2,
                "audioCodec": "mp3",
                "bitrate": 320,
                "container": "mp3",
                "duration": 300000,
                "hasVoiceActivity": False,
                "id": 1,
            }
        ],
        "addedAt": 1234567890,
        "art": "/library/metadata/1/art/1234567890",
        "duration": 300000,
        "grandparentArt": "/library/metadata/1/art/1234567890",
        "grandparentGuid": "plex://artist/1",
        "grandparentKey": "/library/metadata/1",
        "grandparentRatingKey": "1",
        "grandparentThumb": "/library/metadata/1/thumb/1234567890",
        "grandparentTitle": "Test Artist",
        "guid": "local://1",
        "index": 1,
        "key": "/library/metadata/1",
        "lastViewedAt": 1234567890,
        "librarySectionID": 1,
        "librarySectionKey": "/library/sections/1",
        "librarySectionTitle": "Music",
        "musicAnalysisVersion": "1",
        "originalTitle": "Test Original Title",
        "parentGuid": "local://2",
        "parentIndex": 1,
        "parentKey": "/library/metadata/2",
        "parentRatingKey": "2",
        "parentThumb": "/library/metadata/2/thumb/1234567890",
        "parentTitle": "Test Album",
        "parentYear": 2024,
        "ratingKey": "1",
        "summary": "",
        "thumb": "/library/metadata/1/thumb/1234567890",
        "title": "Test Track",
        "type": "track",
    }

    playlist_data: PlexApiPlaylistResponse = {
        "ratingKey": "100",
        "title": "Test Playlist",
        "smart": False,
        "playlistType": "audio",
        "composite": "/library/metadata/100/composite/1234567890",
        "icon": "playlist",
        "duration": 1800000,
        "leafCount": 5,
        "addedAt": 1234567890,
        "updatedAt": 1234567890,
        "guid": "plex://playlist/100",
    }

    # Configure the mock with data
    mock_plex_api.track.fetch_tracks.return_value = [track_data]
    mock_plex_api.playlist.fetch_playlists.return_value = [playlist_data]
    mock_plex_api.playlist.fetch_playlist.return_value = playlist_data
    mock_plex_api.playlist.fetch_playlist_items.return_value = [track_data]

    return mock_plex_api


@pytest.fixture
def plex_library_collection(monkeypatch, mock_plex_api_with_data):
    """Fixture for a PlexLibrarySectionCollection with mocked API."""
    from plistsync.services.plex import PlexLibrarySectionCollection

    # Monkeypatch the PlexApi constructor to return our mock
    monkeypatch.setattr(
        "plistsync.services.plex.library.PlexApi",
        lambda **kwargs: mock_plex_api_with_data,
    )

    return PlexLibrarySectionCollection("Music")
