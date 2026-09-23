from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Self

from plistsync.core.ids import TrackID
from plistsync.core.track import Track, TrackInfo


@dataclass(frozen=True)
class MockTrackID(TrackID, service="test"):
    """Minimal track ID for tests, serialized as ``test:track:<id>``."""

    id: str

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a ``test:track:<id>`` serial or a raw id."""
        if value.startswith("test:track:"):
            value = value[len("test:track:") :]
        return cls(value)

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the mock."""
        return "test"

    @property
    def serial(self) -> str:
        return f"test:track:{self.id}"

    @property
    def url(self) -> str:
        """Public web URL."""
        return f"https://example.com/track/{self.id}"

    def __str__(self) -> str:
        return self.id


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
