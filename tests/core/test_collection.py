"""Test suite for collection protocols and matching functionality."""

from __future__ import annotations

import pytest

from pathlib import PurePath
from typing import ClassVar, NamedTuple, TYPE_CHECKING

from plistsync.core.collection import (
    IDLookup,
    InfoLookup,
    TrackStream,
)
from plistsync.core.ids import FilePath, ISRC

from .mock_collections import (
    MockFullCapabilityCollection,
    MockIDLookupCollection,
    MockInfoLookupCollection,
    MockStreamInfoCollection,
    MockTrackStreamCollection,
)
from .mock_track import MockTrack

if TYPE_CHECKING:
    from plistsync.core.matching import Matches


_ALL_COLLECTION_TYPES: tuple[type, ...] = (
    MockIDLookupCollection,
    MockInfoLookupCollection,
    MockTrackStreamCollection,
    MockFullCapabilityCollection,
)

_COLLECTION_TYPES_WITH_INFO: tuple[type, ...] = (
    MockInfoLookupCollection,
    MockTrackStreamCollection,
    MockFullCapabilityCollection,
)

_COLLECTION_TYPES_WITH_ID_LOOKUP: tuple[type, ...] = (
    MockIDLookupCollection,
    MockFullCapabilityCollection,
)


class _MatchManyScenario(NamedTuple):
    """A test scenario for verifying match_many ≡ [match(t) for t in tracks]."""

    name: str
    collection_tracks: list[MockTrack]
    query_tracks: list[MockTrack]
    applicable_types: tuple[type, ...] = _ALL_COLLECTION_TYPES


_MATCH_MANY_SCENARIOS: tuple[_MatchManyScenario, ...] = (
    _MatchManyScenario(
        "global_ids",
        collection_tracks=[
            MockTrack("Alpha", ids={ISRC("ISRC001")}),
            MockTrack("Beta", ids={ISRC("ISRC002")}),
            MockTrack("Gamma", ids={ISRC("ISRC003")}),
        ],
        query_tracks=[
            MockTrack("Alpha Query", ids={ISRC("ISRC001")}),
            MockTrack("Gamma Query", ids={ISRC("ISRC003")}),
            MockTrack("Delta Query", ids={ISRC("ISRC999")}),
        ],
    ),
    _MatchManyScenario(
        "info",
        collection_tracks=[
            MockTrack("Song One"),
            MockTrack("Song Two"),
            MockTrack("Song Three"),
        ],
        query_tracks=[
            MockTrack("Song One"),
            MockTrack("Song Three"),
            MockTrack("Unknown Song"),
        ],
        applicable_types=_COLLECTION_TYPES_WITH_INFO,
    ),
    _MatchManyScenario(
        "mixed_ids_and_info",
        collection_tracks=[
            MockTrack("Title A", ids={ISRC("ISRC_A")}),
            MockTrack("Title B", ids={ISRC("ISRC_B")}),
            MockTrack("Title C"),
        ],
        query_tracks=[
            MockTrack("Query A", ids={ISRC("ISRC_A")}),  # global ID
            MockTrack("Title C"),  # info (exact title)
            MockTrack("Title B", ids={ISRC("ISRC_B")}),  # global ID
            MockTrack("No Match"),
        ],
    ),
    _MatchManyScenario(
        "local_ids",
        collection_tracks=[
            MockTrack("Local A", ids={FilePath(PurePath("/music/track_a.flac"))}),
            MockTrack("Local B", ids={FilePath(PurePath("/music/track_b.flac"))}),
        ],
        query_tracks=[
            MockTrack("Query A", ids={FilePath(PurePath("/music/track_a.flac"))}),
            MockTrack("Query B", ids={FilePath(PurePath("/music/track_b.flac"))}),
            MockTrack("Query C", ids={FilePath(PurePath("/music/unknown.flac"))}),
        ],
        applicable_types=_COLLECTION_TYPES_WITH_ID_LOOKUP,
    ),
    _MatchManyScenario(
        "global_and_local_mixed",
        collection_tracks=[
            MockTrack("Global Track", ids={ISRC("GLOBAL1")}),
            MockTrack("Local Track", ids={FilePath(PurePath("/music/local.flac"))}),
        ],
        query_tracks=[
            MockTrack("GQ", ids={ISRC("GLOBAL1")}),
            MockTrack("LQ", ids={FilePath(PurePath("/music/local.flac"))}),
        ],
        applicable_types=_COLLECTION_TYPES_WITH_ID_LOOKUP,
    ),
)


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


