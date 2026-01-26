import pytest

from plistsync.core.playlist import Snapshot
from .mock_track import MockTrack
from .mock_playlist import MockPlaylist


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
    def test_edit_tracks(self, ids_before, ids_after, expected_log):
        """Test track_operations() reflects changes in track lists."""
        pl = MockPlaylist("foo", [MockTrack(global_ids=tb) for tb in ids_before])
        with pl.edit():
            pl._tracks = [MockTrack(global_ids=ta) for ta in ids_after]

        assert [t.global_ids for t in pl._tracks] == ids_after  # Local state preserved
        # Check log
        assert (
            list(map(lambda x: (x[0], x[1], x[2].global_ids), pl.log)) == expected_log
        )  # Log reflects changes

    def test_edit_meta(self):
        pl = MockPlaylist("foo", [])
        with pl.edit():
            pl.name = "bar"

        assert pl.name == "bar"

    def test_edit_rollbnack(self):
        pl = MockPlaylist("foo", [])
        try:
            with pl.edit():
                pl.name = "bar"
                raise ValueError()
        except ValueError:
            pass
        assert pl.name == "foo"  # Rollback
