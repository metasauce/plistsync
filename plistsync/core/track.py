"""Abstract representation of a music track."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from copy import copy
from pathlib import PurePath
from typing import TypedDict

from plistsync.core.ids import ISRC, FilePath, TrackID
from plistsync.logger import log


class TrackInfo(TypedDict, total=False):
    """A serialized track.

    This is the dictionary representation of a track.

    Corresponds to collections-protocol `InfoLookup`.
    """

    title: str
    artists: list[str]
    albums: list[str]
    # TODO: Add _unified_ fields like genres, year etc. they should follow _our_
    # convention, likely close to beets.


class Track(ABC):
    """An abstract class representing a track.

    A track is a piece of music. It has a title, artists, albums and identifiers.
    It can be used in a number of places where the generic information about a track
    is needed.
    """

    # --------------------------- Required (protocol) ---------------------------- #

    @property
    @abstractmethod
    def info(self) -> TrackInfo:
        """Get this tracks information."""
        ...

    @property
    @abstractmethod
    def ids(self) -> set[TrackID]:
        """The identifiers of this track."""
        ...

    # ----------------------------- Info Getters ----------------------------- #

    @property
    def title(self) -> str | None:
        """The title of the track."""
        return self.info.get("title", None)

    @property
    def artists(self) -> list[str]:
        """The name of the artists.

        The first artist is the main artist.
        If the track has no artist, return an empty list.
        """
        return self.info.get("artists", [])

    @property
    def albums(self) -> list[str]:
        """The name of the albums the track is in.

        If the track is not in any album, return empty list.
        """
        return self.info.get("albums", [])

    @property
    def path(self) -> PurePath | None:
        """The path to the file of the track."""
        paths = [id.path for id in self.ids if isinstance(id, FilePath)]
        if len(paths) > 1:
            log.warning(f"Found multiple paths: {paths}. Using the first one.")
        return paths[0] if paths else None

    @property
    def isrc(self) -> str | None:
        """International Standard Recording Code."""
        isrcs = [id.id for id in self.ids if isinstance(id, ISRC)]
        if len(isrcs) > 1:
            log.warning(f"Found multiple ISRCs: {isrcs}. Using the first one.")
        return isrcs[0] if isrcs else None

    @property
    def primary_artist(self) -> str | None:
        """The main artist of the track.

        If the track has no artist, return an empty string.
        """
        return self.artists[0] if self.artists else None

    # ----------------------------------- Other ---------------------------------- #

    def diff(self, track2: Track) -> dict:
        """Return a dict of differences between this and another track."""
        # TODO: still need to think about hashing and how we want to interpret equality.
        diffs = {}
        track1 = self

        # Compare info fields
        for key in set(track1.info.keys()).union(track2.info.keys()):
            v1, v2 = track1.info.get(key), track2.info.get(key)
            if v1 != v2:
                diffs[f"info.{key}"] = (v1, v2)

        # Compare ids by serial
        ids1 = {id.serial for id in track1.ids}
        ids2 = {id.serial for id in track2.ids}
        if ids1 != ids2:
            diffs["ids"] = (ids1 - ids2, ids2 - ids1)

        return diffs

    def __eq__(self, other: object) -> bool:
        """Check if two tracks are equal based on their data."""
        if not isinstance(other, Track):
            return False

        # TODO: Design choice:
        # when is a track from another serivce the same track?
        return self.info == other.info and self.ids == other.ids

    def __hash__(self) -> int:
        """Generate a hash based on the track's data."""
        # We need to convert lists to tuples and handle None values
        info_hash = tuple(
            sorted(
                (k, tuple(v) if isinstance(v, list) else v)
                for k, v in self.info.items()
            )
        )
        ids_hash = hash(frozenset(self.ids))

        return hash((info_hash, ids_hash))

    def __repr__(self) -> str:
        cls = type(self).__name__
        artist = self.primary_artist or "?"
        title = self.title or "?"
        return f"{cls}(artist={artist!r}, title={title!r})"


class OfflineTrack(Track):
    """A offline (in memory) track with attached service.

    This class provides a concrete implementation of `Track` for
    managing tracks in memory without any connection to online music services.
    It is useful as an intermediate representation during matching or syncing.
    """

    _info: TrackInfo
    _ids: set[TrackID]

    def __init__(
        self,
        info: TrackInfo,
        ids: Iterable[TrackID] | None = None,
    ):
        self._info = info
        self._ids = set(ids) if ids is not None else set()

    @property
    def info(self) -> TrackInfo:
        return self._info

    @property
    def ids(self) -> set[TrackID]:
        return self._ids

    def merge(self, track: Track) -> OfflineTrack:
        """Merge another track into this one.

        This operation returns a new offline track
        with the merged data.
        """
        info = copy(self.info)
        info.update(track.info)

        ids = copy(self.ids)
        ids.update(track.ids)

        return OfflineTrack(info, ids)

    @classmethod
    def from_track(cls, track: Track) -> OfflineTrack:
        """Create a offline track from arbitrary other track."""
        return cls(track.info, track.ids)
