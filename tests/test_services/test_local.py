from pathlib import Path
from typing import Generator

import pytest
from plistsync.services.local import LocalTrack
from tests.abc import TrackTestBase
from tests.conftest import set_tags


class TestLocalTrack(TrackTestBase):
    track_class = LocalTrack
    test_config = {
        "has_path": True,
    }

    _audio_files: Path

    @pytest.fixture(autouse=True)
    def _request_audio_files(self, audio_files):
        # Needed because cant pass fixture to normal class method
        self._audio_files = audio_files

    def create_track(self) -> Generator[LocalTrack, None, None]:
        # Test all available audio files
        tracks = []
        for audio_file in self._audio_files.iterdir():
            track = LocalTrack(audio_file)
            if track is not None:
                tracks.append(track)

        if not tracks:
            pytest.skip("No tracks found")

        yield from tracks

    def test_create_no_path(self):
        with pytest.raises(FileNotFoundError):
            t = LocalTrack(Path("does/not/exist"))
        with pytest.raises(FileNotFoundError):
            t = LocalTrack("does/not/exist")

    def test_create_invalid_file(self):
        with pytest.raises(ValueError):
            LocalTrack(Path(__file__))

    def test_isrc_identifier(self):
        # Set tags for audio files
        isrc = "US-AT1-99-00001"
        set_tags(self._audio_files, {"isrc": isrc})

        # Test valid isrc identifier
        for track in self.create_track():
            assert track.identifiers.get("isrc") == isrc, "ISRC should be correct"

        # Test empty isrc identifier
        set_tags(self._audio_files, {"isrc": ""})
        for track in self.create_track():
            assert track.identifiers.get("isrc") == None, "ISRC should be None"

        # Test multiple isrc identifiers
        set_tags(self._audio_files, {"isrc": [isrc, isrc + "2"]})
        for track in self.create_track():
            assert track.identifiers.get("isrc") == isrc, "First ISRC should be used"
