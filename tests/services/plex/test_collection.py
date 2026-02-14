from pathlib import Path
from collections.abc import Iterable, Iterator

import pytest
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

    def test_insert_track_by_path(self, audio_files: Path):
        """Test inserting a track into a playlist by path."""
        for collection in self.create_collection():
            tracks = list(collection.tracks)
            track = tracks[0]
            len_before = len(tracks)
            assert track.path is not None, (
                "Track must have a valid path for this test to work"
            )
            # Insert the track into the playlist
            collection.insert_by_path(
                path=track.path,
                library=self.library_collection,
            )

            # Playlist should now contain an added track
            tracks_after = list(collection.tracks)
            assert len(tracks_after) == len_before + 1, (
                "Playlist should have one more track after insertion by path"
            )

    def test_insert_track_by_id(self, audio_files: Path):
        """Test inserting a track into a playlist by Plex ID."""
        for collection in self.create_collection():
            tracks = list(collection.tracks)
            track = tracks[0]
            len_before = len(tracks)

            # Insert the track into the playlist
            collection.insert_by_id(item_id=track.id)

            # Playlist should now contain an added track
            tracks_after = list(collection.tracks)
            assert len(tracks_after) == len_before + 1, (
                "Playlist should have one more track after insertion by ID"
            )

    def test_refresh(self):
        """Test that refreshing the playlist collection works."""
        for collection in self.create_collection():
            # Initially, the playlist should have no tracks
            collection._items_data = []

            collection.refresh()
            assert len(list(collection.tracks)) != 0, (
                "Playlist should have no tracks after refreshing empty data"
            )


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
            for track in library_collection:
                return track
        raise RuntimeError("No track found in created collection")

    @property
    def known_playlist_names(self) -> list[str]:
        return ["Test Playlist"]

    @property
    def unknown_playlist_names(self) -> list[str]:
        return ["Nonexistent Playlist", "Another Unknown Playlist"]

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
        tracks = list(library_collection)
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
                library_collection.get_playlist(Path("Some/Path/Playlist"))
