from pathlib import Path
from collections.abc import Iterable

import pytest
from plistsync.services.plex.playlist import PlexPlaylist
from plistsync.services.plex.track import PlexTrack
from tests.abc.collection import CollectionTestBase, LibraryCollectionTestBase

from plistsync.services.plex import PlexLibrary


class TestPlexPlaylist(CollectionTestBase):
    collection_class = PlexPlaylist

    library_collection: PlexLibrary

    @pytest.fixture(autouse=True)
    def setup(self, plex_library_collection_mock, playlist_data):
        self.library_collection = plex_library_collection_mock
        self.playlist_data = playlist_data

    def create_collection(self) -> Iterable[PlexPlaylist]:
        """Create a PlexLibrary for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pl = PlexPlaylist(
            library=self.library_collection,
            data=self.playlist_data,
        )
        pl.tracks = [
            PlexTrack({"ratingKey": "10637"}),
        ]
        yield pl

    def create_sample_track(self):
        """Create a sample track for testing matches within collections.

        This has to be implemented by the subclass and be a valid Track in the
        collection!
        """
        for collection in self.create_collection():
            for track in collection.tracks:
                return track
        raise RuntimeError("No track found in created collection")


class TestPlexLibrary(LibraryCollectionTestBase):
    collection_class = PlexLibrary

    @pytest.fixture(autouse=True)
    def setup(self, plex_library_collection_mock):
        self.collection = plex_library_collection_mock

    def create_collection(self, *args, **kwargs):
        """Create a PlexLibrary for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        yield self.collection

    def create_sample_track(self):
        """Create a sample track for testing matches within collections.

        This has to be implemented by the subclass and be a valid Track in the
        collection!
        """
        for library_collection in self.create_collection():
            for track in library_collection.tracks:
                return track
        raise RuntimeError("No track found in created collection")

    @property
    def known_playlists(self) -> list[tuple[str, str]]:
        return [
            ("name", "Test Playlist"),
        ]

    @property
    def unknown_playlists(self) -> list[tuple[str, str]]:
        return [
            ("name", "Unknown Playlist"),
            ("name", "Another Unknown Playlist"),
        ]

    def test_preload(self):
        """Test that preloading the library collection works."""
        library = self.collection
        assert isinstance(library, PlexLibrary)
        library.preload()
        assert library._fetched is True, (
            "Library collection should be marked as fetched after preload()"
        )
        assert library._tracks is not None, (
            "Library collection should have tracks loaded after preload()"
        )

        tracks = list(library.tracks)
        assert len(tracks) > 0, "Library collection should yield tracks after preload()"

    def test_locations_property(self):
        """Test that the locations property returns the expected results."""
        locations = self.collection.locations
        assert isinstance(locations, Iterable), "Locations should be iterable"
        assert len(list(locations)) > 0, "Locations should not be empty"
        assert all(isinstance(loc, Path) for loc in locations), (
            "All locations should be Path instances"
        )

    def test_get_playlist_raise(self):
        """Get playlist via path not allowed."""
        with pytest.raises(ValueError):
            self.collection.get_playlist(name="foo", id=121)

    @pytest.mark.parametrize(
        ("info", "expected_titles", "expected_call"),
        [
            (
                {
                    "title": "Test Track",
                    "artists": ["Test Original Title"],
                    "albums": ["Test Album"],
                },
                ["Test Track"],
                {
                    "title": "Test Track",
                    "artist": "Test Original Title",
                    "album": "Test Album",
                },
            ),
            (
                {"title": "Test Track", "artists": ["Test Artist"]},
                ["Test Track"],
                {"title": "Test Track", "artist": "Test Artist", "album": None},
            ),
            (
                {"artists": ["Test Artist"]},
                ["Test Track"],
                {"title": None, "artist": "Test Artist", "album": None},
            ),
        ],
    )
    def test_find_by_info(self, info, expected_titles, expected_call):
        """Find tracks through the server-side media query filter."""
        library = self.collection
        library.api.track.fetch_tracks_by_info.return_value = [
            library.api.track.fetch_tracks.return_value[0]
        ]

        tracks = list(library.find_by_info(info))

        assert [track.title for track in tracks] == expected_titles
        library.api.track.fetch_tracks_by_info.assert_called_once_with(
            section_id=library.id, **expected_call
        )

    @pytest.mark.parametrize(
        ("info", "expected_titles"),
        [
            ({"title": "Test Track", "albums": ["Test Album"]}, ["Test Track"]),
            ({"title": "Test Track", "artists": ["Someone Else"]}, []),
        ],
    )
    def test_find_by_info_uses_cached_tracks(self, info, expected_titles):
        """After iterating, the in-memory tracks are matched without a request."""
        library = self.collection
        library.preload()

        tracks = list(library.find_by_info(info))

        assert [track.title for track in tracks] == expected_titles
        library.api.track.fetch_tracks_by_info.assert_not_called()

    def test_find_by_info_requires_metadata(self):
        with pytest.raises(ValueError, match="at least one"):
            self.collection.find_by_info({})
