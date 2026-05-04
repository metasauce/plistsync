from typing import Any
from unittest.mock import ANY, Mock
import pytest
from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    OfflinePlaylist,
    Snapshot,
)
from plistsync.core.track import OfflineTrack

from ..core.mock_playlist import MockMultiRequestServicePlaylist, MockServicePlaylist
from ..core.mock_track import MockTrack
from ..abc.playlist import (
    TestPlaylistBase,
    TestMultiRequestServicePlaylistBase,
    TestServicePlaylistBase,
)


class TestOfflinePlaylist(TestPlaylistBase):
    def create_playlist(self, name="Name", n_tracks=0):
        return OfflinePlaylist(
            name,
            "description",
            [
                OfflineTrack(info={"title": f"Track {i}"}, global_ids={"isrc": str(i)})
                for i in range(n_tracks)
            ],
        )

    @pytest.mark.parametrize(
        ["name", "n_tracks", "expected_repr"],
        [
            ("Name", 0, "Playlist(name='Name', tracks=0)"),
            ("Name", 10, "Playlist(name='Name', tracks=10)"),
        ],
    )
    def test_repr(self, name, n_tracks, expected_repr):
        repr_str = repr(self.create_playlist(name, n_tracks))
        assert expected_repr in repr_str


class TestMockServicePlaylist(TestServicePlaylistBase):
    def create_playlist(self, name="Name", n_tracks=0):
        return MockServicePlaylist(
            name,
            "description",
            [MockTrack(global_ids={"isrc": str(i)}) for i in range(n_tracks)],
        )


class TestMockMultiRequestServicePlaylist(TestMultiRequestServicePlaylistBase):
    def create_playlist(self, name="Name", n_tracks=0):
        return MockMultiRequestServicePlaylist(
            name,
            "description",
            [MockTrack(global_ids={"isrc": str(i)}) for i in range(n_tracks)],
        )

    def test_default_remote_move_track(self, playlist: MultiRequestServicePlaylist):
        """Test that move defaults to delete and insert"""
        playlist._remote_update_metadata = Mock()
        playlist._remote_insert_track = Mock()
        playlist._remote_delete_track = Mock()
        playlist._track_key = Mock(side_effect=lambda x: x)

        before: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[3, 4])
        after: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[4, 3])
        playlist._remote_commit(before, after)
        playlist._remote_delete_track.assert_called_once_with(
            idx=1, track=4, tracks_before=ANY
        )
        playlist._remote_insert_track.assert_called_once_with(
            idx=0, track=4, tracks_before=ANY
        )

    def test_none_name_raises(self, playlist: MultiRequestServicePlaylist):
        playlist.info.pop("name")

        with pytest.raises(ValueError, match="has no name"):
            playlist.name
