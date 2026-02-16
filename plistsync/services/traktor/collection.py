from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, overload
from uuid import uuid4

from lxml import etree
from lxml.etree import Element, SubElement, _Element

from plistsync.core.collection import LibraryCollection, LocalLookup, TrackStream
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo, Snapshot
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log

from .track import NMLPlaylistTrack, NMLTrack, TraktorPath

if TYPE_CHECKING:
    from lxml.etree import _ElementTree


def xpath_string_escape(input_str: str) -> str:
    """Create a concatenation of alternately-quoted strings.

    This is always a valid XPath expression.
    see https://stackoverflow.com/questions/57639667/how-to-deal-with-single-and-double-quotes-in-xpath-in-python
    """
    if "'" not in input_str:
        return f"'{input_str}'"
    parts = input_str.split("'")
    return "concat('" + "', \"'\" , '".join(parts) + "', '')"


class NMLCollection(LibraryCollection, TrackStream, LocalLookup):
    """A Traktor NML collection.

    Allows to parse and interact with a Traktor NML file. I.e. traktor export playlist

    Sadly nml files do not contain unique identifiers for tracks, thus we need to
    iterate over all tracks to find a match. Might be less efficient than other
    collections.
    """

    path: Path
    tree: _ElementTree

    def __init__(self, path: Path | str):
        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"File {path} does not exist")

        self.path = Path(path)

        # An NML file is a XML file
        self.tree = etree.parse(self.path)

    def write(self):
        """Write the changes back to the NML file."""
        self.tree.write(
            self.path,
            encoding="utf-8",
            xml_declaration=True,
            standalone=False,
        )
        log.debug(f"Written collection changes to '{self.path}'")

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[NMLPlaylistCollection]:
        """Get all playlists in the NML file as NMLPlaylistCollection objects."""
        for node in self._playlist_nodes():
            pl = NMLPlaylistCollection(self, node)
            if pl.name.startswith("_"):
                continue
            yield pl

    @overload
    def get_playlist(self, *, name: str) -> NMLPlaylistCollection: ...

    @overload
    def get_playlist(self, *, uuid: str) -> NMLPlaylistCollection: ...

    def get_playlist(
        self,
        name: str | None = None,
        uuid: str | None = None,
        # path: str | Path | None = None,
    ) -> NMLPlaylistCollection:
        """Get a specific playlist.

        One of the kwargs must be given. Either search
        by name or get by uuid.

        Will raise if not found!
        """
        if sum(arg is not None for arg in [name, uuid]) != 1:
            raise ValueError("Exactly one of name or uuid must be provided")

        root_node: _Element | None = None

        if uuid is not None:
            root_node = self._get_playlist_root_node_by_uuid(uuid)
        else:
            root_node = self._get_playlist_root_node_by_name(name)  # type: ignore[arg-type]

        return NMLPlaylistCollection(self, root_node)

    def _playlist_nodes(self) -> Iterable[_Element]:
        """Get all playlists in the NML file."""
        nodes = self.tree.xpath(".//NODE[@TYPE='PLAYLIST']")
        return nodes

    def _get_playlist_root_node_by_uuid(self, uuid: str) -> _Element:
        """Get a playlist by uuid."""

        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST']/*[@UUID={xpath_string_escape(uuid)}]/.."
        )
        if len(node) > 0:
            return node[0]
        else:
            raise ValueError(f"Playlist '{uuid}' not found!")

    def _get_playlist_root_node_by_name(self, name: str) -> _Element:
        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST'][@NAME={xpath_string_escape(name)}]"
        )
        if len(node) > 0:
            return node[0]
        else:
            raise ValueError(f"Playlist '{name}' not found!")

    def upsert_playlist(self, playlist: NMLPlaylistCollection) -> None:
        """Insert or replace a playlist node in this NML library.

        - Prefer matching by UUID (stable identity)
        - Otherwise append under $ROOT/SUBNODES

        This updates the in-memory XML tree only. Call .write() to persist.
        """
        # Ensure playlist is associated with this library instance
        playlist.library = self

        def _detach(node: _Element) -> None:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)

        try:
            matching_node = self._get_playlist_root_node_by_uuid(playlist.uuid)
        except ValueError:
            matching_node = None

        if matching_node is not None:
            parent = matching_node.getparent()
            if parent is None:
                raise ValueError("Existing playlist node has no parent; cannot replace")

            # Remove the existing node
            # and replace with new playlist root node
            pos = parent.index(matching_node)
            _detach(playlist.root_node)
            if playlist.root_node != matching_node:
                parent.remove(matching_node)
            parent.insert(pos, playlist.root_node)
            return

        # Insert under root
        subnodes = self.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )
        if len(subnodes) == 0:
            raise ValueError("Could not find SUBNODES in $ROOT folder in NML file")

        _detach(playlist.root_node)
        subnodes_el = subnodes[0]
        subnodes_el.append(playlist.root_node)

        count_raw = subnodes_el.get("COUNT", "0")
        try:
            count = int(count_raw)
        except ValueError:
            log.warning(f"Invalid SUBNODES COUNT value: {count_raw!r}, treating as 0")
            count = 0
        subnodes_el.set("COUNT", str(count + 1))

    # --------------------------- LocalLookup protocol --------------------------- #

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> NMLTrack | None:
        """Find a track by its local IDs.

        We only support lookup by path here.
        """
        if file_path := local_ids.get("file_path"):
            return self.find_by_traktor_path(TraktorPath.from_path(file_path))

        return None

    def find_by_traktor_path(self, traktor_path: TraktorPath) -> NMLTrack | None:
        """Find a track by its file path.

        Parameter
        ---------
        traktor_path : TraktorPath
            The file path of the track to find. This should be the full path including
            the filename. In traktor notation /:foo/:bar.mp3. If a volume is specified,
            it should will be ignored for the search.
        """

        collection = self.tree.find("COLLECTION")
        if collection is None:
            raise ValueError("Could not find COLLECTION in NML file")

        entry = collection.xpath(
            f".//ENTRY/LOCATION[@DIR={xpath_string_escape(traktor_path.directories)}]"
            f"[@FILE={xpath_string_escape(traktor_path.file)}]"
            f"[@VOLUME={xpath_string_escape(traktor_path.volume)}]/.."
        )
        if len(entry) == 0:
            return None

        return NMLTrack(entry[0])

    # --------------------------- TrackStream protocol --------------------------- #

    @property
    def tracks(self) -> Iterable[NMLTrack]:
        collection = self.tree.find("COLLECTION")
        if collection is None:
            raise ValueError("Could not find COLLECTION in NML file")

        entries = collection.findall("ENTRY")
        for entry in entries:
            yield NMLTrack(entry)

    def __len__(self) -> int:
        e = self.tree.find("COLLECTION")
        if e is None:
            return 0

        n_str = e.get("ENTRIES", 0)
        return int(n_str)


