import pytest

from plistsync.core.playlist import PlaylistChanges, Snapshot
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
        return {
            "name": "Test Playlist",
            "description": "Original description",
            "tracks": sample_tracks,
        }

    def test_no_change(self, sample_snapshot: Snapshot):
        changes = PlaylistChanges(sample_snapshot, sample_snapshot)
        assert changes.new_name() is None
        assert changes.new_description() is None

    def test_name_description_change(self, sample_snapshot: Snapshot):
        modified_snapshot = sample_snapshot.copy()
        modified_snapshot["name"] = "New Playlist Name"
        modified_snapshot["description"] = "New description"

        changes = PlaylistChanges(sample_snapshot, modified_snapshot)
        assert changes.new_name() == "New Playlist Name"
        assert changes.new_description() == "New description"

    @pytest.mark.parametrize(
        "tracks_before, tracks_after, expected_ops",
        [
            (
                # Same tracks but different objects
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                ],
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                ],
                [
                    ("equal", 0, 1, 0, 1),
                ],
            ),
            (
                # Addition
                [
                    MockTrack(
                        title="Track 4", artists=["Artist D"], global_ids={"isrc": "4"}
                    ),
                ],
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                    MockTrack(
                        title="Track 4", artists=["Artist D"], global_ids={"isrc": "4"}
                    ),
                ],
                [
                    ("insert", 0, 0, 0, 1),
                    ("equal", 0, 1, 1, 2),
                ],
            ),
            (
                # Removal
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                    MockTrack(
                        title="Track 4", artists=["Artist D"], global_ids={"isrc": "4"}
                    ),
                ],
                [
                    MockTrack(
                        title="Track 4", artists=["Artist D"], global_ids={"isrc": "4"}
                    ),
                ],
                [
                    ("delete", 0, 1, 0, 0),
                    ("equal", 1, 2, 0, 1),
                ],
            ),
            (
                # Complex reordering
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                    MockTrack(
                        title="Track 2", artists=["Artist B"], global_ids={"isrc": "2"}
                    ),
                    MockTrack(
                        title="Track 3", artists=["Artist C"], global_ids={"isrc": "3"}
                    ),
                ],
                [
                    MockTrack(
                        title="Track 3", artists=["Artist C"], global_ids={"isrc": "3"}
                    ),
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                    MockTrack(
                        title="Track 2", artists=["Artist B"], global_ids={"isrc": "2"}
                    ),
                ],
                [
                    ("insert", 0, 0, 0, 1),
                    ("equal", 0, 2, 1, 3),
                    ("delete", 2, 3, 3, 3),
                ],
            ),
            (
                # Replacement
                [
                    MockTrack(
                        title="Track 1", artists=["Artist A"], global_ids={"isrc": "1"}
                    ),
                ],
                [
                    MockTrack(
                        title="Track 2", artists=["Artist B"], global_ids={"isrc": "2"}
                    ),
                ],
                [
                    ("replace", 0, 1, 0, 1),
                ],
            ),
        ],
    )
    def test_track_operations(self, tracks_before, tracks_after, expected_ops):
        """Test track_operations() reflects changes in track lists."""
        changes = PlaylistChanges(
            {"tracks": tracks_before, "name": "A", "description": None},
            {"tracks": tracks_after, "name": "A", "description": None},
        )
        assert (
            changes.track_operations(lambda track: track.global_ids["isrc"])
            == expected_ops
        )


class TestPlaylistCollection:
    def test_mock_playlist_collection_basic_functionality(self):
        """Test basic functionality of MockPlaylistCollection."""
        tracks = [MockTrack("1"), MockTrack("2")]
        playlist = MockPlaylist("Test Playlist", tracks)

        assert playlist.name == "Test Playlist"
        assert len(playlist) == 2
        assert list(playlist) == tracks
        assert playlist.description is None

        # Test context manager
        with playlist.edit() as pl:
            assert list(playlist) == tracks
        assert playlist[0] == tracks[0]
