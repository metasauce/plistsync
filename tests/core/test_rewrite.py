import pytest
from pathlib import Path, PurePath
from plistsync.core.rewrite import PathRewrite


class TestPathRewrite:
    """Concise test suite for PathRewrite class."""

    @pytest.mark.parametrize(
        "old, new, test_path, expected",
        [
            # Basic rewrites
            ("/old", "/new", "/old/file.txt", "/new/file.txt"),
            (
                "/music/old",
                "/music/new",
                "/music/old/artist/song.mp3",
                "/music/new/artist/song.mp3",
            ),
            ("/a/b/c", "/x/y/z", "/a/b/c/d/e", "/x/y/z/d/e"),
            # Exact matches
            ("/music", "/audio", "/music", "/audio"),
            # No matches
            ("/old", "/new", "/other/file.txt", "/other/file.txt"),
            ("/music", "/audio", "/musical/show.mp3", "/musical/show.mp3"),
        ],
    )
    def test_apply(self, old, new, test_path, expected):
        """Test path rewriting with various scenarios."""
        rewrite = PathRewrite.from_str(old, new)
        result = rewrite.apply(PurePath(test_path))
        assert result == PurePath(expected)

    def test_invert(self):
        """Test rule inversion."""
        rewrite = PathRewrite.from_str("/old", "/new")
        inverted = rewrite.invert

        assert inverted.old == Path("/new")
        assert inverted.new == Path("/old")

        # Test round-trip
        assert inverted.invert == rewrite

    def test_apply_with_inverted(self):
        """Test applying inverted rule."""
        rewrite = PathRewrite.from_str("/source", "/dest").invert
        result = rewrite.apply(PurePath("/dest/file.txt"))
        assert result == PurePath("/source/file.txt")

    def test_immutable(self):
        """Test NamedTuple immutability."""
        rewrite = PathRewrite.from_str("/old", "/new")
        with pytest.raises(AttributeError):
            rewrite.old = Path("/changed")  # type: ignore

    def test_repr(self):
        rewrite = PathRewrite.from_str("/source", "/dest")
        repr_str = repr(rewrite)
        assert repr_str == "PathRewrite(old='/source', new='/dest')"
