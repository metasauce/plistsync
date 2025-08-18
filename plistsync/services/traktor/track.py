from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Self

from lxml.etree import Element, SubElement

from plistsync.core import Track, GlobalTrackIDs

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
    def title(self) -> str:
        return self.entry.get("TITLE", "")

    @property
    def artists(self) -> list[str]:
        # Only has one artist
        artists = self.entry.get("ARTIST", "")
        return [a for a in re.split(r"[,;]", artists) if a != ""]

    @property
    def albums(self) -> list[str]:
        album = self.entry.find(
            "ALBUM",
        )
        if album is None:
            return []

        title = album.get("TITLE", "")
        return [title] if title != "" else []

    @property
    def global_ids(self) -> GlobalTrackIDs:
        """Sadly no unique identifier in NML files.
        There exists an audio_id, but no idea how to use it or what it is.
        """  # noqa: D205
        return GlobalTrackIDs()

    def serialize(self) -> dict:
        return {
            "entry": self.entry,
        }

    @classmethod
    def deserialize(cls, data: dict) -> Self:
        return cls(data["entry"])

    @property
    def path(self) -> Path:
        loc = self.entry.find("LOCATION")
        if loc is None:
            raise ValueError("Could not find LOCATION in NML entry")

        dir = loc.get("DIR")
        file = loc.get("FILE")

        if dir is None or file is None:
            raise ValueError("Could not find DIR or FILE in NML LOCATION entry")

        # Clean up the DIR path (remove trailing colons and slashes)
        dir = dir.rstrip(":").rstrip("/")

        # Replace colons with slashes to create a valid path
        dir = dir.replace(":", "/")

        return Path(dir) / file


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
        return cls.from_path(track.path)

    def to_nml_track(self, collection: NMLCollection) -> NMLTrack | None:
        """Convert this playlist track to a NMLTrack.

        This might fail if the track does not exist in the main collection.
        """
        return collection.find_by_traktor_path(self.traktor_path)

    @property
    def traktor_path(self) -> str:
        """The path to the track in Traktor format.

        This is the same as the path property, but with the leading slash removed
        and colons replaced with slashes, to account for Traktor's path format.
        """
        pkey = self.entry.find("PRIMARYKEY")
        if pkey is None:
            raise ValueError("Could not find PRIMARYKEY in NMLPlaylistTrack entry")
        key_value = pkey.get("KEY")
        if key_value is None:
            raise ValueError("Could not find KEY in PRIMARYKEY element")
        return key_value

    @property
    def path(self) -> Path:
        """The path to the track file on disk."""
        return _traktor_to_path(self.traktor_path)

    # methods we need to implement

    @property
    def title(self) -> str:
        raise NotImplementedError("NMLPlaylistTrack does not have a title property")

    @property
    def artists(self) -> list[str]:
        return []

    @property
    def albums(self) -> list[str]:
        return []

    @property
    def global_ids(self) -> GlobalTrackIDs:
        """NMLPlaylistTrack does not have identifiers."""
        return GlobalTrackIDs()

    def serialize(self) -> dict:
        raise NotImplementedError()

    @classmethod
    def deserialize(cls, data: dict) -> Self:
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self.path}]"


def _path_to_traktor(path: Path) -> str:
    """Convert a Path to a Traktor path format."""
    return str(path.resolve()).lstrip("/").replace("/", "/:")


def _traktor_to_path(traktor_path: str) -> Path:
    """Convert a Traktor path format to a Path."""
    p = Path(traktor_path.replace("/:", "/"))
    if not p.is_absolute():
        p = Path("/") / p
    return p.resolve()
