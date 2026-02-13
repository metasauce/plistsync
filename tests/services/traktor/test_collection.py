from pathlib import Path
import sys
import pytest
from plistsync.services.traktor import NMLCollection
from plistsync.services.traktor.collection import NMLPlaylistCollection, TraktorPath
from plistsync.services.traktor.track import NMLPlaylistTrack
from tests.abc import CollectionTestBase, LibraryCollectionTestBase


class TestNMLCollection(LibraryCollectionTestBase):
    """Test the NMLCollection class."""

    collection_class = NMLCollection
    collection: NMLCollection

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
            ("name", "unknown playlist", True),
            ("uuid", "asdasdas", True),
        ]

    def test_len(self):
        """Test the length of the collection."""
        assert len(self.collection) == self.length

    def test_find_by_path(self):
        """Test finding a track by its file path."""
        # Test with a valid path in collection
        tp_exists = TraktorPath.from_path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        print(str(tp_exists.directories))
        print(str(tp_exists.file))
        print(str(tp_exists.volume))

        # Try with Volume specified
        track = self.collection.find_by_traktor_path(tp_exists)
        assert track is not None
        assert track.title == "Dragger"

        # Test with an invalid path
        tp_nonexistent = TraktorPath.from_path("D:/:nonexistent.mp3")
        track = self.collection.find_by_traktor_path(tp_nonexistent)
        assert track is None


class TestNMLPlaylistCollection(CollectionTestBase):
    """Test the NMLPlaylistCollection class."""

    collection_class = NMLPlaylistCollection

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLCollection, sample_track):
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
        with p1.edit():
            p1.tracks.append(NMLPlaylistTrack.from_path(track_path))
        assert len(p1) == l_before + 1

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

    def test_find_by_path(self, collection: NMLCollection, audio_files: Path):
        """Test finding a track by its file path in a playlist."""
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid traktor path
        example_path = "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"  # noqa: E501
        track = p1.find_by_traktor_path(TraktorPath(example_path))
        assert track is not None

        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = p1.find_by_local_ids({"file_path": example_path})
        assert track is not None
