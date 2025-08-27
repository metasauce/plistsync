from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Self

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


class TraktorPath(NamedTuple):
    volume: str
    directory: str
    file: str

    @classmethod
    def from_macos_path(cls, path: Path) -> TraktorPath:
        """
        Create a TraktorPath from a macOS file path.

        The default pattern we expect is `/Volumes/vol_name/dirs/file.ext`.
        """

        parts = path.parts # do not resolve - results are OS dependent!
        parts = parts[1:] # remove leading slash
        if parts[0] == "Users":
            # for convenience, allow paths without /Volumes prefix and use the root volume
            # this needs subprocess, cos no native python way. highly discouraged!
            volume = _find_macos_volume_name()
            if volume is not None:
                parts = ("Volumes", volume, *parts)
                log.warning(
                    "Had to infer macOS root volume. "
                    + f" for future calls, please prepend /Volumes/{volume}/"
                )
            else:
                raise ValueError(
                    "For macOS paths, please use the full path format, including the "
                    + "volume name. Likely /Volumes/Macintosh HD/dirs/file.ext"
                )

        if parts[0] != "Volumes" or len(parts) < 3:
            raise ValueError(f"Invalid path: {path} {parts}")

        volume = parts[1]
        directory = "/:".join(parts[2:-1])
        file = parts[-1]
        return cls(volume=volume, directory=directory, file=file)

    @classmethod
    def from_windows_path(cls, path: Path) -> TraktorPath:
        """
        Create a TraktorPath from a Windows file path.

        The default pattern we expect is `C:/dirs/file.ext`.
        """
        parts = path.parts # do not resolve - results are OS dependent!
        if len(parts) < 3:
            raise ValueError(f"Invalid path: {path} {parts}")

        volume = parts[0]
        directory = "/:".join(parts[1:-1])
        file = parts[-1]
        return cls(volume=volume, directory=directory, file=file)

    def to_path(self) -> Path:
        # also needs windows vs macos distinction -.-
        """Convert the TraktorPath back to a filesystem Path."""
        parts = [self.volume] + self.directory.split("/:") + [self.file]
        return Path(*parts)

def _find_macos_volume_name() -> str | None:
    try:
        cmd = ["diskutil", "info", "/", ]
        output = subprocess.check_output(cmd, text=True)
        for line in output.splitlines():
            if "Volume Name:" in line:
                return line.split(":", 1)[1].strip()
    except Exception as e:
        return None


def _path_to_traktor(path: Path) -> str:
    """Convert a Path to a Traktor path format."""
    return str(path.resolve()).lstrip("/").replace("/", "/:")


def _traktor_to_path(traktor_path: str) -> Path:
    """Convert a Traktor path format to a Path."""
    return Path(traktor_path.replace("/:", "/"))
