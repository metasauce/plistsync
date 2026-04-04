from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from lxml.etree import Element, SubElement, _Element

from plistsync.core.collection import LocalLookup
from plistsync.core.playlist import (
    PlaylistIDs,
    PlaylistInfo,
    ServicePlaylist,
    Snapshot,
)
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log

from .path import NMLPath
from .track import NMLPlaylistTrack
from .utility import (
    detach,
    sanitize_plist_name,
    xpath_string_escape,
)

if TYPE_CHECKING:
    from .library import NMLLibraryCollection


class NMLPlaylistCollection(ServicePlaylist[NMLPlaylistTrack], LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library: NMLLibraryCollection

    # Root node to the playlist (should always be attached to the library)
    root_node: _Element  # <Node TYPE="PLAYLIST">

    _tracks: list[NMLPlaylistTrack] | None = None

    def __init__(
        self,
        library: NMLLibraryCollection,
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
    def tracks(self, value: list[NMLPlaylistTrack]):
        self._tracks = value

    @property
    def ids(self) -> PlaylistIDs:
        """Unique identifiers of the playlist."""
        return PlaylistIDs(traktor_id=self.uuid)

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

    @classmethod
    def create_new(
        cls,
        name: str,
        description: str | None = None,
        tracks: list[NMLPlaylistTrack] | None = None,
        library: NMLLibraryCollection | None = None,
    ):
        if library is None:
            library = NMLLibraryCollection()

        root_node = cls._create_root_node(name)

        # Insert under playlists root
        subnodes = library.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )
        if len(subnodes) == 0:
            raise ValueError("Could not find SUBNODES in $ROOT folder in NML file")
        subnodes_el = subnodes[0]
        subnodes_el.append(root_node)

        # Increment count in library
        count_raw = subnodes_el.get("COUNT", "0")
        try:
            count = int(count_raw)
        except ValueError:
            log.warning(f"Invalid SUBNODES COUNT value: {count_raw!r}, treating as 0")
            count = 0
        subnodes_el.set("COUNT", str(count + 1))

        pl = cls(library, root_node)

        with pl.remote_edit():
            # Description not supported
            # pl.description = description
            if tracks:
                pl.tracks = tracks

        return pl

    @classmethod
    def get_by_ids(
        cls,
        ids: PlaylistIDs,
        library: NMLLibraryCollection | None = None,
    ):
        if library is None:
            library = NMLLibraryCollection()

        if ids and (traktor_id := ids.get("traktor_id")):
            maybe_root_node = library._get_playlist_root_node_by_uuid(traktor_id)
            if maybe_root_node is not None:
                return cls(
                    library,
                    maybe_root_node,
                )

        raise ValueError("Playlist not found!")

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
