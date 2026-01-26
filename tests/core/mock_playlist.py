from typing import Any
from plistsync.core.playlist import PlaylistCollection


class MockPlaylist(PlaylistCollection):
    """Mock PlaylistCollection implementation for testing."""

    def __init__(self, name: str, tracks: None | list = None):
        self._name = name
        self._tracks = tracks or []
        self.log: list[tuple[Any, ...]] = []

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def _remote_delete_track(self, idx: int, track) -> None:
        self.log.append(("delete", idx, track))

    def _remote_insert_track(self, idx: int, track) -> None:
        self.log.append(("insert", idx, track))

    def _remote_update_metadata(
        self, new_name: str | None = None, new_description: str | None = None
    ):
        self.log.append(("update_meta", new_name, new_description))

    @staticmethod
    def _track_key(track) -> str:
        return track.global_ids["isrc"]  # Fixed to match test expectations
