from plistsync.core.playlist import PlaylistCollection


class MockPlaylist(PlaylistCollection):
    """Mock PlaylistCollection implementation for testing."""

    def __init__(self, name: str, tracks: None | list = None):
        self._name = name
        self._tracks = tracks or []

    @property
    def name(self) -> str:
        return self._name

    def apply_changes(self, playlist_changes) -> None:
        pass
