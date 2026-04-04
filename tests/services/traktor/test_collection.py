from pathlib import Path
import sys
import pytest
from plistsync.services.traktor import NMLLibraryCollection
from plistsync.services.traktor import NMLPlaylistCollection
from plistsync.services.traktor import NMLPath
from plistsync.services.traktor.track import NMLPlaylistTrack
from plistsync.services.traktor.utility import xpath_string_escape
from tests.abc.collection import CollectionTestBase, LibraryCollectionTestBase

from lxml.etree import _Element


class TestNMLCollection(LibraryCollectionTestBase):
    """Test the NMLCollection class."""

    collection_class = NMLLibraryCollection
    collection: NMLLibraryCollection

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
            ("uuid", "6868ecd66b354d37a33b965dae7a82e7"),  # By UUID
        ]

    @property
    def unknown_playlists(self):
        return [
            ("name", "unknown playlist"),
            ("uuid", "asdasdas"),
        ]

    def test_get_playlist_invalid_args(self, collection):
        with pytest.raises(ValueError):
            collection.get_playlist(name="Foo", uuid="bar")

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

    def test_write_persists(self, collection: NMLLibraryCollection) -> None:
        """Calling write should persist the collection"""
        new_name = "Updated name"
        p = collection.get_playlist_or_raise(uuid="6868ecd66b354d37a33b965dae7a82e7")
        p.name = new_name
        collection.write()

        # After reload should be persisteted!
        reloaded = NMLLibraryCollection(collection.path)
        p2 = reloaded.get_playlist_or_raise(uuid="6868ecd66b354d37a33b965dae7a82e7")
        assert p2.name == new_name

    def test_find_by_local_ids(self, collection: NMLLibraryCollection):
        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = collection.find_by_local_ids({"file_path": example_path})
        assert track is not None

        track = collection.find_by_local_ids({})
        assert track is None

    @pytest.mark.parametrize(
        [
            "backup",
        ],
        [(True,), (False,)],
    )
    def test_write_backup(
        self,
        collection: NMLLibraryCollection,
        backup: bool,
    ):
        collection.write(backup=backup)
        # Check that a .bak file was or was not created
        bak_files = list(collection.path.parent.glob(f"{collection.path.stem}*.bak"))
        assert len(bak_files) == int(backup)


class TestNMLPlaylistCollection(CollectionTestBase):
    """Test the NMLPlaylistCollection class."""

    collection_class = NMLPlaylistCollection

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLLibraryCollection, sample_track):
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
        [Path("/Volumes/Macintosh HD/foo/bar.mp3")],
    )
    def test_insert_track(self, track_path):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        l_before = len(p1)
        with p1.remote_edit():
            p1.tracks.append(NMLPlaylistTrack.from_path(track_path))
        assert len(p1) == l_before + 1

    @pytest.mark.parametrize(
        "track_path",
        [Path("/Volumes/Macintosh HD/foo/bar.mp3")],
    )
    def test_overwrite_tracks(self, track_path):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None
        with p1.remote_edit():
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
        with p1.remote_edit():
            for audio_file in audio_files.iterdir():
                p1.tracks.append(NMLPlaylistTrack.from_path(audio_file))
                break
        assert len(p1) == l_before + 1

    def test_find_by_traktor_path(self, collection: NMLLibraryCollection, caplog):
        """Test finding a track by its file path in a playlist."""
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid traktor path
        example_path = "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"  # noqa: E501
        track = p1.find_by_traktor_path(NMLPath(example_path))
        assert track is not None

        # Test valid but not in collection
        track = p1.find_by_traktor_path(NMLPath("D:/:Not/:existing.flac"))
        assert track is None

        with p1.remote_edit():
            p1.tracks.append(p1.tracks[-1])
        track = p1.find_by_traktor_path(p1.tracks[-1].traktor_path)
        assert "duplicate" in caplog.text

    def test_find_by_local_ids(self, collection: NMLLibraryCollection):
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = p1.find_by_local_ids({"file_path": example_path})
        assert track is not None

        track = p1.find_by_local_ids({})
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
