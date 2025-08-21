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
