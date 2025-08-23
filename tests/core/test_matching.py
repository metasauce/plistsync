from math import e
import pytest

from plistsync.core.collection import Matches, TrackInfo
from plistsync.core.matching import distance, fuzzy_match

from .mock_track import MockTrack


class TestMatching:
    """Test matching functions and classes."""

    @pytest.fixture
    def foo(self) -> TrackInfo:
        """Create test track info."""
        return TrackInfo(
            **{
                "title": "Test Song",
                "artists": ["Artist One", "Artist Two"],
                "albums": ["Test Album"],
            }
        )

    @pytest.fixture
    def foo_similar(self) -> TrackInfo:
        """Create similar track info."""
        return TrackInfo(
            **{
                "title": "Test Song",
                "artists": ["Artist One", "Artist Two"],
                "albums": ["Test Album Deluxe"],
            }
        )

    @pytest.fixture
    def bar(self) -> TrackInfo:
        """Create different track info."""
        return TrackInfo(
            **{
                "title": "Different",
                "artists": ["Other"],
                "albums": ["Different"],
            }
        )

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("hello", "hello", 1.0),
            ("hello", "hell0", (0.5, 1.0)),  # Similar but not identical
            ("hello", "world", (0.0, 0.5)),
            (["a", "b"], ["a", "b"], 1.0),  # Identical lists
            (["a", "b"], ["b", "a"], 1.0),  # Similar lists
            (["a", "b"], ["x", "y"], 0.0),  # Different lists
            (["a", "b"], ["a"], 0.5),  # One list is a subset of the other
            ([], [], None),  # Identical empty lists
            ("", "a", None),
        ],
    )
    def test_distance(self, a, b, expected):
        result = distance(a, b)
        if isinstance(expected, tuple):
            assert expected[0] <= result < expected[1]
        else:
            assert result == expected

        # Should be invariate to order
        result_reverse = distance(b, a)
        assert result_reverse == result, "Distance should be symmetric"

    def test_distance_same_obj(self):
        a = ["foo", "bar"]
        assert distance(a, a) == 1.0, "Distance should be 1.0 for identical objects"

    def test_distance_invalid_obj(self):
        assert (
            distance(
                (object),  # type: ignore
                ["a"],
            )
            is None
        )

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("foo", "foo", 1.0),
            ("foo", "foo_similar", (0.5, 1.0)),  # Similar but not identical
            ("foo", "bar", (0.0, 0.5)),
            ("empty", "foo", 0.0),
        ],
    )
    def test_fuzzy(self, foo, foo_similar, bar, a, b, expected):
        """fuzzy_match uses distance, on all properties of the track info."""
        track_map = {
            "foo": foo,
            "foo_similar": foo_similar,
            "bar": bar,
            "empty": TrackInfo(),  # type:ignore
        }
        a_track = track_map[a]
        b_track = track_map[b]

        similarity = fuzzy_match(a_track, b_track)
        if isinstance(expected, tuple):
            assert expected[0] <= similarity < expected[1]
        else:
            assert similarity == expected

        similarity_reverse = fuzzy_match(b_track, a_track)
        assert similarity_reverse == similarity, "Fuzzy match should be symmetric"


class TestMatches:
    """Test the Matches dataclass."""

    @pytest.fixture
    def mock_track(self) -> MockTrack:
        """Create a mock track."""
        return MockTrack(title="Test Track")

    @pytest.fixture
    def mock_matches(self, mock_track) -> Matches:
        """Create a Matches instance for testing."""
        found_tracks = [
            MockTrack(title="Match 1"),
            MockTrack(title="Match 2"),
        ]
        similarities = [0.9, 0.7]
        return Matches(
            truth=mock_track, found=found_tracks, found_similarities=similarities
        )

    def test_matches_initialization(self, mock_track, mock_matches):
        """Test Matches initialization."""
        assert mock_matches.truth == mock_track
        assert len(mock_matches.found) == 2
        assert len(mock_matches.found_similarities) == 2

    def test_similarity_property(self, mock_matches):
        """Test similarity property."""
        assert mock_matches.similarity == 0.9  # Highest similarity

    def test_similarity_no_matches(self, mock_track):
        """Test similarity property with no matches."""
        matches = Matches(truth=mock_track)
        assert matches.similarity == 0.0

    def test_iteration(self, mock_matches):
        """Test iteration over matches."""
        items = list(mock_matches)
        assert len(items) == 2
        for track, similarity in items:
            assert isinstance(track, MockTrack)
            assert isinstance(similarity, float)
