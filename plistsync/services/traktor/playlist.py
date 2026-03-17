from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from lxml.etree import Element, SubElement, _Element

from plistsync.core.collection import LocalLookup
from plistsync.core.playlist import (
    PlaylistCollection,
    PlaylistInfo,
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


class NMLPlaylistCollection(PlaylistCollection[NMLPlaylistTrack], LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library: NMLLibraryCollection

    # Root node to the playlist (not necessarly attached to the library)
    root_node: _Element  # <Node TYPE="PLAYLIST">

    def __init__(
        self,
        library: NMLLibraryCollection | str | Path,
        name: str | _Element,
    ):
        """Initialize the NMLPlaylistCollection.

        Parameter
        ---------
        library_collection : NMLCollection | str | Path
            The root collection from which the playlists are derived.
        name : str | _Element
            The name of the playlist to create. If root node is given,
            as _Element it is used.
        """

        if isinstance(library, (str, Path)):
            from .library import NMLLibraryCollection

            self.library = NMLLibraryCollection(library)
        else:
            self.library = library

        if isinstance(name, str):
            s_name = sanitize_plist_name(name)
            if s_name != name:
                log.warning(
                    f"Playlist name changed from `{name}` to `{s_name}`"
                    " to avoid issues with Traktor.",
                )
            root_node = self._create_playlist_node(s_name)
        else:
            # Use node directly
            root_node = name

        self.root_node = root_node

    @staticmethod
    def _create_playlist_node(name: str) -> _Element:
        """Create a new playlist root node."""
        root_node = Element("NODE", {"TYPE": "PLAYLIST"})
        root_node.set("NAME", name)
        # Add <Playlist> list node
        node = SubElement(root_node, "PLAYLIST")
        node.set("TYPE", "LIST")
        node.set("UUID", uuid4().hex)
        node.set("ENTRIES", "0 ")
        root_node.append(node)
        return root_node

    # ----------------------- Properties and info logic ---------------------- #

    @property
    def playlist_node(self) -> _Element:
        node = self.root_node.find("PLAYLIST")
        if node is not None:
            return node
        raise ValueError("Root node has no 'PLAYLIST' node")

    @property
    def info(self) -> PlaylistInfo:
        return PlaylistInfo(
            name=self.root_node.get("NAME", ""),
        )

    @info.setter
    def info(self, value: PlaylistInfo):
        self.root_node.set("NAME", value.get("name", ""))

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

    # ------------------------------ Tracks Loading ------------------------------ #

    def _fetch_tracks(self):
        entries = self.playlist_node.xpath(".//ENTRY/PRIMARYKEY[@TYPE='TRACK']/..")
        self._tracks = [NMLPlaylistTrack(entry) for entry in entries]

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

    @property
    def tracks(self) -> list[NMLPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            self._fetch_tracks()
        return self._tracks  # type: ignore[return-value]

    @tracks.setter
    def tracks(self, value: list[NMLPlaylistTrack]):
        self._tracks = value

    def __len__(self) -> int:
        """Get the number of tracks in the playlist."""
        entries = self.playlist_node.get("ENTRIES", "0")
        return int(entries) if entries.isdigit() else 0

    # ----------------------------- Remote operations ---------------------------- #
    # Remote methods are not really needed as we just replace the playlist
    # node in the library

    def _remote_edit(
        self,
        before: Snapshot[NMLPlaylistTrack],
        after: Snapshot[NMLPlaylistTrack],
    ) -> None:
        """Wrap apply diff so `edit`."""

        self._overwrite_track_entries(after.tracks)
        self.remote_upsert()

    def _remote_create(self):
        """Create the playlist in the nml collection.

        Will recreate the playlist even if it exsits
        """

        # Insert under playlists root
        subnodes = self.library.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )
        if len(subnodes) == 0:
            raise ValueError("Could not find SUBNODES in $ROOT folder in NML file")
        subnodes_el = subnodes[0]

        detach(self.root_node)
        subnodes_el.append(self.root_node)

        # Increment count
        count_raw = subnodes_el.get("COUNT", "0")
        try:
            count = int(count_raw)
        except ValueError:
            log.warning(f"Invalid SUBNODES COUNT value: {count_raw!r}, treating as 0")
            count = 0
        subnodes_el.set("COUNT", str(count + 1))

    @property
    def remote_associated(self) -> bool:
        root_node = self.library._get_playlist_root_node_by_uuid(self.uuid)
        if root_node is None:
            return False
        return True

    def remote_upsert(self):
        """Insert or replace a playlist node in this NML library.

        - Prefer matching by UUID (stable identity)
        - Otherwise append under $ROOT/SUBNODES

        This updates the in-memory XML tree only. Call .write() to persist.
        """

        try:
            matching_node = self.library._get_playlist_root_node_by_uuid(self.uuid)
        except ValueError:
            matching_node = None

        if matching_node is not None:
            parent = matching_node.getparent()
            if parent is None:
                raise ValueError("Existing playlist node has no parent; cannot replace")

            # Remove the existing node
            # and replace with new playlist root node
            pos = parent.index(matching_node)
            detach(self.root_node)
            if self.root_node != matching_node:
                parent.remove(matching_node)
            parent.insert(pos, self.root_node)
        else:
            self._remote_create()

    def _remote_delete(self):
        """Remove in connected collection."""
        detach(self.root_node)

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
