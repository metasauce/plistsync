from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Literal, NamedTuple, Self

from lxml.etree import Element, SubElement

from plistsync.core import GlobalTrackIDs, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo
from plistsync.logger import log

if TYPE_CHECKING:
    from lxml.etree import _Element

    from .collection import NMLCollection


class NMLTrack(Track):
    """A track in an NML collection (library).

    ```
    # macOS
    <ENTRY
        MODIFIED_DATE="2024/5/27"
        MODIFIED_TIME="11734"
        AUDIO_ID="API...AAA=="
        TITLE="It’s Not My Time"
        ARTIST="3 Doors Down"
    >
        <LOCATION
            DIR="/:clean/:3 Doors Down/:3 Doors Down/:"
            FILE="03 It's Not My Time [278kbps].mp3"
            VOLUME="Traktor"
            VOLUMEID="Traktor"
        ></LOCATION>
        <ALBUM OF_TRACKS="12" TRACK="3" TITLE="3 Doors Down"></ALBUM>
        <MODIFICATION_INFO AUTHOR_TYPE="user"></MODIFICATION_INFO>
        <INFO BITRATE="279000" ...></INFO>
        <TEMPO BPM="128.005371" BPM_QUALITY="100.000000"></TEMPO>
        <LOUDNESS ...></LOUDNESS>
        <MUSICAL_KEY VALUE="21"></MUSICAL_KEY>
        <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="4" START="1536.363840" LEN="0.000000" REPEATS="-1" HOTCUE="-1">
            <GRID BPM="128.005371"></GRID>
        </CUE_V2>
        <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="0" START="1536.363840" LEN="0.000000" REPEATS="-1" HOTCUE="0" COLOR="#FFFFFF"></CUE_V2>
    </ENTRY>
    ```
    """

    entry: _Element

    def __init__(self, entry: _Element):
        self.entry = entry

    @property
    def traktor_path(self):
        loc = self.entry.find("LOCATION")
        if loc is None:
            raise ValueError("Could not find LOCATION in NML entry")

        vol = loc.get("VOLUME")
        dir = loc.get("DIR")
        file = loc.get("FILE")

        return vol, dir, file

    @property
    def path(self) -> Path:
        loc = self.entry.find("LOCATION")
        if loc is None:
            raise ValueError("Could not find LOCATION in NML entry")

        vol = loc.get("VOLUME")
        dir = loc.get("DIR")
        file = loc.get("FILE")

        if dir is None or file is None:
            raise ValueError("Could not find DIR or FILE in NML LOCATION entry")

        dir = _traktor_to_path(dir)

        return Path(vol) / Path(dir) / file

    @property
    def traktor_id(self) -> str:
        """Traktor's internal audio ID for the track."""
        tid = self.entry.get("AUDIO_ID")
        if tid is None:
            # this should not happen.
            raise ValueError("Could not find AUDIO_ID in NML entry.")
        return tid

    # ------------------------------- Contracts ------------------------------ #

    @property
    def global_ids(self) -> GlobalTrackIDs:
        """Sadly no unique identifier in NML files.
        There exists an audio_id, but no idea how to use it or what it is.
        """  # noqa: D205
        return GlobalTrackIDs()

    @property
    def local_ids(self) -> LocalTrackIDs:
        return LocalTrackIDs(
            file_path=self.path,
        )

    @property
    def info(self) -> TrackInfo:
        info = TrackInfo()

        title = self.entry.get("TITLE")
        if title is not None:
            info["title"] = title

        # Only has one artist
        artists = self.entry.get("ARTIST")
        if artists is not None:
            # TODO: heuristic, we split at semicolons and commas, should be configurable.
            info["artists"] = [a for a in re.split(r"[,;]", artists) if a != ""]

        album = self.entry.find("ALBUM")
        if album is not None:
            album_title = album.get("TITLE")
            if album_title is not None:
                info["albums"] = [album_title]

        return info


