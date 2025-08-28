from enum import auto
from typing import Generator

from pathlib import Path, PurePosixPath, PureWindowsPath
import pytest
from plistsync.core import Collection, Track
from plistsync.services.local import LocalTrack
from plistsync.services.traktor import NMLTrack
from plistsync.services.traktor.track import TraktorPath
from plistsync.services.traktor.collection import NMLPlaylistCollection
from plistsync.services.traktor.collection import NMLCollection
from tests.abc import CollectionTestBase, LibraryCollectionTestBase, TrackTestBase

import lxml.etree as ET


import pytest


class TestTraktorPath:
    @pytest.mark.parametrize(
        "path, parts",
        [
            # MacOS style paths
            (
                "/Volumes/Macintosh HD/Music/Drum and Bass/file.flac",
                ("Macintosh HD", "Music", "Drum and Bass", "file.flac"),
            ),
            (
                "/Macintosh HD/Music/file.flac",
                ("Macintosh HD", "Music", "file.flac"),
            ),
            (
                PurePosixPath("/Volumes/Macintosh HD/Music/file.flac"),
                ("Macintosh HD", "Music", "file.flac"),
            ),
            (
                Path("/Macintosh HD/Music/file.flac"),
                ("Macintosh HD", "Music", "file.flac"),
            ),
        ],
    )
    def test_from_path_mac(self, path, parts):
        tp = TraktorPath.from_path(path)
        assert tp.os == "macos"
        assert tp.volume is not None
        assert tp.directories is not None
        assert tp.file is not None
        assert tp.parts == parts

    @pytest.mark.parametrize(
        "path",
        [
            Path("C:/Music/Drum and Bass/04 Dragger [1028kbps].flac"),
            Path("C://Music///Drum and Bass/04 Dragger [1028kbps].flac"),
            Path("C:\\Music\\Drum and Bass\\04 Dragger [1028kbps].flac"),
            PureWindowsPath("C:\\Music\\Drum and Bass\\04 Dragger [1028kbps].flac"),
        ],
    )
    def test_from_path_windows(self, path):
        tp = TraktorPath.from_path(path)
        assert tp.os == "windows"
        assert tp.volume == "C:"
        assert tp.directories == "Music/:Drum and Bass"
        assert tp.file == "04 Dragger [1028kbps].flac"

    @pytest.mark.parametrize(
        "path",
        [
            "foo/bar/file.flac",  # no slash start and no drive
            "/Macintosh HD/Music/Drum and Bass/file.flac",  # macOS pathn without /Volumes
            "/Volumes/file.flac",  # macOS no volume ?
            "/foo/Music/Drum and Bass/file.flac",  # linux style path not supported
        ],
    )
    def test_from_path_invalid(self, path):
        with pytest.raises(Exception):
            TraktorPath.from_path(path)


@pytest.fixture()
def collection():
    """Fixture to create a NMLCollection for testing."""
    t_path = Path(__file__).parent.parent / "data" / "traktor_playlist.nml"
    return NMLCollection(t_path)


@pytest.fixture()
def sample_track():
    """Fixture to create a sample NMLTrack for testing."""
    return NMLTrack(
        ET.fromstring(
            """
                <ENTRY MODIFIED_DATE="2024/12/31" MODIFIED_TIME="84980"
                    AUDIO_ID="APd4yoypyZuaqbuMqM7+u+3f393+v/3IevqreJZFrv23u7zZvZzZunes/8itvNzv3//9r9///+/7///r///M7v//yvvP/v//////////////////////////////////////////////////////////3////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////+///////////////////////////////////////////////////////////8lRAAAAAA=="
                    TITLE="Ready Or Not (Original Mix)" ARTIST="Smash, Grab">
                    <LOCATION DIR="/:sync/:jungle is massive/:" FILE="06 Ready Or Not [1074kbps].flac"
                        VOLUME="F:" VOLUMEID="6580a7aa"></LOCATION>
                    <ALBUM TRACK="6"
                        TITLE="Welcome To The Jungle, Vol. 5: The Ultimate Jungle Cakes Drum &amp; Bass Compilation"></ALBUM>
                    <MODIFICATION_INFO AUTHOR_TYPE="user"></MODIFICATION_INFO>
                    <INFO BITRATE="1075000" PRODUCER="Jungle Cakes"
                        COVERARTID="121/ZXLGDNDNMRPNLDS4GWDYBLD20QPA" KEY="8m" PLAYCOUNT="1" PLAYTIME="247"
                        IMPORT_DATE="2025/1/5" LAST_PLAYED="2025/1/1" RELEASE_DATE="2017/7/17" FLAGS="12"
                        FILESIZE="32703" COLOR="5"></INFO>
                    <TEMPO BPM="175.000031" BPM_QUALITY="100.000000"></TEMPO>
                    <LOUDNESS PEAK_DB="0.214146" PERCEIVED_DB="-3.563812" ANALYZED_DB="-3.563812"></LOUDNESS>
                    <MUSICAL_KEY VALUE="22"></MUSICAL_KEY>
                    <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="4" START="2.342987" LEN="0.000000"
                        REPEATS="-1" HOTCUE="-1">
                        <GRID BPM="175.000031"></GRID>
                    </CUE_V2>
                    <CUE_V2 NAME="AutoGrid" DISPL_ORDER="0" TYPE="0" START="2.342987" LEN="0.000000"
                        REPEATS="-1" HOTCUE="0" COLOR="#FFFFFF"></CUE_V2>
                </ENTRY>
                """
        )
    )


