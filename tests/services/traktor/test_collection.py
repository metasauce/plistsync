from pathlib import Path, PurePath
import sys
import pytest
from plistsync.core.ids import FilePath
from plistsync.services.traktor import NMLLibrary
from plistsync.services.traktor import NMLPlaylist
from plistsync.services.traktor import NMLPath
from plistsync.services.traktor.track import NMLPlaylistTrack
from plistsync.services.traktor.utility import xpath_string_escape
from tests.abc.collection import CollectionTestBase, LibraryCollectionTestBase

from lxml import etree
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml.etree import _Element


class TestNMLLibrary(LibraryCollectionTestBase):
    """Test the NMLLibrary class."""

    collection_class = NMLLibrary
    collection: NMLLibrary

    length = 265  # Number of tracks in the test NML file

    @pytest.fixture(autouse=True)
    def setup(self, collection, sample_track):
        self.collection = collection
        self.track = sample_track

    def create_collection(self):
        yield self.collection

    def create_sample_track(self):
        return self.track

    @property
    def known_playlists(self):
        return [
            ("name", "Silvester Full Playthrough"),  # By name
            ("id", "6868ecd66b354d37a33b965dae7a82e7"),  # By UUID
        ]

    @property
    def unknown_playlists(self):
        return [
            ("name", "unknown playlist"),
            ("id", "asdasdas"),
        ]

    def test_get_playlist_invalid_args(self, collection: NMLLibrary):
        with pytest.raises(ValueError):
            collection.get_playlist(name="Foo", id="bar")  # type: ignore

    def test_len(self):
        """Test the length of the collection."""
        assert len(self.collection) == self.length

        # Remove the COLLECTION node to force 0
        node: _Element = self.collection.tree.find("COLLECTION")  # type: ignore
        parent: _Element = node.getparent()  # type: ignore
        parent.remove(node)
        assert len(self.collection) == 0

    def test_find_by_path(self):
        """Test finding a track by its file path."""
        # Test with a valid path in collection
        tp_exists = NMLPath.from_path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        # Try with Volume specified
        track = self.collection.find_by_traktor_path(tp_exists)
        assert track is not None
        assert track.title == "Dragger"

        # Test with an invalid path
        tp_nonexistent = NMLPath.from_path("D:/:nonexistent.mp3")
        track = self.collection.find_by_traktor_path(tp_nonexistent)
        assert track is None

    def test_write_persists(self, collection: NMLLibrary) -> None:
        """Calling write should persist the collection"""
        new_name = "Updated name"
        p = collection.get_playlist_or_raise(id="6868ecd66b354d37a33b965dae7a82e7")
        p.name = new_name
        collection.write()

        # After reload should be persisteted!
        reloaded = NMLLibrary(collection.path)
        p2 = reloaded.get_playlist_or_raise(id="6868ecd66b354d37a33b965dae7a82e7")
        assert p2.name == new_name

    def test_find_by_ids(self, collection: NMLLibrary):
        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = collection.find_by_ids({FilePath(example_path)})
        assert track is not None

        track = collection.find_by_ids(set())
        assert track is None

    @pytest.mark.parametrize(
        [
            "backup",
        ],
        [(True,), (False,)],
    )
    def test_write_backup(
        self,
        collection: NMLLibrary,
        backup: bool,
    ):
        collection.write(backup=backup)
        # Check that a .bak file was or was not created
        bak_files = list(collection.path.parent.glob(f"{collection.path.stem}*.bak"))
        assert len(bak_files) == int(backup)