class NMLPlaylistTrack(Track):
    """A track in an NML playlist.

    Tracks in Playlists are stored differently than in the main collection,
    and they only hold the file path. And do not need to exists in the
    main collection.

    ```
    # macOS
    <ENTRY>
        <PRIMARYKEY TYPE="TRACK"
            KEY="vigsoe/:Users/:paul/:Music/:clean/:Dr. Apollo, Pesa One/:Culito/:01 Culito [950kbps].flac"></PRIMARYKEY>
    </ENTRY>
    # Windows
    <ENTRY>
        <PRIMARYKEY TYPE="TRACK"
            KEY="D:/:SYNC/:library/:QZB/:Delirium Ep/:01 Tech Priest [956kbps].flac"></PRIMARYKEY>
    </ENTRY>
    ```
    """

    entry: _Element

    def __init__(self, entry: _Element):
        """Initialize a NMLPlaylistTrack with an XML entry.

        Parameters
        ----------
        entry : _Element
            The XML entry for the track in the playlist, xml should look like this:


        """

        self.entry = entry

    @classmethod
    def from_traktor_path(cls, traktor_path: str) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack with underlying XML Entry from a Traktor path."""
        entry = Element("ENTRY")
        primary_key = SubElement(entry, "PRIMARYKEY")
        primary_key.set("TYPE", "TRACK")
        primary_key.set("KEY", traktor_path)
        return cls(entry)

    @classmethod
    def from_path(cls, path: Path) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack with underlying XML Entry from a path (i.e. to insert into an NML playlist)."""
        path = path.resolve()

        return cls.from_traktor_path(_path_to_traktor(path))

    @classmethod
    def from_track(cls, track: Track) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack with underlying XML Entry from any track with a path."""
        if track.path is None:
            raise ValueError(
                "Track does not have a path, cannot create NMLPlaylistTrack."
            )
        return cls.from_path(track.path)

    def to_nml_track(self, collection: NMLCollection) -> NMLTrack | None:
        """Convert this playlist track to a NMLTrack.

        This might fail if the track does not exist in the main collection.
        """
        return collection.find_by_traktor_path(self.traktor_path)

    @property
    def traktor_path(self) -> str:
        """The path to the track in Traktor format.

        In NML Playlists, the xml entry has the volume name as part of the path.
        This is inconsistent with the xml of the tracks location in the main lib,
        where the volume name is a separate field.
        """
        pkey = self.entry.find("PRIMARYKEY")
        if pkey is None:
            raise ValueError("Could not find PRIMARYKEY in NMLPlaylistTrack entry")
        key_value = pkey.get("KEY")
        if key_value is None:
            raise ValueError("Could not find KEY in PRIMARYKEY element")

        # Remove any chars before and including the first occurrence of '/:'
        processed_value = re.sub(r"^.*?/:", "", key_value, count=1)
        return processed_value

    @property
    def path(self) -> Path:
        """The path to the track file on disk."""
        return _traktor_to_path(self.traktor_path)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self.path}]"

    # ------------------------------- Contracts ------------------------------ #

    @property
    def global_ids(self) -> GlobalTrackIDs:
        """NMLPlaylistTrack does not have identifiers."""
        return GlobalTrackIDs()

    @property
    def local_ids(self) -> LocalTrackIDs:
        """NMLPlaylistTrack does not have identifiers."""
        return LocalTrackIDs(
            file_path=self.path,
        )

    @property
    def info(self) -> TrackInfo:
        info = TrackInfo()

        # PS 2025-08-23:
        # NMLPlaylistTrack does not have metadata, only path.
        # We _could_ get the data from the main collection, but since conversion
        # is so easy, I dont think its worth the added complexity.

        return info


class TraktorPath:
    # following the logic in NML **Playlists**: volume/:directory/:file
    _parts: list[str]

    def __init__(self, path: str):
        """Construct a TraktorPath from a Traktor-style path string.

        As used by Traktors NML files in the playlist section: volume/:directory/:file
        """
        if path.count("/:") < 1:
            raise ValueError(
                f"Invalid Traktor path: {path}, follow schema volume/:directory/:file"
            )
        self._parts = path.split("/:")

    @property
    def volume(self) -> str:
        return self._parts[0]

    @property
    def directories(self) -> str:
        if len(self._parts) <= 2:
            return "/:"
        return "/:".join(self._parts[1:-1])

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
    def from_path(cls, path: str | Path | PurePosixPath | PureWindowsPath) -> Self:
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
                    f"Path looks like a windows path (does not start with / ) but "
                    + f"has an unexpected drive letter ({path})"
                )
        else:
            # MacOS
            if not path.startswith("/Volumes/"):
                raise ValueError(
                    f"Path looks like a macOS path (starts with / ) but "
                    + f"does not start with /Volumes ({path})"
                )
            # Remove /Volumes prefix
            path = path[len("/Volumes/") :]

        return cls(path.replace("/", "/:"))

    @property
    def pure_path(self) -> PureWindowsPath | PurePosixPath:
        """Convert the TraktorPath back to a (pure) filesystem Path."""

        if self.os == "macos":
            return PurePosixPath("/Volumes", *self._parts)
        else:
            return PureWindowsPath(*self._parts)

    def __str__(self) -> str:
        return "/:".join(self._parts)

    def __repr__(self) -> str:
        return f"TraktorPath[{str(self)}, {hash(self)}]"
