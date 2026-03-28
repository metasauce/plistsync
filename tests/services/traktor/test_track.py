from pathlib import PureWindowsPath
import pytest

from plistsync.services.traktor import NMLTrack

from tests.abc.tracks import TestTrack


class TestNMLTrack(TestTrack):
    track_class = NMLTrack
    test_config = {
        "has_path": True,
    }

    @pytest.fixture(autouse=True)
    def setup(self, sample_track):
        self.track = sample_track

    def create_track(self, *args, **kwargs):
        return self.track

    def test_path(self):
        """Test the path property of the NMLTrack."""
        expected_path = PureWindowsPath(
            "F:/sync/jungle is massive/06 Ready Or Not [1074kbps].flac"
        )
        assert self.track.path == expected_path
