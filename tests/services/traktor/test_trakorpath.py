import pytest
from pathlib import Path, PurePosixPath, PureWindowsPath
from plistsync.services.traktor.track import TraktorPath


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
        tp = TraktorPath.from_path(path)
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
        tp = TraktorPath.from_path(path)
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
            TraktorPath.from_path(path)

    def test_from_nml_location(self, collection):
        # Get a track from the collection
        for track in collection:
            loc = track.entry.find("LOCATION")
            TraktorPath.from_nml_location(loc)

    def test_directory_structure(self):
        # Test the directory structure of a valid TraktorPath
        valid_path = TraktorPath("C:/:foo/:bar/:baz/:file.flac")
        assert valid_path.parts == ["C:", "foo", "bar", "baz", "file.flac"]
        assert valid_path.volume == "C:"
        assert valid_path.directories == "/:foo/:bar/:baz/:"
        assert valid_path.file == "file.flac"
