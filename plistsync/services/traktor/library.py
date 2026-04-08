from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, overload

from lxml import etree

from plistsync.config import Config
from plistsync.core.collection import Library, LocalLookup, TrackStream
from plistsync.core.playlist import PlaylistIDs
from plistsync.core.track import LocalTrackIDs
from plistsync.logger import log

from .path import NMLPath
from .playlist import NMLPlaylist
from .track import NMLTrack
from .utility import sanitize_plist_name, xpath_string_escape

if TYPE_CHECKING:
    from lxml.etree import _Element, _ElementTree


class NMLLibrary(
    Library[NMLTrack, NMLPlaylist],
    TrackStream[NMLTrack],
    LocalLookup[NMLTrack],
):
    """A Traktor NML Library.

    Allows to parse and interact with a Traktor NML file. I.e. traktor export playlist

    Sadly nml files do not contain unique identifiers for tracks, thus we need to
    iterate over all tracks to find a match. Might be less efficient than other
    collections.
    """

    path: Path
    tree: _ElementTree

    def __init__(self, path: Path | str | None = None):
        if path is None:
            path = Config().traktor.path

        if isinstance(path, str):
            path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"File {path} does not exist")

        self.path = Path(path)

        # An NML file is a XML file
        self.tree = etree.parse(self.path)

    def write(self, backup: bool | None = None):
        """Write changes to NML file.

        Creates backup if backup=True or config 'traktor.backup_before_write' enabled.
        """

        if backup is None:
            traktor_config = Config().traktor
            backup = traktor_config.backup_before_write

        if backup:
            nml_backup = self.path.with_suffix(
                f".{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
            )
            copyfile(self.path, nml_backup)

        self.tree.write(
            self.path,
            encoding="utf-8",
            xml_declaration=True,
            standalone=False,
        )
        log.debug(f"Written collection changes to '{self.path}'")

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[NMLPlaylist]:
        """Get all playlists in the NML file as NMLPlaylist objects."""
        for node in self._playlist_nodes():
            pl = NMLPlaylist(self, node)
            if pl.name.startswith("_"):
                continue
            yield pl

    @overload
    def get_playlist(self, *, name: str | None = None) -> NMLPlaylist | None: ...
    @overload
    def get_playlist(self, *, uuid: str | None = None) -> NMLPlaylist | None: ...
    @overload
    def get_playlist(self, *, ids: PlaylistIDs | None = None) -> NMLPlaylist | None: ...

    def get_playlist(
        self,
        *,
        ids: PlaylistIDs | None = None,
        name: str | None = None,
        uuid: str | None = None,
    ) -> NMLPlaylist | None:
        """Get a specific playlist.

        Exactly one of the kwargs must be given. Either search by name or by uuid.

        If Ids are not found this raises, but if names are not found it retuns None.
        """
        if sum(arg is not None for arg in [name, uuid, ids]) != 1:
            raise ValueError("Exactly one of name, ids or uuid must be provided")

        if ids and (traktor_id := ids.get("traktor_id")):
            uuid = traktor_id

        root_node: _Element | None = None

        if uuid is not None:
            root_node = self._get_playlist_root_node_by_uuid(uuid)
        elif name is not None:
            s_name = sanitize_plist_name(name)
            if s_name != name:
                log.warning(
                    f"Playlist name changed from `{name}` to `{s_name}`"
                    " to avoid issues with Traktor.",
                )
            root_node = self._get_playlist_root_node_by_name(s_name)

        if root_node is None:
            return None

        return NMLPlaylist(self, root_node)

    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: Sequence[NMLTrack] | None = None,
    ):
        root_node = NMLPlaylist._create_root_node(name)

        # Insert under playlists root
        subnodes = self.tree.xpath(
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

        pl = NMLPlaylist(self, root_node)

        with pl.edit():
            # Description not supported
            # pl.description = description
            if tracks:
                pl.tracks = tracks

        return pl

    def _playlist_nodes(self) -> Iterable[_Element]:
        """Get all playlists in the NML file."""
        nodes = self.tree.xpath(".//NODE[@TYPE='PLAYLIST']")
        return nodes

    def _get_playlist_root_node_by_uuid(self, uuid: str) -> _Element | None:
        """Get a playlist by uuid."""

        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST']/*[@UUID={xpath_string_escape(uuid)}]/.."
        )
        if len(node) > 0:
            return node[0]
        else:
            return None

    def _get_playlist_root_node_by_name(self, name: str) -> _Element | None:
        node = self.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST'][@NAME={xpath_string_escape(name)}]"
        )
        if len(node) > 0:
            return node[0]
        else:
            return None

    # --------------------------- LocalLookup protocol --------------------------- #

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> NMLTrack | None:
        """Find a track by its local IDs.

        We only support lookup by path here.
        """
        if file_path := local_ids.get("file_path"):
            return self.find_by_traktor_path(NMLPath.from_path(file_path))

        return None

    def find_by_traktor_path(self, traktor_path: NMLPath) -> NMLTrack | None:
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
