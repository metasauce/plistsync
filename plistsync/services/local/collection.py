from __future__ import annotations

from collections.abc import Generator, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from plistsync.core import Collection, TrackID
from plistsync.core.collection import IDLookup

from .track import FileCache, LocalTrack


class LocalCollection(Collection, IDLookup):
    """A a lazy collection of tracks from a file system.

    This collection does not load all tracks into memory at once. Instead it
    iterates over the tracks in the file system as needed.
    """

    path: Path
    _cache: FileCache | None

    def __init__(self, path: Path | str, cache: FileCache | None = None):
        """
        Create a new lazy collection of tracks from a file system path.

        Parameters
        ----------
        path: Path | str
            The path to the directory containing the tracks.
        cache: FileCache | None
            Optional shared cache for file metadata to avoid repeated disk reads.
        """

        if isinstance(path, str):
            path = Path(path)

        self.path = path
        self._cache = cache

        # Check if the path exists
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist.")

    def find_by_ids(self, ids: Iterable[TrackID]) -> LocalTrack | None:
        """Find a track by its IDs."""
        identifiers = frozenset(ids)
        if not identifiers:
            return None

        with ThreadPoolExecutor(max_workers=4) as executor:

            def _get_track_ids(track: LocalTrack) -> frozenset[TrackID]:
                return track.ids

            futures = {executor.submit(_get_track_ids, track): track for track in self}

        for future in as_completed(futures):
            track = futures[future]
            track_ids: frozenset[TrackID] = future.result()

            if identifiers & track_ids:
                return track

        return None

    def __iter__(self) -> Generator[LocalTrack, None, None]:
        # Use rglob to recursively find all files
        for file_path in self.path.rglob("*"):
            if file_path.is_file():
                yield LocalTrack(file_path, cache=self._cache)
