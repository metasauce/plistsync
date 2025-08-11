from pathlib import Path
from typing import Generator

import pytest
from plistsync.services.plex import PlexTrack
from tests.abc import TrackTestBase
from tests.conftest import set_tags


class TestPlexTrack(TrackTestBase):
    track_class = PlexTrack
    test_config = {
        "has_path": True,
    }

    _audio_files: Path

    @pytest.fixture(autouse=True)
    def _request_audio_files(self, audio_files):
        # Needed because cant pass fixture to normal class method
        self._audio_files = audio_files
        set_tags(self._audio_files, {"isrc": "US-AT1-99-00001"})

    def create_track(self, *args, **kwargs) -> Generator[PlexTrack, None, None]:
        for audio_file in self._audio_files.iterdir():
            # TODO: dynamically create plex DATA from audio file, i.e. fix inconsistencies
            yield PlexTrack(
                {
                    "Image": [
                        {
                            "alt": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
                            "type": "coverPoster",
                            "url": "/library/metadata/58473/thumb/1713284425",
                        },
                        {
                            "alt": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
                            "type": "background",
                            "url": "/library/metadata/55906/art/1713284398",
                        },
                    ],
                    "Media": [
                        {
                            "Part": [
                                {
                                    "container": "mp3",
                                    "duration": 629032,
                                    "file": audio_file,
                                    "hasThumbnail": "1",
                                    "id": 112271,
                                    "key": "/library/parts/112271/1716780133/file.mp3",
                                    "size": 26170369,
                                }
                            ],
                            "audioChannels": 2,
                            "audioCodec": "mp3",
                            "bitrate": 320,
                            "container": "mp3",
                            "duration": 629032,
                            "hasVoiceActivity": False,
                            "id": 58357,
                        }
                    ],
                    "addedAt": 1713284375,
                    "art": "/library/metadata/55906/art/1713284398",
                    "duration": 629032,
                    "grandparentArt": "/library/metadata/55906/art/1713284398",
                    "grandparentGuid": "plex://artist/5d07bbfc403c6402904a5ec9",
                    "grandparentKey": "/library/metadata/55906",
                    "grandparentRatingKey": "55906",
                    "grandparentThumb": "/library/metadata/55906/thumb/1713284398",
                    "grandparentTitle": "Various Artists",
                    "guid": "local://58516",
                    "index": 43,
                    "key": "/library/metadata/58516",
                    "lastViewedAt": 1725619057,
                    "librarySectionID": 5,
                    "librarySectionKey": "/library/sections/5",
                    "librarySectionTitle": "Music",
                    "musicAnalysisVersion": "1",
                    "originalTitle": "Sharam Vs Justice",
                    "parentGuid": "local://58473",
                    "parentIndex": 1,
                    "parentKey": "/library/metadata/58473",
                    "parentRatingKey": "58473",
                    "parentThumb": "/library/metadata/58473/thumb/1713284425",
                    "parentTitle": "Tech And Minimal Collection Volume 20",
                    "parentYear": 2011,
                    "ratingKey": "58516",
                    "summary": "",
                    "thumb": "/library/metadata/58473/thumb/1713284425",
                    "title": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
                    "type": "track",
                }
            )

    def test_plex_identifiers(self):
        # Test valid plex identifier
        for track in self.create_track():
            assert track.plex_id == "58516", "Plex ID should be correct"
