import pytest
from pathlib import Path, PurePosixPath, PureWindowsPath
from lxml.etree import Element
from plistsync.services.traktor import NMLPath


class TestTraktorPath:
    @pytest.mark.parametrize(
        "path, expected_parts",
        [
            (
                "/Volumes/Macintosh HD/Music/Drum and Bass/file.flac",
                ("Macintosh HD", "Music", "Drum and Bass", "file.flac"),
            ),
            (
                PurePosixPath("/Volumes/Macintosh HD/Music/file.flac"),
                ("Macintosh HD", "Music", "file.flac"),
            ),
            (
                Path("/Volumes/Macintosh HD/Music/file.flac"),
                ("Macintosh HD", "Music", "file.flac"),
            ),
        ],
    )
    def test_from_path_mac(self, path, expected_parts):
        tp = NMLPath.from_path(path)
        assert tp.os == "macos"
        assert tp.volume is not None
        assert tp.directories is not None
        assert tp.file is not None
        assert tp.parts == list(expected_parts)
        assert isinstance(tp.pure_path, PurePosixPath)
        assert str(tp.pure_path).startswith("/Volumes/")

    @pytest.mark.parametrize(
        "path, expected_parts",
        [
            (
                "C:/Music/Drum and Bass/file.flac",
                ("C:", "Music", "Drum and Bass", "file.flac"),
            ),
            (
                "C:\\Music\\Drum and Bass\\file.flac",
                ("C:", "Music", "Drum and Bass", "file.flac"),
            ),
            (
                "D:/file.flac",
                ("D:", "file.flac"),
            ),
            (
                PureWindowsPath("E:/Music/Drum and Bass/file.flac"),
                ("E:", "Music", "Drum and Bass", "file.flac"),
            ),
            (
                Path("F:/Music/Drum and Bass/file.flac"),
                ("F:", "Music", "Drum and Bass", "file.flac"),
            ),
        ],
    )
    def test_from_path_windows(self, path, expected_parts):
        tp = NMLPath.from_path(path)
        assert tp.os == "windows"
        assert tp.volume is not None
        assert tp.directories is not None
        assert tp.file is not None
        assert tp.parts == list(expected_parts)
        assert isinstance(tp.pure_path, PureWindowsPath)

        assert str(tp.pure_path).startswith(tp.volume)
        # windows uses backslashes in the pure path representation,
        # independent of how we created our TraktorPath
        assert str(tp.pure_path) == "\\".join(tp.parts)

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
            NMLPath.from_path(path)

    def test_from_nml_location(self, collection):
        # Get a track from the collection
        for track in collection.tracks:
            loc = track.entry.find("LOCATION")
            NMLPath.from_nml_location(loc)

    def test_directory_structure(self):
        # Test the directory structure of a valid TraktorPath
        valid_path = NMLPath("C:/:foo/:bar/:baz/:file.flac")
        assert valid_path.parts == ["C:", "foo", "bar", "baz", "file.flac"]
        assert valid_path.volume == "C:"
        assert valid_path.directories == "/:foo/:bar/:baz/:"
        assert valid_path.file == "file.flac"

    def test_to_nml_location_standalone(self):
        path = NMLPath("D:/:SYNC/:library/:Artist/:Track.flac")
        loc = path.to_nml_location()

        assert loc.tag == "LOCATION"
        assert loc.get("DIR") == "/:SYNC/:library/:Artist/:"
        assert loc.get("FILE") == "Track.flac"
        assert loc.get("VOLUME") == "D:"
        assert loc.get("VOLUMEID") == "D:"

    def test_to_nml_location_with_parent(self):
        path = NMLPath("Macintosh HD/:Users/:paul/:Music/:track.mp3")
        parent = Element("ENTRY")

        loc = path.to_nml_location(parent)

        assert loc.getparent() is parent
        assert parent.find("LOCATION") is loc
        assert loc.get("DIR") == "/:Users/:paul/:Music/:"
        assert loc.get("FILE") == "track.mp3"
        assert loc.get("VOLUME") == "Macintosh HD"
        assert loc.get("VOLUMEID") == "Macintosh HD"

    @pytest.mark.parametrize(
        ("volume", "volume_id"),
        [
            ("D:", "D:"),  # volume id matches volume
            ("D:", "6580a7aa"),  # volume id differs from volume
        ],
        # This should take decent care of volume id to volume consistency.
        # However, it does not cover the case where we create Library entries from
        # Playlist tracks (for the latter we have no volume ids)
    )
    def test_to_nml_location_roundtrip_volume_and_volumeid(self, volume, volume_id):
        loc = Element("LOCATION")
        loc.set("DIR", "/:SYNC/:library/:Artist/:")
        loc.set("FILE", "Track.flac")
        loc.set("VOLUME", volume)
        loc.set("VOLUMEID", volume_id)

        path = NMLPath.from_nml_location(loc)
        serialized = path.to_nml_location()

        assert serialized.get("DIR") == loc.get("DIR")
        assert serialized.get("FILE") == loc.get("FILE")
        assert serialized.get("VOLUME") == loc.get("VOLUME")
        assert serialized.get("VOLUMEID") == loc.get("VOLUMEID")
