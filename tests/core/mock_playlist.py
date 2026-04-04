import random
from typing import Any
from plistsync.core import Track
from plistsync.core.playlist import (
    MultiRequestServicePlaylist,
    OfflinePlaylist,
    PlaylistIDs,
    ServicePlaylist,
    Snapshot,
)


class MockServicePlaylist(
    OfflinePlaylist,
    ServicePlaylist[Track],
):
    """Mock PlaylistCollection implementation for testing."""

    def __init__(self, *args, **kwargs):
        self.log: list[tuple[Any, ...]] = []
        super().__init__(*args, **kwargs)

    @classmethod
    def get_or_create_from_ids(cls, ids: PlaylistIDs | None = None):
        return cls(name="name", description="description")

    def _remote_delete(self):
        self.log.append(("remote_delete",))

    def _remote_commit(self, before: Snapshot[Track], after: Snapshot[Track]):
        self.log.append(("remote_commit",))


class MockMultiRequestServicePlaylist(
    OfflinePlaylist,
    MultiRequestServicePlaylist[Track],
):
    """Mock IncrementalPlaylistCollection implementation for testing."""

    def __init__(self, *args, **kwargs):
        self.log: list[tuple[Any, ...]] = []
        super().__init__(*args, **kwargs)

    @classmethod
    def get_or_create_from_ids(cls, ids: PlaylistIDs | None = None):
        return cls(name="name", description="description")

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
        return track.global_ids.get("isrc", str(random.randbytes(10)))
