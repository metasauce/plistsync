from typing import Any
from unittest.mock import ANY, Mock
import pytest
from plistsync.core.playlist import MultiRequestPlaylistCollection, Snapshot
from plistsync.core.track import GlobalTrackIDs

from ..core.mock_playlist import MockPlaylist, MockPlaylistMultiRequest
from ..core.mock_track import MockTrack
from ..abc.playlist import TestPlaylistCollection, TestMultiRequestPlaylistCollection


def make_mock_playlist(
    *,
    name: str = "foo",
    ids: list[GlobalTrackIDs] | None = None,
    remote_associated: bool = True,
) -> MockPlaylist:
    if ids is not None:
        tracks = [MockTrack(global_ids=gid) for gid in ids]
    else:
        tracks = None
    return MockPlaylist(name, tracks, remote_associated=remote_associated)


class TestMockPlaylist(TestPlaylistCollection):
    Playlist = MockPlaylist

    def create_playlist(self):
        return make_mock_playlist(name="A playlist", remote_associated=False)

    @pytest.mark.parametrize(
        ["name", "n_tracks", "expected_repr"],
        [
            ("Name", 0, "Playlist(name='Name', tracks=0)"),
            ("Name", 10, "Playlist(name='Name', tracks=10)"),
        ],
    )
    def test_repr(self, name, n_tracks, expected_repr):
        repr_str = repr(
            make_mock_playlist(
                name=name,
                ids=[{"isrc": str(i)} for i in range(n_tracks)],
            )
        )
        assert expected_repr in repr_str


def make_mock_playlist_multi(
    *,
    name: str = "foo",
    ids: list[GlobalTrackIDs] | None = None,
    remote_associated: bool = True,
) -> MockPlaylistMultiRequest:
    if ids is not None:
        tracks = [MockTrack(global_ids=gid) for gid in ids]
    else:
        tracks = None
    return MockPlaylistMultiRequest(name, tracks, remote_associated=remote_associated)


class TestMockMockPlaylistMultiRequest(TestMultiRequestPlaylistCollection):
    Playlist = MockPlaylistMultiRequest

    def create_playlist(self):
        return make_mock_playlist_multi(name="A playlist", remote_associated=False)

    def test_default_remote_move_track(self, playlist: MultiRequestPlaylistCollection):
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

    def test_none_name_raises(self, playlist: MultiRequestPlaylistCollection):
        playlist.info.pop("name")

        with pytest.raises(ValueError, match="has no name"):
            playlist.name
