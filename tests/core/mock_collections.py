from __future__ import annotations

from plistsync.core.collection import (
    Collection,
    IDLookup,
    InfoLookup,
    TrackStream,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mock_track import MockTrack
    from plistsync.core.track import TrackInfo
    from plistsync.core import TrackID
    from collections.abc import Iterable, Iterator


class MockIDLookupCollection(Collection, IDLookup):
    """Mock collection with ID lookup capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []
        self._tracks_by_id: dict[TrackID, MockTrack] = {}
        for track in self.tracks:
            for tid in track.ids:
                self._tracks_by_id[tid] = track

    def find_by_ids(self, ids: Iterable[TrackID]) -> MockTrack | None:
        for tid in ids:
            if tid in self._tracks_by_id:
                return self._tracks_by_id[tid]
        return None


class MockInfoLookupCollection(Collection, InfoLookup):
    """Mock collection with track search capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []

    def find_by_info(self, info: TrackInfo) -> Iterable[MockTrack]:
        for track in self.tracks:
            if info.get("title") == track.title:
                yield track


class MockTrackStreamCollection(Collection, TrackStream):
    """Mock collection with track streaming capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self._tracks = tracks or []

    @property
    def tracks(self) -> Iterable[MockTrack]:
        yield from self._tracks


class MockFullCapabilityCollection(Collection, IDLookup, InfoLookup, TrackStream):
    """Mock collection with all capabilities."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self._tracks = tracks or []
        self._tracks_by_id: dict[TrackID, MockTrack] = {}
        for track in self._tracks:
            for tid in track.ids:
                self._tracks_by_id[tid] = track

    def find_by_ids(self, ids: Iterable[TrackID]) -> MockTrack | None:
        for tid in ids:
            if tid in self._tracks_by_id:
                return self._tracks_by_id[tid]
        return None

    def find_by_info(self, info: TrackInfo) -> Iterator[MockTrack]:
        for track in self._tracks:
            if info.get("title") == track.title:
                yield track

    @property
    def tracks(self) -> Iterable[MockTrack]:
        yield from self._tracks
