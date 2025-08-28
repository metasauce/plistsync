from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Generator, Iterable, Iterator
from uuid import uuid4

from lxml import etree
from lxml.etree import Element, SubElement, _Element

from plistsync.core import Collection, Track
from plistsync.core.collection import LibraryCollection, LocalLookup, TrackStream
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log

from .track import NMLPlaylistTrack, NMLTrack

if TYPE_CHECKING:
    from lxml.etree import _ElementTree


def xpath_string_escape(input_str: str) -> str:
    """Create a concatenation of alternately-quoted strings that is always a valid XPath expression.

    see https://stackoverflow.com/questions/57639667/how-to-deal-with-single-and-double-quotes-in-xpath-in-python
    """
    if "'" not in input_str:
        return f"'{input_str}'"
    parts = input_str.split("'")
    return "concat('" + "', \"'\" , '".join(parts) + "', '')"


class NMLCollection(LibraryCollection, TrackStream, LocalLookup):
    """A Traktor NML collection.

    Allows to parse and interact with a Traktor NML file. I.e. traktor export playlist

    Sadly nml files do not contain unique identifiers for tracks, thus we need to iterate over all tracks to find a match. Might be less efficient than other collections.
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

    def find_by_traktor_path(self, path: str) -> NMLTrack | None:
        """Find a track by its file path.

        Parameter
        ---------
        path : str
            The file path of the track to find. This should be the full path including the filename. In traktor notation /:foo/:bar.mp3. If a volume is specified, it should will be ignored for the search.
        """

        collection = self.tree.find("COLLECTION")
        if collection is None:
            raise ValueError("Could not find COLLECTION in NML file")

        # Remove volume from path if it exists
        if not path.startswith("/"):
            # If the path does not start with a slash, we assume it is a volume
            # e.g. "C:/:foo/:bar.mp3"
            path = "/" + path.split("/", 1)[-1]

        # remove ending file.any
        path, file = path.rsplit("/:", 1)

        entry = collection.xpath(
            f".//ENTRY/LOCATION[@DIR={xpath_string_escape(path + '/:')}][@FILE={xpath_string_escape(file)}]/.."
        )
        if len(entry) == 0:
            return None

        return NMLTrack(entry[0])

    # ------------------------------- Protocols ------------------------------ #

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> NMLTrack | None:
        """Find a track by its local IDs.

        We only support lookup by path here.
        """
        if file_path := local_ids.get("file_path"):
            # If the file_path is set, we can use it to find the track
            return self.find_by_traktor_path(_path_to_traktor(file_path))
        return None

    def __iter__(self) -> Iterator[NMLTrack]:
        collection = self.tree.find("COLLECTION")
        if collection is None:
            raise ValueError("Could not find COLLECTION in NML file")

        entries = collection.findall("ENTRY")
        for entry in entries:
            yield NMLTrack(entry)

    # --------------------------------- playlists -------------------------------- #

    @property
    def playlists(self) -> Iterable[NMLPlaylistCollection]:
        """Get all playlists in the NML file as NMLPlaylistCollection objects."""
        for node in self._playlist_nodes():
            pl = NMLPlaylistCollection(self, node)
            if pl.name.startswith("_"):
                continue
            yield pl

    def get_playlist(self, name: Path | str) -> NMLPlaylistCollection | None:
        try:
            return NMLPlaylistCollection(self, self._get_playlist_root_node(str(name)))
        except ValueError:
            return None

    def _playlist_nodes(self) -> Iterable[_Element]:
        """Get all playlists in the NML file."""
        nodes = self.tree.xpath(".//NODE[@TYPE='PLAYLIST']")
        return nodes

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


class NMLPlaylistCollection(Collection, TrackStream, LocalLookup):
    """A Traktor NML playlist collection.

    Traktor playlists use file paths as the identifiers.

    Allows to parse and interact with a Traktor NML file that contains playlists.
    """

    library_collection: NMLCollection
    root_node: _Element  # <Node TYPE="PLAYLIST">
    playlist_node: _Element  # <Playlist TYPE="LIST">, sits in root_node

    def __init__(
        self,
        library_collection: NMLCollection | str | Path,
        playlist: str | _Element | None = None,
        create: bool = False,
    ):
        """Initialize the NMLPlaylistCollection.

        Parameter
        ---------
        library_collection : NMLCollection | str | Path
            The root collection from which the playlists are derived.
        playlist : str | _Element
            The name or uuid of the playlist to fetch, or an XML element representing the
            playlist. If an XML element is provided, it will override any existing
            playlist with the same uuid. If None, creates a new empty playlist.
        create : bool
            If True, creates a new empty playlist in the library_collection,
            if the specified playlist does not exist yet. Otherwise raises an error.

        Notes
        -----
        - Even if `create` is set to true, no changes are written to disk
        until the `commit` method is called.
        """

        if isinstance(library_collection, (str, Path)):
            self.library_collection = NMLCollection(Path(library_collection))
        else:
            self.library_collection = library_collection

        root_node: _Element | None = None
        playlist_node: _Element | None = None
        if isinstance(playlist, str):
            # sanitize the playlist name, traktor is picky with special characters
            p_name = playlist.replace("$", "*").replace("\\", "|").lstrip("_")
            if p_name != playlist:
                log.warning(
                    f"Had to change playlist name from {playlist} to {p_name} to avoid issues with Traktor."
                )
            playlist = p_name
            root_node = self.library_collection._get_playlist_root_node(playlist)
        elif isinstance(playlist, _Element):
            # We assume the node is a valid playlist node
            root_node = playlist

        # Did not find a playlist node, we might want to create a new one
        if root_node is None and create:
            # Create a new empty playlist node
            playlist_name = "New Playlist"
            if isinstance(playlist, str) and playlist != "":
                playlist_name = playlist
            root_node = Element("NODE", {"TYPE": "PLAYLIST"})
            root_node.set("NAME", playlist_name)

            # Add <Playlist> list node
            playlist_node = SubElement(root_node, "PLAYLIST")
            playlist_node.set("TYPE", "LIST")
            playlist_node.set("UUID", uuid4().hex)
            playlist_node.set("ENTRIES", "0 ")
            root_node.append(playlist_node)

            # Playlists live in a SUBNODES node of the $ROOT folder
            subnodes = self.library_collection.tree.xpath(
                f".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
            )
            if len(subnodes) == 0:
                raise ValueError("Could not find SUBNODES in $ROOT folder in NML file")

            subnodes[0].append(root_node)
            subnodes[0].set("COUNT", str(int(subnodes[0].get("COUNT", "0")) + 1))

        elif root_node is None:
            raise ValueError(
                f"Could not find playlist {playlist} in collection "
                + f"{self.library_collection.path}. Consider setting `create=True`."
            )

        playlist_node = root_node.find("PLAYLIST")
        if playlist_node is None:
            raise ValueError(f"Could not find PLAYLIST node in root node {root_node}")

        self.root_node = root_node
        self.playlist_node = playlist_node

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

    @property
    def name(self) -> str:
        """Get the name of the playlist."""
        name = self.root_node.get("NAME", None)
        if name is None:
            name = "New Playlist"
            self.name = name
        return name

    @name.setter
    def name(self, value: str) -> None:
        """Set the name of the playlist."""
        self.root_node.set("NAME", value)

    def __len__(self) -> int:
        """Get the number of tracks in the playlist."""
        entries = self.playlist_node.get("ENTRIES", "0")
        return int(entries) if entries.isdigit() else 0

    def insert(self, track: Path | Track) -> NMLPlaylistTrack:
        """Insert a track into the playlist.

        ATM it skips duplicate
        """
        if isinstance(track, Track):
            if track.path is None:
                raise ValueError("Tracks need to have a path to be inserted.")
            track = track.path

        # Check if existing track is already in the playlist
        if ptrack := self.find_by_traktor_path(_path_to_traktor(track)):
            return ptrack

        # update playlist entries number
        ptrack = NMLPlaylistTrack.from_path(track)
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

    def find_by_traktor_path(self, path: str) -> NMLPlaylistTrack | None:
        """Find a track by its file path.

        Parameter
        ---------
        path : str
            The file path of the track to find. This should be the full path including the filename. In traktor notation /:foo/:bar.mp3. If a volume is specified, it should will be ignored for the search.
        """

        entries = self.playlist_node.xpath(
            f".//ENTRY/PRIMARYKEY[@TYPE='TRACK'][@KEY={xpath_string_escape(path)}]"
        )
        if len(entries) == 0:
            return None
        elif len(entries) > 1:
            log.warning(
                f"Found duplicate entries for path {path} in playlist, using first one."
            )

        return NMLPlaylistTrack(entries[0])

    # ------------------------------- Protocols ------------------------------ #

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
            return self.find_by_traktor_path(_path_to_traktor(file_path))
        return None

    def __iter__(self) -> Generator[NMLPlaylistTrack, None, None]:
        """Iterate over the tracks in the playlist."""

        # Playlist on include a primarykey node which we still have
        # to match to the collection
        entries = self.playlist_node.xpath(".//ENTRY/PRIMARYKEY[@TYPE='TRACK']/..")
        for entry in entries:
            yield NMLPlaylistTrack(entry)
