from pathlib import PurePosixPath, PureWindowsPath
import pytest

from plistsync.services.traktor import NMLTrack
from plistsync.services.traktor.path import NMLPath
from plistsync.services.traktor.track import NMLPlaylistTrack

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


class TestNMLPlaylistTrackToNMLTrack:
    def test_to_nml_track_returns_existing(self, collection):
        traktor_path = NMLPath.from_path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        playlist_track = NMLPlaylistTrack.from_traktor_path(traktor_path)

        converted = playlist_track.to_nml_track(collection)

        assert converted is not None
        assert isinstance(converted, NMLTrack)
        assert converted.traktor_path == traktor_path

    def test_to_nml_track_inserts_when_missing_by_default(self, collection):
        before_entries = int(collection._collection.get("ENTRIES", "0"))

        playlist_track = NMLPlaylistTrack.from_path(
            PurePosixPath("/Volumes/Macintosh HD/foo/bar.flac")
        )
        converted = playlist_track.to_nml_track(collection)

        assert converted is not None
        assert isinstance(converted, NMLTrack)
        assert converted.traktor_path == playlist_track.traktor_path

        after_entries = int(collection._collection.get("ENTRIES", "0"))
        assert after_entries == before_entries + 1

    def test_to_nml_track_returns_none_when_missing_and_insert_disabled(
        self, collection
    ):
        before_entries = int(collection._collection.get("ENTRIES", "0"))

        playlist_track = NMLPlaylistTrack.from_path(
            PurePosixPath("/Volumes/Macintosh HD/foo/baz.flac")
        )
        converted = playlist_track.to_nml_track(collection, insert_if_not_found=False)

        assert converted is None

        after_entries = int(collection._collection.get("ENTRIES", "0"))
        assert after_entries == before_entries
