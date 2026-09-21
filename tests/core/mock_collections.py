from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, ClassVar

from plistsync.core.collection import (
    Collection,
    IDLookup,
    InfoLookup,
    Library,
    TrackStream,
)
from plistsync.core.playlist import PlaylistInfo

from .mock_playlist import MockPlaylistID, MockServicePlaylist
from .mock_track import MockTrack

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import Any

    from plistsync.core import PlaylistID, TrackID
    from plistsync.core.track import TrackInfo


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


class MockStreamInfoCollection(Collection, InfoLookup, TrackStream):
    """Mock collection with TrackStream + InfoLookup, but no IDLookup.

    Exercises the fallback path where ``has_info_lookup`` is True
    inside the ``match_many`` fallback stage (the ``519→522`` branch).
    """

    def __init__(self, tracks: list[MockTrack] | None = None):
        self._tracks = tracks or []

    def find_by_info(self, info: TrackInfo) -> Iterator[MockTrack]:
        for track in self._tracks:
            if info.get("title") == track.title:
                yield track

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


class MockLibrary(
    Library[MockTrack, MockServicePlaylist], IDLookup[MockTrack], service="test"
):
    """Mock library with a configurable track catalog.

    ``tracks`` and ``created`` are class attributes so tests can configure
    the library before the code under test instantiates it by class.
    """

    tracks: ClassVar[list[MockTrack]] = []
    """Tracks :meth:`find_by_ids` searches."""

    created: ClassVar[list[MockServicePlaylist]] = []
    """Playlists created through :meth:`create_playlist`."""

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the mock."""
        return "test"

    def find_by_ids(self, ids: Iterable[TrackID]) -> MockTrack | None:
        for tid in ids:
            for track in self.tracks:
                if tid in track.ids:
                    return track
        return None

    def find_many_by_ids(
        self, track_ids_batch: Iterable[Iterable[TrackID]]
    ) -> Iterable[MockTrack | None]:
        return [self.find_by_ids(ids) for ids in track_ids_batch]

    @property
    def playlists(self) -> Iterable[MockServicePlaylist]:
        return MockLibrary.created

    def get_playlist(
        self,
        *,
        id: PlaylistID | str | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> MockServicePlaylist | None:
        for playlist in MockLibrary.created:
            if (id is not None and playlist.id.serial == str(id)) or (
                name is not None and playlist.name == name
            ):
                return playlist
        return None

    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: list[MockTrack] | None = None,
    ) -> MockServicePlaylist:
        playlist = MockServicePlaylist(
            id=MockPlaylistID(name),
            info=PlaylistInfo(name=name, description=description),
            tracks=list(tracks or []),
        )
        MockLibrary.created.append(playlist)
        return playlist
