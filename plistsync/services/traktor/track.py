from __future__ import annotations

import re
from pathlib import PurePath
from typing import TYPE_CHECKING

from lxml.etree import Element, SubElement

from plistsync.core import GlobalTrackIDs, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo

from .path import NMLPath

if TYPE_CHECKING:
    from lxml.etree import _Element

    from .library import NMLLibraryCollection


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
        <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="4" START="1536.363840"
        LEN="0.000000" REPEATS="-1" HOTCUE="-1">
            <GRID BPM="128.005371"></GRID>
        </CUE_V2>
        <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="0" START="1536.363840"
        LEN="0.000000" REPEATS="-1" HOTCUE="0" COLOR="#FFFFFF"></CUE_V2>
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
    def path(self) -> PurePath:
        loc = self.entry.find("LOCATION")
        if loc is None:
            raise ValueError("Could not find LOCATION in NML entry")

        return NMLPath.from_nml_location(loc).pure_path

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
            # TODO: heuristic, we split at semicolons and commas, should be configurable
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
    and they only hold the file path. And do not need to exist in the
    main collection. Traktor will add them to the collection if "checking consistency",
    but it will also remove tracks from a playlist if they are neither found on disk nor
    in the main collection.

    ```
    # macOS
    <ENTRY>
        <PRIMARYKEY TYPE="TRACK"
            KEY="vigsoe/:Users/:paul/:Music/:clean/:Dr. Apollo, Pesa One/:Culito/:01
            Culito [950kbps].flac"></PRIMARYKEY>
    </ENTRY>

    # Windows
    <ENTRY>
        <PRIMARYKEY TYPE="TRACK"
            KEY="D:/:SYNC/:library/:QZB/:Delirium Ep/:01 Tech Priest [956kbps].flac">
        </PRIMARYKEY>
    </ENTRY>
    ```
    """

    entry: _Element

    def __init__(self, entry: _Element):
        """Initialize a NMLPlaylistTrack with an XML entry.

        Parameters
        ----------
        entry : _Element
            The XML entry for the track in the playlist
        """

        self.entry = entry

    @classmethod
    def from_traktor_path(cls, traktor_path: NMLPath) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack with underlying XML Entry from a Traktor path."""
        entry = Element("ENTRY")
        primary_key = SubElement(entry, "PRIMARYKEY")
        primary_key.set("TYPE", "TRACK")
        primary_key.set("KEY", str(traktor_path))
        return cls(entry)

    @classmethod
    def from_path(cls, path: PurePath) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack with underlying XML Entry from a path.

        This path must be absolute and contain the volume name see also
        :py:func:`TraktorPath.from_path`
        Avoid using path.resolve(), as it might break depending on the OS.
        """
        return cls.from_traktor_path(NMLPath.from_path(path))

    @classmethod
    def from_track(cls, track: Track) -> NMLPlaylistTrack:
        """Create a NMLPlaylistTrack.

        Includes underlying XML Entry from any
        track with a path.
        """
        if track.path is None:
            raise ValueError(
                "Track does not have a path, cannot create NMLPlaylistTrack."
            )
        return cls.from_path(track.path)

    def to_nml_track(self, collection: NMLLibraryCollection) -> NMLTrack | None:
        """Convert this playlist track to a NMLTrack.

        This might fail if the track does not exist in the main collection.
        """
        return collection.find_by_traktor_path(self.traktor_path)

    @property
    def traktor_path(self) -> NMLPath:
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

        return NMLPath(key_value)

    @property
    def path(self) -> PurePath:
        """The path to the track file on disk."""
        return self.traktor_path.pure_path

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
