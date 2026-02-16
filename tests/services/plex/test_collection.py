from pathlib import Path
from collections.abc import Iterable, Iterator

import pytest
from plistsync.services.plex.track import PlexTrack
from tests.abc import CollectionTestBase, LibraryCollectionTestBase

from plistsync.services.plex.collection import (
    PlexPlaylistCollection,
    PlexLibrarySectionCollection,
)


class TestPlexPlaylistCollection(CollectionTestBase):
    collection_class = PlexPlaylistCollection

    library_collection: PlexLibrarySectionCollection

    @pytest.fixture(autouse=True)
    def setup(self, plex_library_collection):
        self.library_collection = plex_library_collection

    def create_collection(self) -> Iterable[PlexPlaylistCollection]:
        """Create a PlexLibrarySectionCollection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        yield PlexPlaylistCollection(
            self.library_collection,
            "foo",
            tracks=[
                PlexTrack({"ratingKey": "10637"}),
            ],
        )

    def create_sample_track(self):
        """Create a sample track for testing matches within collections.

        This has to be implemented by the subclass and be a valid Track in the
        collection!
        """
        for collection in self.create_collection():
            for track in collection.tracks:
                return track
        raise RuntimeError("No track found in created collection")


class TestPlexLibrarySectionCollection(LibraryCollectionTestBase):
    collection_class = PlexLibrarySectionCollection

    @pytest.fixture(autouse=True)
    def setup(self, plex_library_collection):
        self.collection = plex_library_collection

    def create_collection(self) -> Iterator[PlexLibrarySectionCollection]:
        """Create a PlexLibrarySectionCollection for testing.

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
    def known_playlist_names(self) -> list[str]:
        return ["Test Playlist"]

    @property
    def unknown_playlist_names(self) -> list[str]:
        return ["Unknown Playlist", "Another Unknown Playlist"]

    def test_preload(self):
        """Test that preloading the library collection works."""
        library_collection: PlexLibrarySectionCollection = next(
            self.create_collection()
        )
        library_collection.preload()
        assert library_collection._fetched is True, (
            "Library collection should be marked as fetched after preload()"
        )
        assert library_collection._tracks is not None, (
            "Library collection should have tracks loaded after preload()"
        )

        # Iter should yield tracks after preload
        tracks = list(library_collection.tracks)
        assert len(tracks) > 0, "Library collection should yield tracks after preload()"

    def test_locations_property(self):
        """Test that the locations property returns the expected results."""
        for library_collection in self.create_collection():
            locations = library_collection.locations
            assert isinstance(locations, Iterable), "Locations should be iterable"
            assert len(locations) > 0, "Locations should not be empty"
            assert all(isinstance(loc, Path) for loc in locations), (
                "All locations should be Path instances"
            )

    def test_get_playlist_raise(self):
        """Get playlist via path not allowed."""
        with pytest.raises(ValueError):
            for library_collection in self.create_collection():
                library_collection.get_playlist(name="foo", id=121)  # type:ignore
