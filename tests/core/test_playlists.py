from collections.abc import Callable
import pytest

from plistsync.core.playlist import Snapshot
from plistsync.core.track import GlobalTrackIDs
from tests.abc import MultiRequestPlaylistCollectionTestBase, PlaylistCollectionTestBase
from .mock_track import MockTrack
from .mock_playlist import MockPlaylist, MockPlaylistMultiRequest


@pytest.fixture
def make_playlist() -> Callable[..., MockPlaylist]:
    def _make(
        *,
        name: str = "foo",
        ids: list[GlobalTrackIDs] | None = None,
        remote_associated: bool = True,
    ) -> MockPlaylist:
        tracks = [MockTrack(global_ids=gid) for gid in (ids or [])]
        return MockPlaylist(name, tracks, remote_associated=remote_associated)

    return _make


@pytest.fixture
def make_multi_request_playlist() -> Callable[..., MockPlaylist]:
    def _make(
        *,
        name: str = "foo",
        ids: list[GlobalTrackIDs] | None = None,
        remote_associated: bool = True,
    ) -> MockPlaylist:
        tracks = [MockTrack(global_ids=gid) for gid in (ids or [])]
        return MockPlaylistMultiRequest(
            name, tracks, remote_associated=remote_associated
        )

    return _make


def eq_isrc(track: MockTrack) -> str:
    if irsc := track.global_ids.get("isrc"):
        return irsc

    raise ValueError(f"Track {track.title} has no ISRC.")


class TestPlaylistChanges:
    @pytest.fixture
    def sample_tracks(self) -> list[MockTrack]:
        return [
            MockTrack(
                title="Track 1",
                artists=["Artist A"],
                global_ids={"isrc": "1"},
            ),
            MockTrack(
                title="Track 2",
                artists=["Artist B"],
                global_ids={"isrc": "2"},
            ),
            MockTrack(
                title="Track 3",
                artists=["Artist C"],
                global_ids={"isrc": "3"},
            ),
        ]

    @pytest.fixture
    def sample_snapshot(self, sample_tracks: list[MockTrack]) -> Snapshot:
        """Return a sample snapshot for testing."""
        return Snapshot(
            name="Test Playlist",
            description="Original description",
            tracks=sample_tracks,
        )


class TestPlaylistCollection:
    @pytest.mark.parametrize(
        "ids_before, ids_after, expected_log",
        [
            # No change (different objects, same ISRC)
            (
                [{"isrc": "1"}],
                [{"isrc": "1"}],
                [],
            ),
            # Addition
            (
                [{"isrc": "4"}],
                [{"isrc": "1"}, {"isrc": "4"}],
                [("insert", 0, {"isrc": "1"})],
            ),
            # Deletion
            (
                [{"isrc": "1"}, {"isrc": "4"}],
                [{"isrc": "4"}],
                [("delete", 0, {"isrc": "1"})],
            ),
            # Move
            (
                [{"isrc": "1"}, {"isrc": "4"}],
                [{"isrc": "4"}, {"isrc": "1"}],
                [("delete", 1, {"isrc": "4"}), ("insert", 0, {"isrc": "4"})],
            ),
        ],
    )
    def test_edit_tracks(
        self,
        make_multi_request_playlist,
        ids_before,
        ids_after,
        expected_log,
    ) -> None:
        pl = make_multi_request_playlist(ids=ids_before)
        with pl.remote_edit():
            pl._tracks = [MockTrack(global_ids=ta) for ta in ids_after]

        assert [t.global_ids for t in pl._tracks] == ids_after  # Local state preserved
        # Check log
        assert [(op, idx, t.global_ids) for (op, idx, t) in pl.log] == expected_log

    def test_edit_metadata(self, make_multi_request_playlist) -> None:
        pl = make_multi_request_playlist()

        with pl.remote_edit():
            pl.name = "bar"

        assert pl.name == "bar"

    def test_edit_rollback(self, make_multi_request_playlist) -> None:
        pl = make_multi_request_playlist()

        with pytest.raises(ValueError):
            with pl.remote_edit():
                pl.name = "bar"
                raise ValueError()

        assert pl.name == "foo"  # rollback

    @pytest.mark.parametrize(
        ["name", "n_tracks", "expected_repr"],
        [
            ("Name", 0, "Playlist(name='Name', tracks=0)"),
            ("Name", 10, "Playlist(name='Name', tracks=10)"),
        ],
    )
    def test_repr(self, make_playlist, name, n_tracks, expected_repr):
        repr_str = repr(
            make_playlist(
                name=name,
                ids=[i for i in range(n_tracks)],
            )
        )
        assert expected_repr in repr_str


class TestPlaylistRemoteLifecycle:
    def test_create(self, make_playlist) -> None:
        pl = make_playlist(remote_associated=False)

        pl.remote_create()

        assert pl.remote_associated is True
        assert ("remote_create",) in pl.log

    def test_create_raises_if_already_associated(self, make_playlist) -> None:
        pl = make_playlist(remote_associated=True)

        with pytest.raises(ValueError, match="already associated"):
            pl.remote_create()

    def test_delete(self, make_playlist) -> None:
        pl = make_playlist(remote_associated=True)

        pl.remote_delete()

        assert pl.remote_associated is False
        assert ("remote_delete",) in pl.log

    def test_delete_raises_if_not_associated(self, make_playlist) -> None:
        pl = make_playlist(remote_associated=False)

        with pytest.raises(ValueError, match="associated"):
            pl.remote_delete()


class TestMockPlaylistCollection(PlaylistCollectionTestBase):
    def create_playlist(self, *, remote_associated: bool = True) -> MockPlaylist:
        return MockPlaylist(
            "pl",
            None,
            remote_associated=remote_associated,
        )

    def create_track(self, *, isrc: str) -> MockTrack:
        return MockTrack(global_ids={"isrc": isrc})

    def test_none_name_raises(self):
        pl = self.create_playlist()
        pl.info.pop("name")

        with pytest.raises(ValueError, match="has no name"):
            pl.name


class TestMockPlaylistIncrementalCollection(MultiRequestPlaylistCollectionTestBase):
    def create_playlist(
        self, *, remote_associated: bool = True
    ) -> MockPlaylistMultiRequest:
        return MockPlaylistMultiRequest(
            "pl",
            None,
            remote_associated=remote_associated,
        )
