from typing import Iterable, Iterator
from plistsync.core.track import TrackInfo, GlobalTrackIDs, LocalTrackIDs
from .mock_track import MockTrack

from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LocalLookup,
    TrackSearch,
    TrackStream,
)


class MockGlobalLookupCollection(Collection, GlobalLookup):
    """Mock collection with global lookup capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []
        self._tracks_by_global_id = {
            global_id: track
            for track in self.tracks
            for global_id in track.global_ids.values()
        }

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> MockTrack | None:
        for global_id in global_ids.values():
            if global_id in self._tracks_by_global_id:
                return self._tracks_by_global_id[global_id]
        return None


class MockLocalLookupCollection(Collection, LocalLookup):
    """Mock collection with local lookup capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []
        self._tracks_by_local_id = {
            local_id: track
            for track in self.tracks
            for local_id in track.local_ids.values()
        }

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> MockTrack | None:
        for local_id in local_ids.values():
            if local_id in self._tracks_by_local_id:
                return self._tracks_by_local_id[local_id]
        return None


class MockTrackSearchCollection(Collection, TrackSearch):
    """Mock collection with track search capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []

    def search_by_info(self, info: TrackInfo) -> Iterable[MockTrack]:
        for track in self.tracks:
            if info.get("title") == track.title:
                yield track


class MockTrackStreamCollection(Collection, TrackStream):
    """Mock collection with track streaming capability."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []

    def __iter__(self):
        return iter(self.tracks)


class MockFullCapabilityCollection(
    Collection, GlobalLookup, LocalLookup, TrackSearch, TrackStream
):
    """Mock collection with all capabilities."""

    def __init__(self, tracks: list[MockTrack] | None = None):
        self.tracks = tracks or []
        self._tracks_by_global_id = {
            global_id: track
            for track in self.tracks
            for global_id in track.global_ids.values()
        }
        self._tracks_by_local_id = {
            local_id: track
            for track in self.tracks
            for local_id in track.local_ids.values()
        }

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> MockTrack | None:
        for global_id in global_ids.values():
            if global_id in self._tracks_by_global_id:
                return self._tracks_by_global_id[global_id]
        return None

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> MockTrack | None:
        for local_id in local_ids.values():
            if local_id in self._tracks_by_local_id:
                return self._tracks_by_local_id[local_id]
        return None

    def search_by_info(self, info: TrackInfo) -> Iterator[MockTrack]:
        for track in self.tracks:
            if info.get("title") == track.title:
                yield track

    def __iter__(self):
        return iter(self.tracks)
