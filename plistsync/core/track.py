"""Abstract representation of a music track."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import PurePath
from typing import TypedDict


class GlobalTrackIDs(TypedDict, total=False):
    """Global Unique identifiers for a track.

    Each identifier in this collection should uniquely identify a track
    across all systems and collections. Unlike local identifiers, these
    are intended to allow unambiguous track matching across devices,
    libraries, or services.

    Corresponds to collections-protocol `GlobalLookup`.
    """

    tidal_id: str
    """Tidal ID of the track.

    Globally unique within the Tidal service.
    """

    isrc: str
    """International Standard Recording Code.

    A standardized identifier intended to be globally unique for a recording.
    TODO: A track may have multiple ISRCs (e.g., different releases or regions),
    so this field may need to support multiple values in the future.
    """

    spotify_id: str
    """Spotify ID of the track.

    Globally unique within the Spotify service.
    """


class LocalTrackIDs(TypedDict, total=False):
    """Locally scoped identifiers for a track.

    These identifiers are unique only within a specific collection or context,
    such as a local library, playlist, database, or device. They are intended
    for identifying a track within that local scope and may not be unique globally.

    Corresponds to collections-protocol `LocalLookup`.
    """

    file_path: PurePath
    """Local (pure) filesystem path to the track file.

    This is not globally unique because file paths may differ across devices
    or mount points, even if the underlying track is the same.
    (This is also why we use PurePath, which is OS-agnostic, instead of Path.)
    """

    beets_id: int
    """Track ID from a local Beets library.

    Unique only within a local Beets library. Different libraries may assign
    different IDs to the same track.
    """

    plex_id: str
    """Track ID from a Plex media server library.

    Unique only within a single Plex library. The same track in another Plex
    server or library may have a different ID.
    """


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

    # ----------------------------- Info Getters ----------------------------- #

    # Lets not overdo it, in principle we could expose all underlying data, but
    # this bloats a lot.
    # Convention: The convenience getters give value or None,
    # or lists that can be empty but have the same length as the input

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
        return self.local_ids.get("file_path", None)

    @property
    def isrc(self) -> str | None:
        """International Standard Recording Code."""
        return self.global_ids.get("isrc", None)

    @property
    def primary_artist(self) -> str | None:
        """The main artist of the track.

        If the track has no artist, return an empty string.
        """
        return self.artists[0] if self.artists else None

    # --------------------------------- Contracts -------------------------------- #

    # Every track has to implement all three contracts.

    @property
    @abstractmethod
    def info(self) -> TrackInfo:
        """Get this tracks information."""
        ...

    @property
    @abstractmethod
    def global_ids(self) -> GlobalTrackIDs:
        """The globally unique identifiers of this track."""
        ...

    @property
    @abstractmethod
    def local_ids(self) -> LocalTrackIDs:
        """The locally unique identifiers of this track."""
        ...

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

        # Compare global_ids fields
        for key in set(track1.global_ids.keys()).union(track2.global_ids.keys()):
            v1, v2 = track1.global_ids.get(key), track2.global_ids.get(key)
            if v1 != v2:
                diffs[f"global_ids.{key}"] = (v1, v2)

        # Compare local_ids fields
        for key in set(track1.local_ids.keys()).union(track2.local_ids.keys()):
            v1, v2 = track1.local_ids.get(key), track2.local_ids.get(key)
            if v1 != v2:
                diffs[f"local_ids.{key}"] = (v1, v2)

        return diffs

    def __eq__(self, other: object) -> bool:
        """Check if two tracks are equal based on their data."""
        if not isinstance(other, Track):
            return False

        # TODO: Design choice:
        # when is a track from another serivce the same track?
        return (
            self.info == other.info
            and self.global_ids == other.global_ids
            and self.local_ids == other.local_ids
        )

    def __hash__(self) -> int:
        """Generate a hash based on the track's data."""
        # We need to convert lists to tuples and handle None values
        info_hash = tuple(
            sorted(
                (k, tuple(v) if isinstance(v, list) else v)
                for k, v in self.info.items()
            )
        )
        global_ids_hash = tuple(sorted(self.global_ids.items()))
        local_ids_hash = tuple(sorted(self.local_ids.items()))

        return hash((info_hash, global_ids_hash, local_ids_hash))

    def __repr__(self) -> str:
        return f"Track[{self.primary_artist} > {self.title}, hash: {hash(self)}]"
