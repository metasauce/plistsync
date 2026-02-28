from typing import Any
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo


class MockPlaylist(PlaylistCollection):
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

    def _remote_delete_track(self, idx: int, track, live_list) -> None:
        self.log.append(("delete", idx, track))

    def _remote_insert_track(self, idx: int, track, live_list) -> None:
        self.log.append(("insert", idx, track))

    def _remote_update_metadata(
        self, new_name: str | None = None, new_description: str | None = None
    ):
        self.log.append(("update_meta", new_name, new_description))

    def _remote_create(self):
        self.log.append(("remote_create",))
        self._remote_associated = True

    def _remote_delete(self):
        self.log.append(("remote_delete",))
        self._remote_associated = False

    @property
    def remote_associated(self):
        return self._remote_associated

    @staticmethod
    def _track_key(track) -> str:
        return track.global_ids["isrc"]  # Fixed to match test expectations
