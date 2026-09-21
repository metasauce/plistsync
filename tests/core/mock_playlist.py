from __future__ import annotations
from dataclasses import dataclass
from functools import cache
import random
from typing import Any, Self, TYPE_CHECKING
from unittest.mock import Mock
from plistsync.core.ids import PlaylistID
from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    OfflinePlaylist,
    ServicePlaylist,
)
from plistsync.core.track import OfflineTrack

if TYPE_CHECKING:
    from plistsync.core.playlist import (
        Snapshot,
    )


@dataclass(frozen=True)
class MockPlaylistID(PlaylistID, service="test"):
    """Minimal playlist ID for tests, serialized as ``test:playlist:<id>``."""

    id: str

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a ``test:playlist:<id>`` serial or a raw id."""
        if value.startswith("test:playlist:"):
            value = value[len("test:playlist:") :]
        return cls(value)

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the mock."""
        return "test"

    @property
    def serial(self) -> str:
        return f"test:playlist:{self.id}"

    @property
    def url(self) -> str:
        """Public web URL."""
        return f"https://example.com/playlist/{self.id}"

    def __str__(self) -> str:
        return self.id


class MockServicePlaylist(
    OfflinePlaylist, ServicePlaylist[OfflineTrack], service="test"
):
    """Mock PlaylistCollection implementation for testing."""

    def __init__(self, *args, **kwargs):
        self.log: list[tuple[Any, ...]] = []
        super().__init__(*args, **kwargs)
        self.library = Mock()

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the mock."""
        return "test"

    def _remote_delete(self):
        self.log.append(("remote_delete",))

    def _remote_commit(
        self, before: Snapshot[OfflineTrack], after: Snapshot[OfflineTrack]
    ):
        self.log.append(("remote_commit",))


class MockMultiRequestServicePlaylist(
    OfflinePlaylist, MultiRequestServicePlaylist[OfflineTrack], service="test"
):
    """Mock IncrementalPlaylistCollection implementation for testing."""

    def __init__(self, *args, **kwargs):
        self.log: list[tuple[Any, ...]] = []
        super().__init__(*args, **kwargs)
        self.library = Mock()

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the mock."""
        return "test"

    def _remote_delete(self):
        self.log.append(("remote_delete",))

    def _remote_delete_track(
        self,
        idx: int,
        track,
        tracks_before,
    ) -> None:
        if isinstance(track, list):
            for t in track:
                self.log.append(("delete", idx, t))
        else:
            self.log.append(("delete", idx, track))

    def _remote_insert_track(
        self,
        idx: int,
        track,
        tracks_before,
    ) -> None:
        if isinstance(track, list):
            for t in track:
                self.log.append(("insert", idx, t))
        else:
            self.log.append(("insert", idx, track))

    def _remote_update_metadata(
        self, new_name: str | None = None, new_description: str | None = None
    ):
        self.log.append(("update_meta", new_name, new_description))

    @staticmethod
    def _track_key(track) -> str:
        for tid in track.ids:
            return tid.serial
        return str(random.randbytes(10))
