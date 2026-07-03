import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
from typing import ClassVar, Self


@dataclass(frozen=True)
class PlaylistID(ABC):
    """Immutable base for service-specific playlist identifiers.

    Decouples the service-specific representation from the generic playlist
    management logic.

    Should contain a unique identifier for a playlist
    within a specific service.
    Should not be passed down to the API layer of a service.
    There, the native, service-specific representation should be used,
    e.g. a simple `id` string for spotify, or the int `id` for plex.

    We need this abstraction to allow us to load and save playlists in a generic
    way i.e. to implement the loading logic only once but have it work for
    all services.
    """

    @classmethod
    @abstractmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (URL, URI, or raw id)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def serial(self) -> str:
        """
        Plistsync's internal string-representation of service specific playlist ID.

        By convention it should look like `service_name:your_custom:format` e.g.
        `spotify:playlist:actual_id`. This is not enforced but recommended.

        By convention, to get the _canonical_ representation that the service API
        understands, you should define `__str__` or `__int__` methods to get the
        shorter and convenient values.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(serial={self.serial!r})"


class Scope(Enum):
    """Scope in which the id can be used.

    This determines matching behavior of the id.
    """

    GLOBAL = "global"
    LOCAL = "local"


@dataclass(frozen=True)
class TrackID(ABC):
    """Immutable base for service-specific track identifiers.

    Decouples the service-specific representation from the generic track
    management logic.

    Should contain a unique identifier for a track
    within a specific service.
    Should not be passed down to the API layer of a service.
    There, the native, service-specific representation should be used,
    e.g. a simple `id` string for spotify, or the int `id` for plex.

    We need this abstraction to allow us to load and save tracks in a generic
    way i.e. to implement the loading logic only once but have it work for
    all services.
    """

    scope: ClassVar[Scope] = Scope.GLOBAL

    @classmethod
    @abstractmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (URL, URI, or raw id)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def serial(self) -> str:
        """
        Plistsync's internal string-representation of service specific track ID.

        By convention it should look like `service_name:your_custom:format` e.g.
        `spotify:track:actual_id`. This is not enforced but recommended.

        By convention, to get the _canonical_ representation that the service API
        understands, you should define `__str__` or `__int__` methods to get the
        shorter and convenient values.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}(serial={self.serial!r})"


# Commonly shared IDS


@dataclass(frozen=True)
class ISRC(TrackID):
    """International Standard Recording Code.

    A standardized identifier intended to be globally unique for a recording.
    """

    id: str
    """The raw 12-character ISRC (e.g. ``USRC17607839``)."""

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (URL, URI, serial, or raw id).

        Accepts the raw 12-character ISRC, the serial format
        (``isrc:XXAAA0000000``), or the dashed format (``XX-AAA-00-00000``).
        """
        value = value.strip()
        # Strip optional serial prefix
        if value.lower().startswith("isrc:"):
            value = value[5:]
        # Strip dashes from standard notation (e.g. US-AT1-99-00001)
        value = value.replace("-", "")
        value = value.upper()
        # Validate ISRC format: 12 characters, alphanumeric
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", value):
            raise ValueError(f"Invalid ISRC: {value!r}")
        return cls(value)

    @property
    def serial(self) -> str:
        """Plistsync's internal string-representation of ISRC."""
        return f"isrc:{self.id}"

    def __str__(self) -> str:
        """Compact display (just the raw id)."""
        return self.id


@dataclass(frozen=True)
class FilePath(TrackID):
    """File path identifier for local tracks.

    This is a simple wrapper around a file path, used to identify local tracks in a
    consistent way.
    """

    scope: ClassVar[Scope] = Scope.LOCAL

    path: PurePath
    """The filesystem path to the track file."""

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (raw path or serial ``file:...`` format)."""
        value = value.strip()
        if value.lower().startswith("file:"):
            value = value[5:]
        return cls(PurePath(value))

    @property
    def serial(self) -> str:
        """Plistsync's internal string-representation of the file path."""
        return f"file:{self.path.as_posix()}"

    def __str__(self) -> str:
        """Compact display (just the raw path string)."""
        return str(self.path)
