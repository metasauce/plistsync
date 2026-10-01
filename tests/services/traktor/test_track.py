from pathlib import PurePosixPath, PureWindowsPath
from typing import ClassVar
import pytest

from plistsync.services.traktor import NMLTrack
from plistsync.services.traktor.path import NMLPath
from plistsync.services.traktor.track import NMLPlaylistTrack

from tests.abc.tracks import TestTrack
from tests.core.mock_track import MockTrack


class TestNMLTrack(TestTrack):
    track_class = NMLTrack
    test_config: ClassVar[dict[str, bool]] = {
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
    def test_info_is_empty_without_library(self):
        playlist_track = NMLPlaylistTrack.from_traktor_path(
            NMLPath("D:/:Music/:missing.flac")
        )

        assert playlist_track.info == {}

    def test_info_uses_linked_library(self, collection):
        traktor_path = NMLPath(
            "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/"
            ":04 Dragger [1028kbps].flac"
        )
        playlist_track = NMLPlaylistTrack.from_traktor_path(
            traktor_path, library=collection
        )

        assert playlist_track.info.get("title") == "Dragger"

    def test_info_is_empty_when_library_has_no_track(self, collection):
        playlist_track = NMLPlaylistTrack.from_traktor_path(
            NMLPath("D:/:Music/:missing.flac"), library=collection
        )

        assert playlist_track.info == {}

    def test_from_track_preserves_library_link(self, collection, sample_track):
        playlist_track = NMLPlaylistTrack.from_track(sample_track, library=collection)

        assert playlist_track.library is collection

    def test_from_track_requires_path(self):
        with pytest.raises(ValueError, match="does not have a path"):
            NMLPlaylistTrack.from_track(MockTrack())

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
