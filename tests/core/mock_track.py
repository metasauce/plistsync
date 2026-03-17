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
    def info(self) -> TrackInfo:
        return self._info

    @property
    def global_ids(self) -> GlobalTrackIDs:
        return self._global_ids

    @property
    def local_ids(self) -> LocalTrackIDs:
        return self._local_ids