def sanitize_name(input_str: str) -> str:
    """Sanitize the playlist name, traktor is picky with special characters."""
    return input_str.replace("$", "*").replace("\\", "|").lstrip("_")


class NMLPlaylistCollection(PlaylistCollection, LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library: NMLCollection

    # Root node to the playlist (not necessarly attached to the library)
    root_node: _Element  # <Node TYPE="PLAYLIST">

    def __init__(
        self,
        library: NMLCollection | str | Path,
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
            self.library = NMLCollection(library)
        else:
            self.library = library

        if isinstance(name, str):
            s_name = sanitize_name(name)
            if s_name != name:
                log.warning(
                    f"Playlist name changed from `{name}` to `{s_name}`"
                    " issues with Traktor.",
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

    def _remote_insert_track(self, *args, **kwargs) -> None:
        return None

    def _remote_delete_track(self, *args, **kwargs) -> None:
        return None

    def _remote_update_metadata(self, *args, **kwargs) -> None:
        return None

    def _apply_diff(
        self,
        before: Snapshot[NMLPlaylistTrack],
        after: Snapshot[NMLPlaylistTrack],
    ) -> None:
        """Wrap apply diff so `edit`."""
        super()._apply_diff(before, after)
        # Instead of an incremental update we just rewrite everything
        # here as this is easier and performance isnt really an issue
        self._overwrite_track_entries(after.tracks)
        self.library.upsert_playlist(self)

    def _remote_create(self):
        raise NotImplementedError

    @property
    def remote_associated(self) -> bool:
        raise NotImplementedError

    @staticmethod
    def _track_key(track: NMLPlaylistTrack):
        return track.path

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
            return self.find_by_traktor_path(TraktorPath.from_path(file_path))
        return None

    def find_by_traktor_path(
        self, traktor_path: TraktorPath
    ) -> NMLPlaylistTrack | None:
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
