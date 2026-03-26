import random
from typing import Any
from plistsync.core.playlist import (
    MultiRequestPlaylistCollection,
    PlaylistCollection,
    PlaylistInfo,
    Snapshot,
)
from tests.core.mock_track import MockTrack


class MockPlaylist(PlaylistCollection[MockTrack]):
    """Mock PlaylistCollection implementation for testing."""

    def __init__(
        self,
        name: str,
        tracks: None | list = None,
        remote_associated: bool = True,
    ):
        self._info: PlaylistInfo = {"name": name}
        self.log: list[tuple[Any, ...]] = []
        self._tracks = tracks or []
        self._remote_associated = remote_associated

    @property
    def info(self) -> PlaylistInfo:
        return self._info

    @info.setter
    def info(self, value: PlaylistInfo):
        self._info = value

    @property
    def remote_associated(self):
        return self._remote_associated

    def _remote_commit(self, before: Snapshot[MockTrack], after: Snapshot[MockTrack]):
        self.log.append(("remote_commit",))

    def _remote_create(self):
        self.log.append(("remote_create",))
        self._remote_associated = True

    def _remote_delete(self):
        self.log.append(("remote_delete",))
        self._remote_associated = False


class MockPlaylistMultiRequest(MultiRequestPlaylistCollection[MockTrack], MockPlaylist):
    """Mock IncrementalPlaylistCollection implementation for testing."""

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