class TestNMLTrack(TrackTestBase):
    track_class = NMLTrack
    test_config = {
        "has_path": True,
    }

    @pytest.fixture(autouse=True)
    def setup(self, sample_track):
        self.track = sample_track

    def create_track(self, *args, **kwargs) -> Generator[Track, None, None]:
        yield self.track


class TestNMLCollection(LibraryCollectionTestBase):
    """Test the NMLCollection class."""

    collection_class = NMLCollection

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
    def known_playlist_names(self):
        return [
            "Silvester Full Playthrough",  # By name
            "6868ecd66b354d37a33b965dae7a82e7",  # By UUID
        ]

    @property
    def unknown_playlist_names(self):
        return ["unknown playlist"]

    def test_len(self, collection):
        """Test the length of the collection."""
        assert len(collection) == self.length

    def test_find_by_path(self, collection):
        """Test finding a track by its file path."""
        # Test with a valid path
        example_path = "/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"

        track = collection.find_by_traktor_path(example_path)
        assert track is not None
        assert track.title == "Dragger"

        # Try with Volume specified
        track = collection.find_by_traktor_path("D:" + example_path)
        assert track is not None
        assert track.title == "Dragger"

        # Test with an invalid path
        track = collection.find_by_traktor_path("D:/:nonexistent.mp3")
        assert track is None


class TestNMLPlaylistCollection(CollectionTestBase):
    """Test the NMLPlaylistCollection class."""

    collection_class = NMLPlaylistCollection

    @pytest.fixture(autouse=True)
    def setup(self, collection, sample_track):
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
        p1 = self.collection.get_playlist(self.name)
        assert p1 is not None

        p1.uuid = "new-uuid"
        assert p1.uuid == "new-uuid"

        # Reset to original UUID
        p1.uuid = self.uuid
        assert p1.uuid == self.uuid

    def test_set_name(self):
        """Test setting the name of a playlist."""
        p1 = self.collection.get_playlist(self.name)
        assert p1 is not None

        p1.name = "New Playlist Name"
        assert p1.name == "New Playlist Name"

        # Reset to original name
        p1.name = self.name
        assert p1.name == self.name

    @pytest.mark.parametrize(
        "track",
        [Path("/foo/bar.mp3"), "file"],
    )
    def test_insert_track(self, track, audio_files):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(self.name)
        assert p1 is not None

        l_before = len(p1)
        if isinstance(track, Path):
            p1.insert(track)
        else:
            for audio_file in audio_files.iterdir():
                p1.insert(LocalTrack(audio_file))
                break

        # Check if the track was added
        assert len(p1) == l_before + 1

    def test_find_by_path(self, collection: NMLCollection, audio_files: Path):
        """Test finding a track by its file path in a playlist."""
        p1 = collection.get_playlist(self.name)
        assert p1 is not None

        # Test with a valid traktor path
        example_path = "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"
        track = p1.find_by_traktor_path(example_path)
        assert track is not None

        # Test with a valid path
        example_path = Path(
            "/D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = p1.find_by_local_ids({"file_path": example_path})
        assert track is not None
