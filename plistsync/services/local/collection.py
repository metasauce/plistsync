from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from plistsync.core import Collection, GlobalTrackIDs

from .track import LocalTrack


class LocalCollection(Collection):
    """A a lazy collection of tracks from a file system.

    This collection does not load all tracks into memory at once. Instead it
    iterates over the tracks in the file system as needed.
    """

    path: Path

    def __init__(self, path: Path | str):
        """
        Create a new lazy collection of tracks from a file system path.

        Parameters
        ----------
        path: Path | str
            The path to the directory containing the tracks.
        """

        if isinstance(path, str):
            path = Path(path)

        self.path = path

        # Check if the path exists
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist.")

    def find_by_identifiers(self, identifiers: GlobalTrackIDs) -> LocalTrack | None:
        if len(identifiers) == 0:
            return None

        # Not too sure if this has any performance benefits but
        # at least for the first read it should be faster than
        # doing it single threaded
        # Should be IO bound in most cases
        # TODO: max workers should be configurable
        with ThreadPoolExecutor(max_workers=4) as executor:

            def _get_track_identifiers(track: LocalTrack) -> GlobalTrackIDs:
                return track.global_ids

            futures = {
                executor.submit(_get_track_identifiers, track): track for track in self
            }

        for future in as_completed(futures):
            track = futures[future]
            track_ids: GlobalTrackIDs = future.result()

            # Search for each identifier in the tracks metadata
            for key, value in identifiers.items():
                if value is None or not isinstance(value, str):
                    continue

                found_value = track_ids.get(key)
                if found_value is None or not isinstance(found_value, str):
                    continue

                # Casefold comparison is more robust than
                # doing .lower() or .upper() as it handles
                # more edge cases
                value = value.casefold()
                found_value = found_value.casefold()
                if value == found_value:
                    return track

        return None

    def __iter__(self) -> Generator[LocalTrack, None, None]:
        # Use rglob to recursively find all files
        for file_path in self.path.rglob("*"):
            if file_path.is_file():
                potential_track = LocalTrack(file_path)
                if potential_track is not None:
                    yield potential_track
