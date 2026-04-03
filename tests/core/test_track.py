import pytest
from pathlib import PurePath

from plistsync.core.track import Track, GlobalTrackIDs, LocalTrackIDs
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

    # TODO: The following tests need a bit of alignment with the base 'TestTrack'
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

    def test_global_ids_property(self):
        """Test the global_ids property."""
        global_ids: GlobalTrackIDs = {
            "tidal_id": "12345",
            "isrc": "USRC17607839",
            "spotify_id": "spotify:track:abc123",
        }
        track = MockTrack(global_ids=global_ids)
        assert track.global_ids.get("tidal_id") == "12345"
        assert track.global_ids.get("isrc") == "USRC17607839"
        assert track.global_ids.get("spotify_id") == "spotify:track:abc123"

    def test_local_ids_property(self):
        """Test the local_ids property."""
        local_ids: LocalTrackIDs = {
            "file_path": PurePath("/music/song.mp3"),
            "beets_id": 42,
            "plex_id": "plex://library/123",
        }
        track = MockTrack(local_ids=local_ids)

        assert track.local_ids.get("file_path") == PurePath("/music/song.mp3")
        assert track.local_ids.get("beets_id") == 42
        assert track.local_ids.get("plex_id") == "plex://library/123"

    def test_convenience_getters(self):
        """Test the convenience getter properties."""
        track = MockTrack(
            title="My Song",
            artists=["Main Artist", "Feat Artist"],
            albums=["Album A", "Album B"],
            global_ids={"isrc": "USRC12345678"},
            local_ids={"file_path": PurePath("/path/to/song.mp3")},
        )

        assert track.title == "My Song"
        assert track.artists == ["Main Artist", "Feat Artist"]
        assert track.albums == ["Album A", "Album B"]
        assert track.path == PurePath("/path/to/song.mp3")
        assert track.isrc == "USRC12345678"
        assert track.primary_artist == "Main Artist"

    def test_convenience_getters_with_missing_data(self):
        """Test convenience getters when data is missing."""
        track = MockTrack(title="", artists=[], albums=[], global_ids={}, local_ids={})

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
        "local_ids,expected",
        [
            (
                {"file_path": PurePath("/music/track.flac")},
                PurePath("/music/track.flac"),
            ),
            ({}, None),
        ],
    )
    def test_track_path_property(self, local_ids, expected):
        """Test the path property."""
        track = MockTrack(local_ids=local_ids)
        assert track.path == expected

    @pytest.mark.parametrize(
        "global_ids,expected",
        [
            ({"isrc": "GBARL2000789"}, "GBARL2000789"),
            ({}, None),
        ],
    )
    def test_track_isrc_property(self, global_ids, expected):
        """Test the isrc property."""
        track = MockTrack(global_ids=global_ids)
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
        track1 = MockTrack(
            title="Same Song",
            artists=["Same Artist"],
            global_ids={"isrc": "same123"},
            local_ids={"file_path": PurePath("/same/path.mp3")},
        )
        track2 = MockTrack(
            title="Same Song",
            artists=["Same Artist"],
            global_ids={"isrc": "same123"},
            local_ids={"file_path": PurePath("/same/path.mp3")},
        )

        diffs = track1.diff(track2)
        assert diffs == {}

    def test_track_diff_different_tracks(self):
        """Test diff method with different tracks."""
        track1 = MockTrack(
            title="Song A",
            artists=["Artist A"],
            global_ids={"isrc": "ISRC123"},
            local_ids={"file_path": PurePath("/path/a.mp3")},
        )
        track2 = MockTrack(
            title="Song B",
            artists=["Artist B"],
            global_ids={"isrc": "ISRC456"},
            local_ids={"file_path": PurePath("/path/b.mp3")},
        )

        diffs = track1.diff(track2)

        assert "info.title" in diffs
        assert diffs["info.title"] == ("Song A", "Song B")
        assert "info.artists" in diffs
        assert diffs["info.artists"] == (["Artist A"], ["Artist B"])
        assert "global_ids.isrc" in diffs
        assert diffs["global_ids.isrc"] == ("ISRC123", "ISRC456")
        assert "local_ids.file_path" in diffs
        assert diffs["local_ids.file_path"] == (
            PurePath("/path/a.mp3"),
            PurePath("/path/b.mp3"),
        )

    def test_track_diff_partial_data(self):
        """Test diff method when tracks have partial data."""
        track1 = MockTrack(
            title="Song",
            artists=["Artist"],
            global_ids={"isrc": "ISRC123"},  # has isrc but no spotify_id
            local_ids={
                "file_path": PurePath("/path.mp3")
            },  # has file_path but no beets_id
        )
        track2 = MockTrack(
            title="Song",
            artists=["Artist"],
            global_ids={"spotify_id": "spotify123"},  # has spotify_id but no isrc
            local_ids={"beets_id": 42},  # has beets_id but no file_path
        )

        diffs = track1.diff(track2)

        # Should show differences in global_ids and local_ids
        assert "global_ids.isrc" in diffs
        assert diffs["global_ids.isrc"] == ("ISRC123", None)
        assert "global_ids.spotify_id" in diffs
        assert diffs["global_ids.spotify_id"] == (None, "spotify123")
        assert "local_ids.file_path" in diffs
        assert diffs["local_ids.file_path"] == (PurePath("/path.mp3"), None)
        assert "local_ids.beets_id" in diffs
        assert diffs["local_ids.beets_id"] == (None, 42)
