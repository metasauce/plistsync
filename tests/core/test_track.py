import pytest
from pathlib import PurePath

from plistsync.core.ids import FilePath, ISRC
from plistsync.core.track import OfflineTrack, Track
from tests.abc.tracks import TestTrack
from .mock_track import MockTrack


class TestMockTrack(TestTrack):
    """Test suite for the Track abstract class and its implementations."""

    def create_track(self, *args, **kwargs) -> MockTrack:
        return MockTrack(*args, **kwargs)

    def test_track_abstract_class_cannot_be_instantiated(self):
        """Test that Track abstract class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Track()  # type: ignore

    def test_property_track_info(self):
        """Test the info property returns correct TrackInfo."""
        track = MockTrack(
            title="Test Title",
            artists=["Artist 1", "Artist 2"],
            albums=["Album 1"],
        )
        info = track.info
        assert isinstance(info, dict)
        assert info.get("title") == "Test Title"
        assert info.get("artists") == ["Artist 1", "Artist 2"]
        assert info.get("albums") == ["Album 1"]

    def test_ids_property(self):
        """Test the ids property."""
        ids = {ISRC("USRC17607839"), FilePath(PurePath("/music/song.mp3"))}
        track = MockTrack(ids=ids)
        assert len(track.ids) == 2
        assert any(isinstance(t, ISRC) and t.id == "USRC17607839" for t in track.ids)
        assert any(
            isinstance(t, FilePath) and t.path == PurePath("/music/song.mp3")
            for t in track.ids
        )

    def test_convenience_getters(self):
        """Test the convenience getter properties."""
        track = MockTrack(
            title="My Song",
            artists=["Main Artist", "Feat Artist"],
            albums=["Album A", "Album B"],
            ids={ISRC("USRC12345678"), FilePath(PurePath("/path/to/song.mp3"))},
        )
        assert track.title == "My Song"
        assert track.artists == ["Main Artist", "Feat Artist"]
        assert track.albums == ["Album A", "Album B"]
        assert track.path == PurePath("/path/to/song.mp3")
        assert track.isrc == "USRC12345678"
        assert track.primary_artist == "Main Artist"

    def test_convenience_getters_with_missing_data(self):
        """Test convenience getters when data is missing."""
        track = MockTrack(title="", artists=[], albums=[], ids=set())
        assert track.title == ""
        assert track.artists == []
        assert track.albums == []
        assert track.path is None
        assert track.isrc is None
        assert track.primary_artist is None

    def test_track_with_multiple_artists_and_albums(self):
        """Test track with multiple artists and albums."""
        track = MockTrack(
            title="Collaboration",
            artists=["Artist 1", "Artist 2", "Artist 3"],
            albums=["Original Album", "Greatest Hits", "Remix Album"],
        )
        assert len(track.artists) == 3
        assert track.artists[0] == "Artist 1"
        assert track.artists[1] == "Artist 2"
        assert track.artists[2] == "Artist 3"
        assert len(track.albums) == 3
        assert "Greatest Hits" in track.albums
        assert track.primary_artist == "Artist 1"

    @pytest.mark.parametrize(
        "ids,expected",
        [
            ({FilePath(PurePath("/music/track.flac"))}, PurePath("/music/track.flac")),
            (set(), None),
        ],
    )
    def test_track_path_property(self, ids, expected):
        """Test the path property."""
        track = MockTrack(ids=ids)
        assert track.path == expected

    @pytest.mark.parametrize(
        "ids,expected",
        [
            ({ISRC("GBARL2000789")}, "GBARL2000789"),
            (set(), None),
        ],
    )
    def test_track_isrc_property(self, ids, expected):
        """Test the isrc property."""
        track = MockTrack(ids=ids)
        assert track.isrc == expected

    @pytest.mark.parametrize(
        "artists,expected_primary",
        [
            (["Solo Artist"], "Solo Artist"),
            (["Main", "Feature"], "Main"),
            ([], None),
            ([""], ""),
        ],
    )
    def test_primary_artist_various_cases(self, artists, expected_primary):
        """Test primary_artist with various artist configurations."""
        track = MockTrack(artists=artists)
        assert track.primary_artist == expected_primary

    @pytest.mark.parametrize(
        ["title", "artists", "expected_repr"],
        [
            ("Song", ["Artist"], "Track(artist='Artist', title='Song')"),
            ("Song", [], "Track(artist='?', title='Song')"),
            ("", ["Artist"], "Track(artist='Artist', title='?')"),
            ("", [], "Track(artist='?', title='?')"),
            (None, [], "Track(artist='?', title='?')"),
        ],
    )
    def test_repr(self, title, artists, expected_repr):
        """Test the string representation of a track."""
        repr_str = repr(MockTrack(title=title, artists=artists))
        assert expected_repr in repr_str


class TestTrackDiffs:
    """Tests equality for different tracks."""

    def test_track_diff_identical_tracks(self):
        """Test diff method with identical tracks."""
        ids = {ISRC("same123"), FilePath(PurePath("/same/path.mp3"))}
        track1 = MockTrack(
            title="Same Song",
            artists=["Same Artist"],
            ids=ids,
        )
        track2 = MockTrack(
            title="Same Song",
            artists=["Same Artist"],
            ids=ids,
        )
        diffs = track1.diff(track2)
        assert diffs == {}

    def test_track_diff_different_tracks(self):
        """Test diff method with different tracks."""
        track1 = MockTrack(
            title="Song A",
            artists=["Artist A"],
            ids={ISRC("ISRC123"), FilePath(PurePath("/path/a.mp3"))},
        )
        track2 = MockTrack(
            title="Song B",
            artists=["Artist B"],
            ids={ISRC("ISRC456"), FilePath(PurePath("/path/b.mp3"))},
        )
        diffs = track1.diff(track2)
        assert "info.title" in diffs
        assert diffs["info.title"] == ("Song A", "Song B")
        assert "info.artists" in diffs
        assert diffs["info.artists"] == (["Artist A"], ["Artist B"])
        assert "ids" in diffs
        only_in_1, only_in_2 = diffs["ids"]
        assert "isrc:ISRC123" in only_in_1
        assert "isrc:ISRC456" in only_in_2
        assert "file:/path/a.mp3" in only_in_1
        assert "file:/path/b.mp3" in only_in_2

    def test_track_diff_partial_data(self):
        """Test diff method when tracks have partial data."""
        track1 = MockTrack(
            title="Song",
            artists=["Artist"],
            ids={ISRC("ISRC123"), FilePath(PurePath("/path.mp3"))},
        )
        track2 = MockTrack(
            title="Song",
            artists=["Artist"],
            ids={FilePath(PurePath("/other.mp3"))},
        )
        diffs = track1.diff(track2)
        assert "ids" in diffs
        only_in_1, only_in_2 = diffs["ids"]
        assert "isrc:ISRC123" in only_in_1
        assert "file:/path.mp3" in only_in_1
        assert "file:/other.mp3" in only_in_2


class TestOfflineTrack:
    def test_merge(self):
        """Test that the OfflinePlaylist merge works as expected"""
        track1 = OfflineTrack(
            info={"title": "Title"},
            ids={ISRC("ISRC123")},
        )
        track2 = OfflineTrack(
            info={"artists": ["Artist"], "title": "Title2"},
            ids={FilePath(PurePath("/path.mp3"))},
        )
        merged = track1.merge(track2)
        assert merged.artists == ["Artist"]
        assert merged.path == PurePath("/path.mp3")
        assert merged.isrc == "ISRC123"
        assert merged.title == "Title2"  # Precedence of merged track's info
