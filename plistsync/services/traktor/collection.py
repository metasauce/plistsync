from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePath
from typing import TYPE_CHECKING
from uuid import uuid4

from lxml import etree
from lxml.etree import Element, SubElement, _Element

from plistsync.core import Track
from plistsync.core.collection import LibraryCollection, LocalLookup, TrackStream
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo
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

    # ------------------------ LibraryCollection protocol ------------------------ #

    def _playlist_nodes(self) -> Iterable[_Element]:
        """Get all playlists in the NML file."""
        nodes = self.tree.xpath(".//NODE[@TYPE='PLAYLIST']")
        return nodes

    @property
    def playlists(self) -> Iterable[NMLPlaylistCollection]:
        """Get all playlists in the NML file as NMLPlaylistCollection objects."""
        for node in self._playlist_nodes():
            pl = NMLPlaylistCollection(self, node)
            if pl.name.startswith("_"):
                continue
            yield pl

    def _get_playlist_root_node(self, playlist: str) -> _Element | None:
        """Get a playlist by name or uuid."""

        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST']/*[@UUID={xpath_string_escape(playlist)}]/.."
        )
        if len(node) > 0:
            return node[0]

        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST'][@NAME={xpath_string_escape(playlist)}]"
        )
        return node[0] if len(node) > 0 else None

    def get_playlist(self, name: Path | str) -> NMLPlaylistCollection | None:
        try:
            return NMLPlaylistCollection(self, self._get_playlist_root_node(str(name)))
        except ValueError:
            return None

    # --------------------------- LocalLookup protocol --------------------------- #

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> NMLTrack | None:
        """Find a track by its local IDs.

        We only support lookup by path here.
        """
        if file_path := local_ids.get("file_path"):
            return self.find_by_traktor_path(TraktorPath.from_path(file_path))
        return None

    def __len__(self) -> int:
        e = self.tree.find("COLLECTION")
        if e is None:
            return 0

        n_str = e.get("ENTRIES", 0)
        return int(n_str)

    def commit(self):
        """Write the changes back to the NML file."""
        self.tree.write(self.path, encoding="utf-8", xml_declaration=True)
        log.debug(f"Committed changes to {self.path}")

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


def sanitize_name(input_str: str) -> str:
    """Sanitize the playlist name, traktor is picky with special characters."""
    return input_str.replace("$", "*").replace("\\", "|").lstrip("_")


class NMLPlaylistCollection(PlaylistCollection, LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library_collection: NMLCollection

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
            The name or uuid of the playlist to fetch, from the collection.
            If _Element uses as root_node (for intenal purpose).
        """

        if isinstance(library, (str, Path)):
            self.library_collection = NMLCollection(library)
        else:
            self.library_collection = library

        if isinstance(name, str):
            s_name = sanitize_name(name)
            if s_name != name:
                log.warning(
                    f"Playlist name changed from `{name}` to `{s_name}`"
                    " issues with Traktor.",
                )

            root_node = self.library_collection._get_playlist_root_node(s_name)

            # Did not find a playlist node, we need to create a new one
            # this will NOT attach it into the main library yet!
            if root_node is None:
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

    def _attach_to_library(self, force=False):
        """Attach the playlist element into the nml library."""
        # Playlists lifes in a SUBNODES node of the $ROOT folder
        subnodes = self.library_collection.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )
        if len(subnodes) == 0:
            raise ValueError("Could not find SUBNODES in $ROOT folder in NML file")

        # Check if already exists
        if force or self.root_node not in subnodes[0]:
            subnodes[0].append(self.root_node)
            subnodes[0].set("COUNT", str(int(subnodes[0].get("COUNT", "0")) + 1))

    # ----------------------- Properties and info logic ---------------------- #

    @property
    def playlist_node(self) -> _Element:
        if node := self.root_node.find("PLAYLIST"):
            return node
        raise ValueError("Root node has no 'PLAYLIST' node")

    @property
    def info(self) -> PlaylistInfo:
        return PlaylistInfo(
            name=self.root_node.get("NAME", ""),
        )

    @info.setter
    def info(self, value: PlaylistInfo):
        self.root_node.set("NAME", value.get("NAME", ""))

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

    @property
    def tracks(self) -> list[NMLPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        entries = self.playlist_node.xpath(".//ENTRY/PRIMARYKEY[@TYPE='TRACK']/..")
        return [NMLPlaylistTrack(entry) for entry in entries]

    @tracks.setter
    def tracks(self, value: list[NMLPlaylistTrack]):
        # TODO set entries
        raise NotImplementedError

    def __len__(self) -> int:
        """Get the number of tracks in the playlist."""
        entries = self.playlist_node.get("ENTRIES", "0")
        return int(entries) if entries.isdigit() else 0

    # ----------------------------- Remote operations ---------------------------- #
    # TODO
    def insert(self, track: PurePath | Track) -> NMLPlaylistTrack:
        """Insert a track into the playlist.

        ATM it skips duplicate
        """
        path: PurePath
        if isinstance(track, Track):
            if track.path is None:
                raise ValueError("Tracks need to have a path to be inserted.")
            path = track.path
        else:
            path = track

        # Check if existing track is already in the playlist
        if ptrack := self.find_by_traktor_path(TraktorPath.from_path(path)):
            return ptrack

        # update playlist entries number
        ptrack = NMLPlaylistTrack.from_path(path)
        self.playlist_node.append(ptrack.entry)

        # Update the number of entries in the playlist
        entries_raw = self.playlist_node.get("ENTRIES", "0")
        try:
            entries = int(entries_raw)
        except ValueError:
            # If the entries are not a valid integer, we assume it's 0
            log.warning(f"Invalid number of entries in playlist: {entries_raw}")
            entries = 0
        entries += 1
        self.playlist_node.set("ENTRIES", str(entries))

        return ptrack

    def commit(self):
        """Write the changes back to the NML file."""
        self.library_collection.commit()

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
