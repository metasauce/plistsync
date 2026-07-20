from __future__ import annotations
from plistsync.core.track import Track, TrackInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plistsync.core import TrackID


class MockTrack(Track, service="test"):
    """Mock Track implementation for testing."""

    def __init__(
        self,
        title: str = "Test Track",
        artists: list[str] | None = None,
        albums: list[str] | None = None,
        ids: set[TrackID] | None = None,
    ):
        self._title = title
        self._artists = artists or []
        self._albums = albums or []
        self._ids = ids or set()
        self._info = TrackInfo(
            **{
                "title": title,
                "artists": self._artists,
                "albums": self._albums,
            }
        )

    @property
    def info(self) -> TrackInfo:
        return self._info

    @property
    def ids(self) -> frozenset[TrackID]:
        return frozenset(self._ids)
