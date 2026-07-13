"""Test suite for collection protocols and matching functionality."""

import pytest

from plistsync.core.collection import (
    IDLookup,
    InfoLookup,
    TrackStream,
)
from plistsync.core.ids import ISRC

from .mock_collections import (
    MockIDLookupCollection,
    MockInfoLookupCollection,
    MockTrackStreamCollection,
    MockFullCapabilityCollection,
)
from .mock_track import MockTrack


class TestProtocolRuntimeChecking:
    """Test runtime protocol checking functionality."""

    @pytest.mark.parametrize(
        "collection_type, check",
        [
            (MockIDLookupCollection, IDLookup),
            (MockInfoLookupCollection, InfoLookup),
            (MockTrackStreamCollection, TrackStream),
            (
                MockFullCapabilityCollection,
                (IDLookup, InfoLookup, TrackStream),
            ),
        ],
    )
    def test_runtime_checkable(self, collection_type, check):
        """Test runtime checking for protocols."""
        col = collection_type([])
        for ins in [IDLookup, InfoLookup, TrackStream]:
            if (isinstance(check, tuple) and (ins in check)) or check == ins:
                assert isinstance(col, ins)
            else:
                assert not isinstance(col, ins)


class TestMatchingInCollections:
    """Test matching functionality in collections."""

    def test_find_by_ids(self):
        """Test find_by_ids for exact ID matches."""
        col = MockFullCapabilityCollection(
            [
                MockTrack("1", ids={ISRC("A")}),
                MockTrack("2", ids={ISRC("B")}),
            ]
        )
        found = col.find_by_ids({ISRC("A")})
        assert found is not None and found.title == "1"

        found_many = col.find_many_by_ids(
            [
                {ISRC("A")},
                {ISRC("B")},
                {ISRC("C")},
            ]
        )
        tracks = list(filter(None, found_many))
        assert len(tracks) == 2

    @pytest.mark.parametrize(
        "skip_after_local, skip_after_fuzzy",
        [
            (False, False),
            (True, False),
            (False, True),
        ],
    )
    @pytest.mark.parametrize(
        "collection_type",
        [
            MockIDLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_id_lookup(self, skip_after_local, skip_after_fuzzy, collection_type):
        """Test ID-based matching in the collection."""
        track = MockTrack(
            title="Test Track",
            ids={ISRC("id")},
        )
        col = collection_type([track])

        found = col.match(
            MockTrack(
                title="FOOO",
                ids={ISRC("id")},
            ),
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        ).best_match
        assert found is not None
        assert found == track

    @pytest.mark.parametrize(
        "skip_after_local, skip_after_fuzzy",
        [
            (False, False),
            (True, False),
            (False, True),
        ],
    )
    @pytest.mark.parametrize(
        "collection_type",
        [
            MockIDLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_id_lookup_no_match(
        self, skip_after_local, skip_after_fuzzy, collection_type
    ):
        """Test ID-based matching when no ID matches."""
        col = collection_type([MockTrack("1", ids={ISRC("A")})])

        found = col.match(
            MockTrack(
                title="Track 2",
                ids={ISRC("B")},
            ),
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        ).best_match
        assert found is None

    @pytest.mark.parametrize(
        "skip_after_local, skip_after_fuzzy",
        [
            (False, False),
            (True, False),
            (False, True),
        ],
    )
    @pytest.mark.parametrize(
        "collection_type",
        [
            MockInfoLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_info(self, skip_after_local, skip_after_fuzzy, collection_type):
        """Test info matching in the collection."""
        track = MockTrack(title="Unique Title")
        col = collection_type([track])

        found = col.match(
            MockTrack(title="Unique Title"),
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        ).best_match
        assert found is not None
        assert found == track

    def test_match_cutoff(self):
        """Test that cutoff works in matching."""
        track = MockTrack(
            title="Test Track",
            ids={ISRC("id")},
        )
        col = MockTrackStreamCollection([track])

        matches = col.match(
            MockTrack(title="Test"),
            cutoff=1.0,
        )
        assert matches.best_match is None
