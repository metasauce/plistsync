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
    """

    file_path: str
    """Local filesystem path to the track file.

    This is not globally unique because file paths may differ across devices
    or mount points, even if the underlying track is the same.
    """

    beets_id: str
    """Track ID from a local Beets library.

    Unique only within a local Beets library. Different libraries may assign
    different IDs to the same track.
    """

    plex_id: str
    """Track ID from a Plex media server library.

    Unique only within a single Plex library. The same track in another Plex
    server or library may have a different ID.
    """


class TrackInfo(TypedDict):
    """A serialized track.

    This is the dictionary representation of a track.
    """

    title: str
    artists: list[str]
    albums: list[str]
    path: NotRequired[str]


class TrackDict(TrackInfo, TypedDict):
    """A serialized track with identifiers.

    This is the dictionary representation of a track with identifiers.
    """

    global_ids: GlobalTrackIDs
    local_ids: LocalTrackIDs


class Track(ABC):
    """An abstract class representing a track.

    A track is a piece of music. It has a title, artists, albums and identifiers. It can be used in a number of places where the generic information about a track is needed.
    """

    # ----------------------------------- Info ----------------------------------- #

    @property
    @abstractmethod
    def title(self) -> str:
        """The title of the track."""

    @property
    @abstractmethod
    def artists(self) -> list[str]:
        """The name of the artists.

        The first artist is the main artist.
        If the track has no artist, return an empty list.
        """

    @property
    @abstractmethod
    def albums(self) -> list[str]:
        """The name of the albums the track is in.

        If the track is not in any album, return empty list.

        TODO:
        -----
        Eventually we might want to use an album object
        here. E.g.:

        .. code-block:: json

            {
                "name": "Album name",
                "release_date": "2021-01-01",
                "artists": ["Artist 1", "Artist 2"],
                "cover": "file:///path/to/file"
            }



        """

    @property
    def path(self) -> Path:
        """The path to the file of the track."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement path property."
        )

    @property
    def info(self) -> TrackInfo:
        """Get this tracks information.

        This may not include any identifiers.
        """

        ret = TrackInfo(
            title=self.title,
            artists=self.artists,
            albums=self.albums,
        )
        try:
            ret["path"] = str(self.path)
        except NotImplementedError:
            pass

        return ret

    # -------------------------------- Matching --------------------------------- #

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

    @property
    def isrc(self) -> str | None:
        """International Standard Recording Code."""
        return self.global_ids.get("isrc")

    # ------------------------------- Serialization ------------------------------ #

    @property
    def primary_artist(self) -> str | None:
        """The main artist of the track.

        If the track has no artist, return an empty string.
        """
        return self.artists[0] if self.artists else None

    def to_dict(self) -> TrackDict:
        """Convert the track to a dictionary."""

        return TrackDict(
            **self.info,
            global_ids=self.global_ids,
            local_ids=self.local_ids,
        )

    @abstractmethod
    def serialize(self) -> dict:
        """Serialize the track to a dictionary."""

    @classmethod
    @abstractmethod
    def deserialize(cls, data: dict) -> "Track":
        """Deserialize a dictionary to a track."""

    # ----------------------------------- Other ---------------------------------- #

    def __repr__(self) -> str:
        return f"Track[{self.primary_artist} > {self.title}]"