class TestNMLPlaylist(CollectionTestBase):
    """Test the NMLPlaylist class."""

    collection_class = NMLPlaylist

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLLibrary, sample_track):
        self.collection = collection
        self.track = sample_track

    def create_collection(self):
        yield self.collection

    def create_sample_track(self):
        return self.track

    # The file only has one playlist
    name = "Silvester Full Playthrough"
    uuid = "6868ecd66b354d37a33b965dae7a82e7"

    def test_set_uuid(self):
        """Test setting the UUID of a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        p1.uuid = "new-uuid"
        assert p1.uuid == "new-uuid"

        # Reset to original UUID
        p1.uuid = self.uuid
        assert p1.uuid == self.uuid

    def test_set_name(self):
        """Test setting the name of a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        p1.name = "New Playlist Name"
        assert p1.name == "New Playlist Name"

        # Reset to original name
        p1.name = self.name
        assert p1.name == self.name

    @pytest.mark.parametrize(
        "track_path",
        [
            Path("/Volumes/Macintosh HD/foo/bar.mp3"),
            PurePath("D:/foo/bar.mp3"),
        ],
    )
    def test_insert_track(self, track_path):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        l_before = len(p1)
        with p1.edit():
            p1.tracks.append(NMLPlaylistTrack.from_path(track_path))
        assert len(p1) == l_before + 1

    @pytest.mark.parametrize(
        "track_path",
        [
            PurePath("/Volumes/Macintosh HD/foo/bar.mp3"),
            PurePath("D:/foo/bar.mp3"),
        ],
    )
    def test_nml_path_to_nml_location(self, track_path):
        traktor_path = NMLPath.from_path(track_path)

        location = traktor_path.to_nml_location()
        assert location.tag == "LOCATION"
        assert location.get("DIR") == traktor_path.directories
        assert location.get("FILE") == traktor_path.file
        assert location.get("VOLUME") == traktor_path.volume

        parent = etree.Element("ENTRY")
        location2 = traktor_path.to_nml_location(parent)
        assert location2.getparent() is parent
        assert parent.find("LOCATION") is location2

    @pytest.mark.parametrize(
        "track_path",
        [
            PurePath("/Volumes/Macintosh HD/foo/insert-me.flac"),
            PurePath("D:/foo/insert-me.flac"),
        ],
    )
    def test_library_insert_track(self, track_path):
        traktor_path = NMLPath.from_path(track_path)
        playlist_track = NMLPlaylistTrack.from_traktor_path(traktor_path)

        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        entries_before = int(collection_node.get("ENTRIES", "0"))

        inserted = self.collection.insert_track(playlist_track)
        assert inserted is not None
        assert inserted.traktor_path == traktor_path

        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        assert int(collection_node.get("ENTRIES", "0")) == entries_before + 1

        entry = inserted.entry
        assert entry.get("MODIFIED_DATE") == "2008/10/16"
        assert entry.get("MODIFIED_TIME") == "0"

        loc = entry.find("LOCATION")
        assert loc is not None
        assert loc.get("DIR") == traktor_path.directories
        assert loc.get("FILE") == traktor_path.file
        assert loc.get("VOLUME") == traktor_path.volume
        assert loc.get("VOLUMEID") == traktor_path.volume_id

        mod_info = entry.find("MODIFICATION_INFO")
        assert mod_info is not None
        assert mod_info.get("AUTHOR_TYPE") == "user"

        info = entry.find("INFO")
        assert info is not None
        assert info.get("IMPORT_DATE") is not None

        inserted_again = self.collection.insert_track(playlist_track)
        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        assert int(collection_node.get("ENTRIES", "0")) == entries_before + 1
        assert inserted_again is not None
        assert inserted_again.traktor_path == traktor_path

        inserted_forced = self.collection.insert_track(playlist_track, force=True)
        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        assert int(collection_node.get("ENTRIES", "0")) == entries_before + 2
        assert inserted_forced is not None
        assert inserted_forced.traktor_path == traktor_path

    @pytest.mark.parametrize(
        "track_path",
        [
            PurePath("/Volumes/Macintosh HD/foo/to-nml-track.flac"),
            PurePath("D:/foo/to-nml-track.flac"),
        ],
    )
    def test_playlist_track_to_nml_track(self, track_path):
        traktor_path = NMLPath.from_path(track_path)
        playlist_track = NMLPlaylistTrack.from_traktor_path(traktor_path)

        found = playlist_track.to_nml_track(self.collection, insert_if_not_found=False)
        assert found is None

        inserted = playlist_track.to_nml_track(self.collection)
        assert inserted is not None
        assert inserted.traktor_path == traktor_path

        found_again = playlist_track.to_nml_track(
            self.collection, insert_if_not_found=False
        )
        assert found_again is not None
        assert found_again.traktor_path == traktor_path

    @pytest.mark.parametrize(
        "track_path",
        [
            PurePath("/Volumes/Macintosh HD/foo/added-via-edit.flac"),
            PurePath("D:/foo/added-via-edit.flac"),
        ],
    )
    def test_playlist_edit_inserts_missing_track_into_library(self, track_path):
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        traktor_path = NMLPath.from_path(track_path)
        missing_track = NMLPlaylistTrack.from_traktor_path(traktor_path)

        assert self.collection.find_by_traktor_path(traktor_path) is None

        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        entries_before = int(collection_node.get("ENTRIES", "0"))

        with p1.edit():
            p1.tracks.append(missing_track)

        collection_node = self.collection.tree.find("COLLECTION")
        assert collection_node is not None
        assert int(collection_node.get("ENTRIES", "0")) == entries_before + 1

        inserted = self.collection.find_by_traktor_path(traktor_path)
        assert inserted is not None
        assert inserted.traktor_path == traktor_path

    @pytest.mark.parametrize(
        "track_path",
        [Path("/Volumes/Macintosh HD/foo/bar.mp3")],
    )
    def test_overwrite_tracks(self, track_path):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None
        with p1.edit():
            p1.tracks = [NMLPlaylistTrack.from_path(track_path)]
        assert len(p1) == 1

    @pytest.mark.skipif(
        sys.platform == "linux",
        reason="""
        we do path prefix checks, which require a macOS or Windows style
        absolute path - which is not possible with real files on linux.
        """,
    )
    def test_insert_track_real_file(self, audio_files: Path):
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        l_before = len(p1)
        with p1.edit():
            for audio_file in audio_files.iterdir():
                p1.tracks.append(NMLPlaylistTrack.from_path(audio_file))
                break
        assert len(p1) == l_before + 1

    def test_find_by_traktor_path(self, collection: NMLLibrary, caplog):
        """Test finding a track by its file path in a playlist."""
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid traktor path
        example_path = "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"
        track = p1.find_by_traktor_path(NMLPath(example_path))
        assert track is not None

        # Test valid but not in collection
        track = p1.find_by_traktor_path(NMLPath("D:/:Not/:existing.flac"))
        assert track is None

        with p1.edit():
            p1.tracks.append(p1.tracks[-1])
        track = p1.find_by_traktor_path(p1.tracks[-1].traktor_path)
        assert "duplicate" in caplog.text

    def test_find_by_ids(self, collection: NMLLibrary):
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = p1.find_by_ids({FilePath(example_path)})
        assert track is not None

        track = p1.find_by_ids(set())
        assert track is None


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("", "''"),
        ("abc", "'abc'"),
        ("a'b", "concat('a', \"'\" , 'b', '')"),
        ("'abc", "concat('', \"'\" , 'abc', '')"),
        ("abc'", "concat('abc', \"'\" , '', '')"),
        ("a'b'c", "concat('a', \"'\" , 'b', \"'\" , 'c', '')"),
    ],
)
def test_xpath_string_escape_format(input_str: str, expected: str) -> None:
    assert xpath_string_escape(input_str) == expected