class TestMatchMany:
    """Test the batched `match_many` method."""

    SKIP_COMBOS: ClassVar = [
        (False, False),
        (True, False),
        (False, True),
    ]

    @staticmethod
    def _collect_matches(matches_iter):
        """Consume an Iterable[Matches] and return a list."""
        return list(matches_iter)

    @staticmethod
    def _match_each(
        collection,
        query_tracks,
        skip_after_local_match=True,
        skip_after_perfect_fuzzy_match=True,
        cutoff=0.6,
    ):
        """Call `match` individually for each query track."""
        return [
            collection.match(
                t,
                skip_after_local_match=skip_after_local_match,
                skip_after_perfect_fuzzy_match=skip_after_perfect_fuzzy_match,
                cutoff=cutoff,
            )
            for t in query_tracks
        ]

    @staticmethod
    def _assert_matches_equal(
        result_a: Matches, result_b: Matches, *, check_order: bool = False
    ):
        """Assert two Matches results are semantically equal.

        By default compares ``truth``, ``best_match``, and ``similarity`` —
        the high-level properties that are deterministic regardless of
        ``map_threadpool`` completion order.

        Pass ``check_order=True`` for deterministic paths (ID-based lookups)
        where full list and similarity ordering is guaranteed.
        """
        assert result_a.truth == result_b.truth, "truth differs"
        assert result_a.best_match == result_b.best_match, (
            f"best_match differs: {result_a.best_match} vs {result_b.best_match}"
        )
        assert result_a.similarity == result_b.similarity, (
            f"similarity differs: {result_a.similarity} vs {result_b.similarity}"
        )

        if check_order:
            # Only for deterministic paths (ID-based lookups)
            assert result_a.found == result_b.found, (
                f"found list differs: {result_a.found} vs {result_b.found}"
            )
            assert result_a.found_similarities == result_b.found_similarities, (
                f"similarities differ: {result_a.found_similarities}"
                f" vs {result_b.found_similarities}"
            )

    @pytest.mark.parametrize("scenario", _MATCH_MANY_SCENARIOS, ids=lambda s: s.name)
    @pytest.mark.parametrize("skip_after_local, skip_after_fuzzy", SKIP_COMBOS)
    @pytest.mark.parametrize("collection_type", _ALL_COLLECTION_TYPES)
    def test_equivalent_to_match(
        self,
        scenario: _MatchManyScenario,
        skip_after_local: bool,
        skip_after_fuzzy: bool,
        collection_type: type,
    ) -> None:
        """match_many yields the same results as calling match for each track."""
        if collection_type not in scenario.applicable_types:
            pytest.skip(
                f"{collection_type.__name__} not applicable for {scenario.name}"
            )

        col = collection_type(scenario.collection_tracks)

        expected = self._match_each(
            col,
            scenario.query_tracks,
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        )
        results = self._collect_matches(
            col.match_many(
                scenario.query_tracks,
                skip_after_local_match=skip_after_local,
                skip_after_perfect_fuzzy_match=skip_after_fuzzy,
            )
        )

        assert len(results) == len(scenario.query_tracks)
        for expected_result, actual_result in zip(expected, results):
            self._assert_matches_equal(expected_result, actual_result)

    @pytest.mark.parametrize("skip_after_local, skip_after_fuzzy", SKIP_COMBOS)
    @pytest.mark.parametrize("collection_type", _COLLECTION_TYPES_WITH_ID_LOOKUP)
    def test_local_id_high_similarity_passes_cutoff(
        self,
        skip_after_local: bool,
        skip_after_fuzzy: bool,
        collection_type: type,
    ) -> None:
        """Local ID match where metadata also matches -> similarity >= cutoff.

        Covers lines 469-473: the record + skip_after_local_match
        and skip_after_perfect_fuzzy_match branches inside the local-ID
        stage of match_many, which are only reached when the fuzzy
        similarity between the query and the found track meets the cutoff.
        """
        lid = FilePath(PurePath("/music/same_title.flac"))
        col = collection_type([MockTrack("Same Title", ids={lid})])
        query = [MockTrack("Same Title", ids={lid})]

        expected = self._match_each(
            col,
            query,
            skip_after_local_match=skip_after_local,
            skip_after_perfect_fuzzy_match=skip_after_fuzzy,
        )
        results = self._collect_matches(
            col.match_many(
                query,
                skip_after_local_match=skip_after_local,
                skip_after_perfect_fuzzy_match=skip_after_fuzzy,
            )
        )
        assert len(results) == 1
        self._assert_matches_equal(expected[0], results[0])

    @pytest.mark.parametrize(
        "collection_type",
        [MockInfoLookupCollection, MockFullCapabilityCollection],
    )
    def test_info_multiple_matches_per_query(self, collection_type: type) -> None:
        """Info stage inner loop iterates multiple matches for one query.

        Covers branch 488->486: when find_many_by_info returns
        more than one track, the inner loop must iterate past a match
        whose similarity is below the cutoff (jumping from 488 to 486).
        """
        col = collection_type(
            [
                MockTrack("Dup", artists=["Foo"]),
                # Very different artist -> fuzzy similarity approx 0.55 < 0.6
                MockTrack("Dup", artists=["Something Completely Different And Long"]),
            ]
        )
        query = [MockTrack("Dup", artists=["Foo"])]

        results = list(col.match_many(query))
        assert len(results) == 1
        # Only the high-similarity match passes the default cutoff
        assert len(results[0].found) == 1
        assert results[0].best_match is not None
        assert results[0].best_match.title == "Dup"

    @pytest.mark.parametrize("skip_after_local, skip_after_fuzzy", SKIP_COMBOS)
    def test_fallback_local_id_match(
        self, skip_after_local: bool, skip_after_fuzzy: bool
    ) -> None:
        """Fallback stage processes local IDs in a stream-only collection.

        Covers lines 514-517: the record + skip_after_local_match
        path inside the fallback stage when a stream-only collection
        (MockTrackStreamCollection) encounters a local-ID intersection.
        """
        lid = FilePath(PurePath("/music/fallback_local.flac"))
        col = MockTrackStreamCollection([MockTrack("FB", ids={lid})])
        query = [MockTrack("FB", ids={lid})]

        results = list(
            col.match_many(
                query,
                skip_after_local_match=skip_after_local,
                skip_after_perfect_fuzzy_match=skip_after_fuzzy,
            )
        )
        assert len(results) == 1
        assert results[0].best_match is not None
        assert results[0].best_match.title == "FB"

    @pytest.mark.parametrize("skip_after_fuzzy", [True, False])
    def test_fallback_info_lookup_branch(self, skip_after_fuzzy: bool) -> None:
        """Fallback stage with TrackStream + InfoLookup (no IDLookup).

        Covers branch 519->522: when has_info_lookup is True
        inside the fallback, not has_info_lookup is skipped and
        execution jumps from the if on 519 to the
        skip_after_perfect_fuzzy_match check on 522.
        """
        col = MockStreamInfoCollection([MockTrack("Info In Fallback")])
        query = [MockTrack("Info In Fallback")]

        results = list(
            col.match_many(
                query,
                skip_after_perfect_fuzzy_match=skip_after_fuzzy,
            )
        )
        assert len(results) == 1
        assert results[0].best_match is not None
        assert results[0].best_match.title == "Info In Fallback"

    def test_empty_input(self):
        """match_many with no tracks yields no results."""
        col = MockFullCapabilityCollection(
            [MockTrack("Some Track", ids={ISRC("ISRC")})]
        )
        results = list(col.match_many([]))
        assert results == []

    def test_all_no_matches(self):
        """When no tracks match, all results are empty Matches."""
        col = MockTrackStreamCollection([MockTrack("Existing", ids={ISRC("ISRC")})])
        query = [
            MockTrack("Unknown A"),
            MockTrack("Unknown B", ids={ISRC("OTHER")}),
        ]
        results = list(col.match_many(query))

        assert len(results) == 2
        for r in results:
            assert r.best_match is None
            assert r.similarity == 0.0

    def test_result_order_preserved(self):
        """match_many yields results in the same order as the input tracks."""
        col = MockFullCapabilityCollection(
            [
                MockTrack("A", ids={ISRC("ISRC_A")}),
                MockTrack("B", ids={ISRC("ISRC_B")}),
                MockTrack("C", ids={ISRC("ISRC_C")}),
            ]
        )
        # Query in non-sorted order
        query = [
            MockTrack("C Query", ids={ISRC("ISRC_C")}),
            MockTrack("A Query", ids={ISRC("ISRC_A")}),
            MockTrack("B Query", ids={ISRC("ISRC_B")}),
        ]
        results = list(col.match_many(query))

        assert len(results) == 3
        # Results preserve query input order: C, A, B
        assert results[0].best_match is not None and results[0].best_match.title == "C"
        assert results[1].best_match is not None and results[1].best_match.title == "A"
        assert results[2].best_match is not None and results[2].best_match.title == "B"

    def test_cutoff_filters_matches(self):
        """A high cutoff removes low-similarity matches."""
        col = MockTrackStreamCollection([MockTrack("Exact Match")])
        query = [MockTrack("Something Completely Different")]

        # With low cutoff, the fuzzy match may pass
        results_low = list(col.match_many(query, cutoff=0.0))
        # With high cutoff, it's filtered out
        results_high = list(col.match_many(query, cutoff=1.0))

        assert results_low[0].best_match is not None
        assert results_high[0].best_match is None
