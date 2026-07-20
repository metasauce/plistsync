from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
from typing import ClassVar, Self

from plistsync.logger import log
from plistsync.services import ServiceLoader
from plistsync.services.registry import Registry


class SerialID(ABC):
    """Immutable base for identifiers with a canonical, namespaced serial form."""

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

    @classmethod
    def prefix(cls) -> str:
        """Prefix, inferred from the module path.

        Should be unique! Defaults to the first part of the module path
        after ``plistsync.services`` i.e. ``plistsync.services.<name>.*``
        get ``<name>``. Classes outside a service module must override this.
        """
        parts = cls.__module__.split(".")
        if "services" in parts:
            return parts[parts.index("services") + 1]
        raise ValueError(
            f"Cannot infer namespace from module {cls.__module__!r}; "
            f"override {cls.__name__}.namespace()"
        )

    def __post_init__(self) -> None:
        """Enforce that ``serial`` starts with the namespace prefix.

        Skipped when the namespace cannot be inferred (e.g. test doubles).
        Subclasses with a custom ``__init__`` or ``__post_init__`` bypass this
        check entirely; the serial round-trip tests guard those.
        """
        try:
            expected = type(self).prefix() + ":"
        except ValueError:
            return
        if not self.serial.startswith(expected):
            raise ValueError(
                f"{type(self).__name__}.serial must start with {expected!r}, "
                f"got {self.serial!r}"
            )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(serial={self.serial!r})"


class Scope(Enum):
    """Scope in which the id can be used.

    This determines matching behavior of the id.
    """

    GLOBAL = "global"
    LOCAL = "local"


@dataclass(frozen=True, repr=False)
class PlaylistID(SerialID, ABC, Registry):
    """Immutable base for playlist identifiers (serial: ``<service>:playlist:<id>``)."""

    @classmethod
    def prefix(cls) -> str:
        return f"{super().prefix()}:playlist"

    @classmethod
    def from_serial(cls, serial: str) -> PlaylistID | None:
        """Load from a serial string (``<service>:playlist:<payload>``).

        This is a convenience method to parse a serial string into the correct
        subclass of :class:`PlaylistID` for the service. Returns ``None`` if the
        service is not available or no matching identifier class is found.
        """
        try:
            service_name = serial.split(":", 1)[0]
        except IndexError:
            log.warning(
                f"Invalid playlist serial {serial!r}, cannot parse service name"
            )
            return None

        service = ServiceLoader.get(service_name)
        if not service:
            log.warning(
                f"Service {service_name!r} not available for playlist serial {serial!r}"
            )
            return None

        for pid_cls in service.playlist_ids():
            # Check if prefix matches
            if pid_cls.prefix().startswith(service_name):
                try:
                    return pid_cls.parse(serial)
                except ValueError:
                    continue

        log.info(
            f"No playlist identifier class found for serial {serial!r}"
            f" in service {service_name!r}"
        )
        return None


@dataclass(frozen=True, repr=False)
class TrackID(SerialID, ABC, Registry):
    """Immutable base for track identifiers (serial: ``<service>:track:<id>``)."""

    scope: ClassVar[Scope] = Scope.GLOBAL

    @classmethod
    def prefix(cls) -> str:
        return f"{super().prefix()}:track"

    @classmethod
    def from_serial(cls, serial: str) -> TrackID | None:
        """Load from a serial string (``<service>:track:<payload>``).

        This is a convenience method to parse a serial string into the correct
        subclass of :class:`TrackID` for the service. Returns ``None`` if the
        service is not available or no matching identifier class is found.
        """
        try:
            service_name = serial.split(":", 1)[0]
        except IndexError:
            log.warning(f"Invalid track serial {serial!r}, cannot parse service name")
            return None

        # We have some global track identifiers that are not tied to a
        # specific service.
        global_service_identifier: dict[str, type[TrackID]] = {
            "isrc": ISRC,
            "file": FilePath,
        }
        if service_name in global_service_identifier:
            try:
                return global_service_identifier[service_name].parse(serial)
            except ValueError:
                log.warning(
                    f"Invalid global track identifier {serial!r} for"
                    f" service {service_name!r}"
                )
                return None

        service = ServiceLoader.get(service_name)
        if not service:
            log.warning(
                f"Service {service_name!r} not available for track serial {serial!r}"
            )
            return None

        for tid_cls in service.track_ids():
            # Check if prefix matches
            if tid_cls.prefix().startswith(service_name):
                try:
                    return tid_cls.parse(serial)
                except ValueError:
                    continue

        log.info(
            f"No track identifier class found for serial {serial!r}"
            f" in service {service_name!r}"
        )
        return None


# Commonly shared IDS


@dataclass(frozen=True)
class ISRC(TrackID, service="core"):
    """International Standard Recording Code.

    A standardized identifier intended to be globally unique for a recording.

    The ``id`` field is always normalised (uppercase, dashes stripped)
    regardless of how the instance is constructed.
    """

    id: str
    """The raw 12-character ISRC (e.g. ``USRC17607839``)."""

    def __init__(self, value: str) -> None:
        normalised = value.replace("-", "").upper()
        object.__setattr__(self, "id", normalised)

    @classmethod
    def prefix(cls) -> str:
        return "isrc"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (URL, URI, serial, or raw id).

        Accepts the raw 12-character ISRC, the serial format
        (``isrc:XXAAA0000000``), or the dashed format (``XX-AAA-00-00000``).
        """
        value = value.strip()
        if value.lower().startswith(cls.prefix()):
            value = value[len(cls.prefix()) + 1 :]
        # __init__ handles dash-stripping and uppercasing
        if not re.fullmatch(
            r"[A-Z]{2}[A-Z0-9]{3}\d{7}", value.replace("-", "").upper()
        ):
            raise ValueError(f"Invalid ISRC: {value!r}")
        return cls(value)

    @property
    def serial(self) -> str:
        """Plistsync's internal string-representation of ISRC."""
        return f"{self.prefix()}:{self.id}"

    def __str__(self) -> str:
        """Compact display (just the raw id)."""
        return self.id


@dataclass(frozen=True)
class FilePath(TrackID, service="core"):
    """File path identifier for local tracks.

    This is a simple wrapper around a file path, used to identify local tracks in a
    consistent way.
    """

    scope: ClassVar[Scope] = Scope.LOCAL

    path: PurePath
    """The filesystem path to the track file."""

    @classmethod
    def prefix(cls) -> str:
        return "file"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (raw path or serial ``file:...`` format)."""
        value = value.strip()
        if value.lower().startswith(cls.prefix()):
            value = value[len(cls.prefix()) + 1 :]
        return cls(PurePath(value))

    @property
    def serial(self) -> str:
        """Plistsync's internal string-representation of the file path."""
        return f"{self.prefix()}:{self.path.as_posix()}"

    def __str__(self) -> str:
        """Compact display (just the raw path string)."""
        return str(self.path)
