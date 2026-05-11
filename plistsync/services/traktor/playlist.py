from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID, uuid4

from lxml.etree import Element, SubElement, _Element

from plistsync.core.collection import LocalLookup
from plistsync.core.playlist import (
    PlaylistID,
    PlaylistInfo,
    ServicePlaylist,
    Snapshot,
)
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log

from .path import NMLPath
from .track import NMLPlaylistTrack, NMLTrack
from .utility import (
    detach,
    sanitize_plist_name,
    xpath_string_escape,
)

if TYPE_CHECKING:
    from .library import NMLLibrary


@dataclass(frozen=True)
class NMLPlaylistID(PlaylistID):
    service_name: ClassVar[str] = "traktor"
    id: UUID  # uuid

    @classmethod
    def parse(cls, value: str | UUID) -> NMLPlaylistID:
        """Parse from UUID, NML URI, or Traktor export formats."""

        if isinstance(value, UUID):
            return cls(value)

        value = str(value).strip()

        # direct UUID validation (strict)
        try:
            return cls(UUID(value))
        except (ValueError, AttributeError):
            pass

        # known URI formats
        if m := re.search(
            r"(?:nml:playlist:|traktor:playlist:)([0-9a-fA-F-]{36})", value
        ):
            try:
                return cls(UUID(m.group(1)))
            except ValueError:
                pass

        # XML / export formats
        if m := re.search(r"uuid=['\"]([0-9a-fA-F-]{36})['\"]", value):
            try:
                return cls(UUID(m.group(1)))
            except ValueError:
                pass

        raise ValueError(f"Invalid Traktor/NML playlist ID: {value!r}")

    @property
    def serial(self) -> str:
        """Canonical Traktor URI."""
        return f"traktor:playlist:{self.id.hex}"

    def __str__(self) -> str:
        return str(self.id.hex)  # Uses hex in internal repr


class NMLPlaylist(ServicePlaylist[NMLPlaylistTrack], LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library: NMLLibrary

    # Root node to the playlist (should always be attached to the library)
    root_node: _Element  # <Node TYPE="PLAYLIST">

    _tracks: list[NMLPlaylistTrack] | None = None

    def __init__(
        self,
        library: NMLLibrary,
        root_node: _Element,
    ):
        """Create a new instance of a traktor playlist given its xml element."""
        self.library = library
        self.root_node = root_node

    @staticmethod
    def _create_root_node(name: str) -> _Element:
        """Create a new playlist root node."""
        s_name = sanitize_plist_name(name)
        if s_name != name:
            log.warning(
                f"Playlist name changed from `{name}` to `{s_name}`"
                " to avoid issues with Traktor.",
            )
        root_node = Element("NODE", {"TYPE": "PLAYLIST"})
        root_node.set("NAME", s_name)
        # Add <Playlist> list node
        node = SubElement(root_node, "PLAYLIST")
        node.set("TYPE", "LIST")
        node.set("UUID", uuid4().hex)
        node.set("ENTRIES", "0 ")
        root_node.append(node)
        return root_node

    @property
    def playlist_node(self) -> _Element:
        node = self.root_node.find("PLAYLIST")
        if node is not None:
            return node
        raise ValueError("Root node has no 'PLAYLIST' node")

    # ----------------------- Required (Playlist protocol) ----------------------- #

    @property
    def info(self) -> PlaylistInfo:
        return PlaylistInfo(
            name=self.root_node.get("NAME", ""),
        )

    @info.setter
    def info(self, value: PlaylistInfo):
        self.root_node.set("NAME", value.get("name", ""))

    @property
    def tracks(self) -> list[NMLPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            return self._fetch_tracks()
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[NMLPlaylistTrack] | Sequence[NMLTrack]):
        def convert(t: NMLPlaylistTrack | NMLTrack):
            # convert tracks to playlist tracks
            if isinstance(t, NMLPlaylistTrack):
                return t
            else:
                return NMLPlaylistTrack.from_track(t)

        self._tracks = list(map(convert, value))

    @property
    def id(self) -> NMLPlaylistID:
        """Unique identifiers of the playlist."""
        return NMLPlaylistID.parse(self.uuid)

    @property
    def uuid(self) -> str:
        """Get the uuid of the playlist."""
        uuid = self.playlist_node.get("UUID", None)
        if uuid is None:
            uuid = uuid4().hex
            self.uuid = uuid
        return uuid

    @uuid.setter
    def uuid(self, value: str) -> None:
        """Set the uuid of the playlist."""
        self.playlist_node.set("UUID", value)

    # -------------------- Required (ServicePlaylist protocol) ------------------- #

    def _remote_delete(self):
        """Remove in connected collection."""
        detach(self.root_node)

    def _remote_commit(
        self,
        before: Snapshot[NMLPlaylistTrack],
        after: Snapshot[NMLPlaylistTrack],
    ) -> None:
        """Persist current state to nml."""

        self._overwrite_track_entries(after.tracks)

    def _overwrite_track_entries(self, tracks: list[NMLPlaylistTrack]) -> None:
        """Rewrite the <ENTRY> list in the underlying XML to match `tracks`."""
        # Remove existing entries
        for entry in list(self.playlist_node.findall("ENTRY")):
            self.playlist_node.remove(entry)

        # Append new entries (avoid reusing Elements that may already have parents)
        for track in tracks:
            self.playlist_node.append(
                NMLPlaylistTrack.from_traktor_path(track.traktor_path).entry
            )
            if self.library.find_by_traktor_path(track.traktor_path) is None:
                self.library.insert_track(track)

        self.playlist_node.set("ENTRIES", str(len(tracks)))

    # ---------------------------- Track lazy loading ---------------------------- #

    def _fetch_tracks(self):
        entries = self.playlist_node.xpath(".//ENTRY/PRIMARYKEY[@TYPE='TRACK']/..")
        self._tracks = [NMLPlaylistTrack(entry) for entry in entries]
        return self._tracks

    # --------------------------- LocalLookup protocol --------------------------- #

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> NMLPlaylistTrack | None:
        """Find a track by its local IDs.

        Note
        -----
        We only support lookup by file_path here. Other local ids are ignored.

        Parameter
        ---------
        local_ids : LocalTrackIDs
        """
        if file_path := local_ids.get("file_path"):
            # If the file_path is set, we can use it to find the track
            return self.find_by_traktor_path(NMLPath.from_path(file_path))
        return None

    def find_by_traktor_path(self, traktor_path: NMLPath) -> NMLPlaylistTrack | None:
        """Find a track by its file path.

        Parameter
        ---------
        path : str
            The file path of the track to find. This should be the full path including
            the filename. In traktor notation /:foo/:bar.mp3. If a volume is specified,
            it should will be ignored for the search.
        """

        entries = self.playlist_node.xpath(
            f".//ENTRY/PRIMARYKEY[@TYPE='TRACK'][@KEY={xpath_string_escape(str(traktor_path))}]/.."
        )
        if len(entries) == 0:
            return None
        elif len(entries) > 1:
            log.warning(
                f"Found duplicate entries for path '{traktor_path}' in playlist"
                ", using first one."
            )

        return NMLPlaylistTrack(entries[0])
