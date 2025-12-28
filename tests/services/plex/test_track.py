from pathlib import Path
from typing import ClassVar, Iterable

import pytest
from plistsync.services.local.track import LocalTrack
from plistsync.services.plex import PlexTrack
from plistsync.services.plex.api_types import PlexApiTrackResponse
from tests.abc import TrackTestBase
from tests.conftest import set_tags


class TestPlexTrack(TrackTestBase):
    track_class = PlexTrack
    test_config = {
        "has_path": True,
    }

    _audio_files: ClassVar[Path]

    @classmethod
    @pytest.fixture(autouse=True, scope="class")
    def _request_audio_files(cls, audio_files):
        # Needed because cant pass fixture to normal class method
        cls._audio_files = audio_files
        set_tags(cls._audio_files, {"isrc": "US-AT1-99-00001"})

    @classmethod
    def create_track(cls, *args, **kwargs) -> Iterable[PlexTrack]:
        for audio_file in cls._audio_files.iterdir():
            # TODO: dynamically create plex DATA from audio file, i.e. fix inconsistencies
            yield PlexTrack(
                PlexApiTrackResponse(
                    **{
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
                                        "file": str(audio_file),
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
            )

    def test_plex_id(self):
        # Test valid plex identifier
        for track in self.create_track():
            assert track.plex_id == "58516", "Plex ID should be correct"

    def test_info(self):
        # Test valid info
        for track in self.create_track():
            info = track.info
            assert isinstance(info, dict), "Info should be a dict"
            assert (
                info.get("title") == "We Are Your Crazy Friends (Baramuda Bootleg Mix)"
            ), "Title should be correct"
            assert info.get("artists") == ["Sharam Vs Justice"], (
                "Artist should be correct"
            )
            assert info.get("albums") == ["Tech And Minimal Collection Volume 20"], (
                "Album should be correct"
            )

    def test_local_ids(self):
        # Test valid local_ids
        for track in self.create_track():
            lids = track.local_ids
            assert isinstance(lids, dict), "local_ids should be a dict"

            # we only use local tracks in the test (not the tidal ones)
            assert "file_path" in lids, "local_ids should contain file_path"
            assert lids["file_path"] == track.path, "file_path should be correct"

            assert "plex_id" in lids, "local_ids should contain plex_id"
            assert lids["plex_id"] == track.plex_id, "plex_id should be correct"

    def test_global_ids_via_local_track(self):
        # plex has very little real metadata in its track-level api respones,
        # so checking that we can retrieve metadata from the actual file
        # is important.
        for track in self.create_track():
            assert track.path is not None, "Track should have a path"
            local_track = LocalTrack(track.path)
            assert local_track.global_ids.get("isrc") == "US-AT1-99-00001", (
                "ISRC should be correct"
            )
