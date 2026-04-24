import re
from pathlib import PurePath, PurePosixPath, PureWindowsPath
from typing import Literal, Self

from lxml.etree import Element, SubElement, _Element


class NMLPath:
    """OS-agnostik representation of a File Path in Traktor.

    Follows the logic in NML Playlists: volume/:directory/:file
    """

    _parts: list[str]

    # We treat volume id as optional, and use the volume by default
    # Should only be changed through our location helpers
    _volume_id: str | None

    def __init__(self, path: str):
        """Construct a TraktorPath from a Traktor-style path string.

        As used by Traktors NML files in the playlist section: volume/:directory/:file
        """
        if path.count("/:") < 1:
            raise ValueError(
                f"Invalid Traktor path: {path}, follow schema volume/:directory/:file"
            )
        self._parts = [p for p in path.split("/:") if p]
        self._volume_id = None

    @property
    def volume(self) -> str:
        return self._parts[0]

    @property
    def volume_id(self) -> str | None:
        if self._volume_id is not None:
            return self._volume_id
        return self.volume

    @property
    def directories(self) -> str:
        if len(self._parts) <= 2:
            return "/:"
        return "/:" + "/:".join(self._parts[1:-1]) + "/:"

    @property
    def parts(self) -> list[str]:
        return self._parts

    @property
    def file(self) -> str:
        return self._parts[-1]

    @property
    def os(self) -> Literal["macos", "windows"]:
        if re.match(r"^[A-Za-z]:$", self.volume):
            return "windows"
        return "macos"

    @classmethod
    def from_nml_location(cls, loc: _Element) -> Self:
        """Create a TraktorPath from a NML LOCATION element.

        Example:

        ```xml
        <LOCATION
            DIR="/:clean/:3 Doors Down/:3 Doors Down/:"
            FILE="03 It's Not My Time [278kbps].mp3"
            VOLUME="Traktor" | VOLUME="C:"
            VOLUMEID="asdasda123"
        ></LOCATION>
        ```
        """
        vol = loc.get("VOLUME")
        dir = loc.get("DIR")
        file = loc.get("FILE")
        volid = loc.get("VOLUMEID", None)

        if dir is None or file is None or vol is None:
            raise ValueError("Could not find DIR, FILE or VOLUME in NML LOCATION entry")

        dir_parts = [p for p in dir.split("/:") if p]
        tp = cls("/:".join([vol, *dir_parts, file]))
        tp._volume_id = volid

        return tp

    def to_nml_location(self, parent: _Element | None = None) -> _Element:
        """
        Create a <LOCATION> element from this NMLPath.

        If `parent` is provided, appends LOCATION to parent.
        Otherwise returns a standalone LOCATION element.
        """
        if parent is None:
            location = Element("LOCATION")
        else:
            location = SubElement(parent, "LOCATION")

        location.set("DIR", self.directories)
        location.set("FILE", self.file)
        location.set("VOLUME", self.volume)
        location.set("VOLUMEID", self.volume_id or self.volume)
        return location

    @classmethod
    def from_path(cls, path: str | PurePath) -> Self:
        """Create a TraktorPath from a filesystem path.

        Provided paths must be absolute and contain the volume name:

        ```
        # Windows
        C:/Users/paul/Music/file.flac

        # macOS
        /Volumes/Macintosh HD/Users/paul/Music/file.flac
        ```
        """
        # Resolve UNC paths ... we might have to revisit this once we get complains
        # form windows users.
        path = str(path).replace("\\", "/")

        if not path.startswith("/"):
            # Windows
            if not re.match(r"^[A-Za-z]:/", path):
                raise ValueError(
                    "Path looks like a windows path (does not start with / ) but "
                    f"has an unexpected drive letter ({path})"
                )
        else:
            # MacOS
            if not path.startswith("/Volumes/"):
                raise ValueError(
                    "Path looks like a macOS path (starts with / ) but "
                    f"does not start with /Volumes ({path})"
                )
            # Remove /Volumes prefix
            path = path[len("/Volumes/") :]

        return cls(path.replace("/", "/:"))

    @property
    def pure_path(self) -> PureWindowsPath | PurePosixPath:
        """Convert the TraktorPath back to a (pure) filesystem Path."""

        if self.os == "macos":
            return PurePosixPath("/Volumes/" + "/".join(self._parts))
        else:
            return PureWindowsPath("/".join(self._parts))

    def __str__(self) -> str:
        return "/:".join(self._parts)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(path={str(self)!r})"

    def __eq__(self, value: object) -> bool:
        """
        Check tracks are the same.

        Currently not comparing volume ids.
        """
        if not isinstance(value, NMLPath):
            return False
        return str(self) == str(value)
