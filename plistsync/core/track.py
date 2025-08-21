from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import NotRequired, TypedDict


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


class LocalTrackIDs(TypedDict, total=False):
    """Locally scoped identifiers for a track.

    These identifiers are unique only within a specific collection or context,
    such as a local library, playlist, database, or device. They are intended
    for identifying a track within that local scope and may not be unique globally.

    Corresponds to collections-protocol `LocalLookup`.
    """

    file_path: Path
    """Local filesystem path to the track file.

    This is not globally unique because file paths may differ across devices
    or mount points, even if the underlying track is the same.
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
    # TODO: Add _unified_ fields like genres, year etc. they should follow _our_ convention,
    # likely close to beets.


class Track(ABC):
    """An abstract class representing a track.

    A track is a piece of music. It has a title, artists, albums and identifiers.
    It can be used in a number of places where the generic information about a track is needed.
    """

    # ----------------------------- Info Getters ----------------------------- #

    # Lets not overdo it, in principle we could expose all underlying data, but
    # this bloats a lot.
    # Convention: The convenience getters give value or None, or lists that can be empty.

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
    def path(self) -> Path | None:
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

    def __repr__(self) -> str:
        return f"Track[{self.primary_artist} > {self.title}]"
