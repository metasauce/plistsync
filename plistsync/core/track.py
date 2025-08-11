from abc import ABC, abstractmethod
from pathlib import Path
from typing import NotRequired, TypedDict


# Define the allowed identifiers with `total=False`
class TrackIdentifiers(TypedDict):
    """Unique identifiers for a track.

    Each identifier has to uniquely identify a track!
    """

    # Tidal ID of the track normally a number
    tidal: NotRequired[str]
    # International Standard Recording Code
    # TODO: Add multiple isrcs support in the future
    isrc: NotRequired[str]
    # Path is not a unique identifier, because mount points might change.
    # but matching also works via TrackInfo, where we give path the highest prio.


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

    identifiers: TrackIdentifiers


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

        TODO: Eventually we want to use an album object here. E.g.
        {
            "name": "Album name",
            "release_date": "2021-01-01",
            "artists": ["Artist 1", "Artist 2"],
            "cover": "https://example"| "file:///path/to/file"
        }
        could be typed as a TypedDict.
        """

    @property
    def path(self) -> Path:
        """The path to the file of the track."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement path property."
        )

    @property
    def info(self) -> TrackInfo:
        """Get the track information without identifiers."""

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

    # -------------------------------- Identifiers -------------------------------- #

    @property
    @abstractmethod
    def identifiers(self) -> TrackIdentifiers:
        """The identifiers of this track.

        The keys are the name of the identifier, the values are the ids.

        For example:
        ```python
        {
            "isrc": "USAT29900609"
        }
        ```
        """

    @property
    def isrc(self) -> str | None:
        """International Standard Recording Code."""
        return self.identifiers.get("isrc")

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
            identifiers=self.identifiers,
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
