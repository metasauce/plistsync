from __future__ import annotations

from itertools import chain
from pathlib import Path
from typing import List, Self, cast

from beets import art
from tinytag import TinyTag

from plistsync.core import Collection, GlobalTrackIDs, Track

from ...logger import log

TagDict = dict[str, list[str] | str | float]


class FileCache:
    """A file cache is a dictionary that maps file paths to track metadata.

    This is useful for collections that tightly integrate with files on disk.
    For example, plex api yields file paths via track metadata, but no isrc.
    Thus, we want to make a detour and read the isrc from file on disk.
    This is somewhat a reoccuring problem.

    TODO: what to have in cache when files are not available or cant be read?
    Empty dicts? None? Raise an error?

    """

    _file_cache: dict[Path, TagDict] = {}

    def __getitem__(self, path: Path) -> TagDict:
        if not path in self._file_cache:
            self._file_cache[path] = self.get_from_disk(path)
        return self._file_cache[path]

    def refresh_for_collection(self, collection: Collection):
        """Fill the cache with metadata from the collection.

        Reads all files defined in collection and stores the metadata in the cache.
        """

        if not collection.is_iterable():
            raise ValueError("The collection is not iterable, cant build cache.")

        for track in collection:
            try:
                path = track.path
            except NotImplementedError:
                log.debug(f"Track {track} does not implement `path`")
                continue

            try:
                self._file_cache[path] = self.get_from_disk(path)
            except:
                log.error(f"Could not read metadata. {track=} {path=}")

    @staticmethod
    def get_from_disk(path: Path) -> TagDict:
        """Get the metadata fresh from disk and update the cache for this track."""

        meta = cast(TagDict, TinyTag.get(path).as_dict())

        # tiny tag seems to have a lenghth one for many fields, extract!
        # and drop traktor4 cos it has a lot of data.
        meta.pop("traktor4", None)
        for key, value in meta.items():
            if isinstance(value, list) and len(value) == 1:
                meta[key] = value[0]

        if len(meta) == 0:
            log.warning(
                f"Could not read metadata from {path}. "
                + "Might be due to inconsistent mount points or permissions."
            )
        return meta


class LocalTrack(Track):
    """A locally available (on disk) track.

    Mostly lazy loaded but allows for caching
    of most metadata.
    """

    __path: Path
    __cache: FileCache | None = None

    def __init__(self, path: Path | str, cache: FileCache | None = None):
        if isinstance(path, str):
            path = Path(path)
        self.__path = path
        self.__cache = cache

        # Check if the path exists and is allowed by tinytag
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist.")
        if not TinyTag.is_supported(path):
            raise ValueError(f"File {path} is not supported by tinytag.")

    @property
    def path(self) -> Path:
        return self.__path

    @property
    def tags(self) -> TagDict:
        """Track tags. id3, vorbis, etc. as dict.

        Cached version of `read_tags`.
        """
        if self.__cache is not None:
            return self.__cache[self.path]
        else:
            return FileCache.get_from_disk(self.path)

    # ---------------------------------------------------------------------------- #
    #                                 ABC methods                                  #
    # ---------------------------------------------------------------------------- #

    @property
    def title(self) -> str:
        title: str | list[str] = self.tags.get("title", self.path.stem)  # type: ignore[assignment]
        if not isinstance(title, list):
            title = [title]
        return title[0]

    @property
    def artists(self) -> List[str]:
        artists: str | list[str] = self.tags.get("artist", [])  # type: ignore[assignment]
        if not isinstance(artists, list):
            artists = [artists]

        # In theory the type can also by List[float]
        # but this makes no sense for an artist field
        # and also it isnt supported by id3 and vorbis tags
        return artists

    @property
    def albums(self) -> List[str]:
        albums: str | list[str] = self.tags.get("album", [])  # type: ignore[assignment]
        if not isinstance(albums, list):
            albums = [albums]

        # In theory the type can also by List[float]
        # but this makes no sense for an albums field
        # and also it isnt supported by id3 and vorbis tags
        return albums

    @property
    def global_ids(self) -> GlobalTrackIDs:
        isrc_raw = self.tags.get("isrc", [])
        isrc: str | None = None

        if not isinstance(isrc_raw, list):
            # float, int does not make sense for isrc
            isrc_raw = [cast(str, isrc_raw)]

        # Parse from array if necessary
        # Sometimes the isrc is a list of isrcs
        if len(isrc_raw) > 0:
            # For vorbis and other non id3 tags
            # list tags might be strings with \x00 as separator
            # might be an issue with tinytag
            # and might be no problem if we switch to mutagen...

            # (flatmap split by \x00 and filter out empty strings)
            isrc_c: chain[str] = chain.from_iterable(
                map(lambda x: x.split("\x00"), isrc_raw)
            )
            isrc_raw = [x for x in isrc_c if x != ""]

            if len(isrc_raw) > 1:
                log.warning(f"Multiple ISRCs found for {self.path}: {isrc_raw}")
            isrc = isrc_raw[0]

        # Create typechecked identifiers dict
        res = GlobalTrackIDs()
        if isrc is not None:
            res["isrc"] = isrc

        return res

    def serialize(self) -> dict:
        return {
            "path": str(self.path),
        }

    @classmethod
    def deserialize(cls, data: dict) -> Self:
        return cls(data["path"])
