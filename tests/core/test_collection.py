"""Test suite for collection protocols and matching functionality."""

import pytest

from plistsync.core.collection import (
    GlobalLookup,
    LocalLookup,
    InfoLookup,
    TrackStream,
)

from .mock_collections import (
    MockGlobalLookupCollection,
    MockLocalLookupCollection,
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
            (MockGlobalLookupCollection, GlobalLookup),
            (MockLocalLookupCollection, LocalLookup),
            (MockInfoLookupCollection, InfoLookup),
            (MockTrackStreamCollection, TrackStream),
            (
                MockFullCapabilityCollection,
                (GlobalLookup, LocalLookup, InfoLookup, TrackStream),
            ),
        ],
    )
    def test_runtime_checkable_global_lookup(self, collection_type, check):
        """Test runtime checking for GlobalLookup protocol."""
        col = collection_type([])
        for ins in [GlobalLookup, LocalLookup, InfoLookup, TrackStream]:
            if (isinstance(check, tuple) and (ins in check)) or check == ins:
                assert isinstance(col, ins)
            else:
                assert not isinstance(col, ins)


class TestMatchingInCollections:
    """Test matching functionality in collections."""

    def test_find_by_global_id(self):
        """Test that NotImplementedError is raised for unimplemented method."""

        col = MockFullCapabilityCollection(
            [
                MockTrack("1", global_ids={"isrc": "A"}),
                MockTrack("2", global_ids={"isrc": "B"}),
            ]
        )

        found = col.find_by_global_ids({"isrc": "A"})
        assert found is not None and found.title == "1"

        found_many = col.find_many_by_global_ids(
            [
                {"isrc": "A"},
                {"isrc": "B"},
                {"isrc": "C"},
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
            MockGlobalLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_global(self, skip_after_local, skip_after_fuzzy, collection_type):
        """Test global matching in the collection.
        E.g. by ISRC.
        """
        track = MockTrack(
            title="Test Track",
            global_ids={"isrc": "id"},
        )
        col = collection_type([track])

        found = col.match(
            MockTrack(
                title="FOOO",
                global_ids={"isrc": "id"},
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
            MockLocalLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_local(self, skip_after_local, skip_after_fuzzy, collection_type):
        """Test local matching in the collection.
        E.g. by Plex local ID.
        """
        track = MockTrack(
            title="Test Track",
            local_ids={"plex_id": "local-id"},
        )
        col = collection_type([track])

        found = col.match(
            MockTrack(
                local_ids={"plex_id": "local-id"},
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
            MockInfoLookupCollection,
            MockTrackStreamCollection,
            MockFullCapabilityCollection,
        ],
    )
    def test_match_info(self, skip_after_local, skip_after_fuzzy, collection_type):
        """Test info matching in the collection.
        E.g. by title.
        """
        track = MockTrack(
            title="Unique Title",
        )
        col = collection_type([track])

        found = col.match(
            MockTrack(
                title="Unique Title",
                global_ids={"isrc": "non-matching-id"},
                local_ids={"plex_id": "non-matching-local-id"},
            ),
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        ).best_match
        assert found is not None
        assert found == track

    def test_match_cutoff(self):
        """Test that cutoff works in matching."""
        track = MockTrack(
            title="Test Track",
            global_ids={"isrc": "id"},
        )
        col = MockTrackStreamCollection([track])

        # Matching with high cutoff should yield no results
        matches = col.match(
            MockTrack(
                title="Test",
            ),
            cutoff=1.0,
        )
        assert matches.best_match is None
