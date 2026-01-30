from collections.abc import Generator

from pathlib import PureWindowsPath
import pytest

from plistsync.core import Track
from plistsync.services.traktor import NMLTrack

from tests.abc import TrackTestBase


class TestNMLTrack(TrackTestBase):
    track_class = NMLTrack
    test_config = {
        "has_path": True,
    }

    @pytest.fixture(autouse=True)
    def setup(self, sample_track):
        self.track = sample_track

    def create_track(self, *args, **kwargs) -> Generator[Track, None, None]:
        yield self.track

    def test_path(self):
        """Test the path property of the NMLTrack."""
        expected_path = PureWindowsPath(
            "F:/sync/jungle is massive/06 Ready Or Not [1074kbps].flac"
        )
        assert self.track.path == expected_path
