import pytest
from pathlib import PurePath

from plistsync.core.ids import TrackID, ISRC, FilePath


class TestISRC:
    """Tests for the ISRC identifier."""

    # -- parse ----------------------------------------------------------------

    @pytest.mark.parametrize(
        "input_value, expected_id",
        [
            ("USRC17607839", "USRC17607839"),
            ("isrc:USRC17607839", "USRC17607839"),
            ("ISRC:USRC17607839", "USRC17607839"),
            ("usrc17607839", "USRC17607839"),
            ("  USRC17607839  ", "USRC17607839"),
            ("  isrc:USRC17607839  ", "USRC17607839"),
        ],
    )
    def test_parse(self, input_value, expected_id):
        isrc = ISRC.parse(input_value)
        assert isrc.id == expected_id

    @pytest.mark.parametrize(
        "bad_input",
        [
            "bad",
            "USR",  # too short
            "USRC176078399",  # too long (13 chars)
            "USRC1760783",  # too short (11 chars)
            "12RC17607839",  # country code must be letters
            "USRC1760783A",  # last 7 must be digits
        ],
    )
    def test_parse_invalid_raises(self, bad_input):
        with pytest.raises(ValueError):
            ISRC.parse(bad_input)

    # -- serial ----------------------------------------------------------------

    def test_serial(self):
        assert ISRC("USRC17607839").serial == "isrc:USRC17607839"

    # -- str -------------------------------------------------------------------

    def test_str(self):
        assert str(ISRC("USRC17607839")) == "USRC17607839"

    # -- dataclass behaviour ---------------------------------------------------

    def test_equality(self):
        a = ISRC("USRC17607839")
        b = ISRC("USRC17607839")
        c = ISRC("GBARL2000789")
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_immutable(self):
        isrc = ISRC("USRC17607839")
        with pytest.raises(Exception):
            isrc.id = "GBARL2000789"  # type: ignore[misc]

    def test_repr(self):
        r = repr(ISRC("USRC17607839"))
        assert "ISRC" in r
        assert "USRC17607839" in r

    # -- subclass contract -----------------------------------------------------

    def test_is_track_id(self):
        assert issubclass(ISRC, TrackID)


class TestFilePath:
    """Tests for the FilePath identifier."""

    # -- parse ----------------------------------------------------------------

    @pytest.mark.parametrize(
        "input_value, expected_path",
        [
            ("/home/user/music/song.flac", PurePath("/home/user/music/song.flac")),
            ("file:/home/user/music/song.flac", PurePath("/home/user/music/song.flac")),
            ("FILE:/home/user/music/song.flac", PurePath("/home/user/music/song.flac")),
            ("  /home/user/music/song.flac  ", PurePath("/home/user/music/song.flac")),
            ("music/song.flac", PurePath("music/song.flac")),
        ],
    )
    def test_parse(self, input_value, expected_path):
        assert FilePath.parse(input_value).path == expected_path

    # -- serial ----------------------------------------------------------------

    @pytest.mark.parametrize(
        "path, expected_serial",
        [
            (PurePath("/home/user/music/song.flac"), "file:/home/user/music/song.flac"),
            (PurePath("music/song.flac"), "file:music/song.flac"),
        ],
    )
    def test_serial(self, path, expected_serial):
        assert FilePath(path).serial == expected_serial

    def test_serial_roundtrip(self):
        fp = FilePath.parse("/home/user/music/song.flac")
        assert FilePath.parse(fp.serial) == fp

    # -- str -------------------------------------------------------------------

    @pytest.mark.parametrize(
        "path, expected_str",
        [
            (PurePath("/home/user/music/song.flac"), "/home/user/music/song.flac"),
            (PurePath("music/song.flac"), "music/song.flac"),
        ],
    )
    def test_str(self, path, expected_str):
        assert str(FilePath(path)) == expected_str

    # -- dataclass behaviour ---------------------------------------------------

    def test_equality(self):
        a = FilePath(PurePath("/home/user/music/song.flac"))
        b = FilePath(PurePath("/home/user/music/song.flac"))
        c = FilePath(PurePath("/other/path.mp3"))
        assert a == b
        assert a != c
        assert hash(a) == hash(b)

    def test_immutable(self):
        fp = FilePath(PurePath("/home/user/music/song.flac"))
        with pytest.raises(Exception):
            fp.path = PurePath("/other")  # type: ignore[misc]

    def test_repr(self):
        r = repr(FilePath(PurePath("/home/user/music/song.flac")))
        assert "FilePath" in r
        assert "song.flac" in r

    # -- subclass contract -----------------------------------------------------

    def test_is_track_id(self):
        assert issubclass(FilePath, TrackID)
