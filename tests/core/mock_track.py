from typing import Any
from plistsync.core.track import Track, TrackInfo, GlobalTrackIDs, LocalTrackIDs


class MockTrack(Track):
    """Mock Track implementation for testing."""

    def __init__(
        self,
        title: str = "Test Track",
        artists: list[str] | None = None,
        albums: list[str] | None = None,
        global_ids: GlobalTrackIDs | None = None,
        local_ids: LocalTrackIDs | None = None,
    ):
        self._title = title
        self._artists = artists or []
        self._albums = albums or []
        self._global_ids = global_ids or {}
        self._local_ids = local_ids or {}
        self._info = TrackInfo(
            **{
                "title": title,
                "artists": self._artists,
                "albums": self._albums,
            }
        )

    @property
    def global_ids(self) -> GlobalTrackIDs:
        return self._global_ids

    @property
    def local_ids(self) -> LocalTrackIDs:
        return self._local_ids

    @property
    def info(self) -> TrackInfo:
        return self._info

    def serialize(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "artists": self.artists,
            "global_ids": dict(self.global_ids),
            "local_ids": dict(self.local_ids),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "MockTrack":
        return cls(
            title=data["title"],
            artists=data["artists"],
            global_ids=data.get("global_ids", {}),
            local_ids=data.get("local_ids", {}),
        )
