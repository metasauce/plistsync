import pytest
from typing import Any, ClassVar
from abc import ABC, abstractmethod

from plistsync.core import LibraryCollection, Track, Collection
from plistsync.core.collection import (
    GlobalLookup,
    InfoLookup,
    Iterable,
    LocalLookup,
    TrackStream,
)
from plistsync.core.matching import Matches
from plistsync.core.playlist import (
    PlaylistCollection,
)


class CollectionTestBase(ABC):
    """Base class for testing collections.

    Implements some basic tests for collections that should be the same for all types of collections.
    """

    collection_class: ClassVar[type[Collection]]

    @abstractmethod
    def create_collection(self, *args, **kwargs) -> Iterable[Collection]:
        """Create a collection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pass

    @abstractmethod
    def create_sample_track(self) -> Track:
        """Create a sample track for testing matches within collections.
        This has to be implemented by the subclass and be a valid Track in the
        collection!
        """
        pass

    def test_global_lookup(self):
        """Test collections that implement GlobalLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, GlobalLookup):
                found_track = collection.find_by_global_ids(track.global_ids)
                # assumptions on the track returned by global id lookup
                assert found_track is None or found_track == track, (
                    "Global lookup should return the matching track or None"
                )

    def test_local_lookup(self):
        """Test collections that implement LocalLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, LocalLookup):
                found_track = collection.find_by_local_ids(track.local_ids)
                # assumptions on the track returned by local id lookup
                # TODO PS@semohr how do we want to decide that "they are equal"?
                assert found_track is None or found_track.diff(track) == {}, (
                    "Local lookup should return the matching track or None"
                )

    def test_info_lookup(self):
        """Test collections that implement InfoLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, InfoLookup):
                found_tracks = list(collection.find_by_info(track.info))
                # assumptions on the track returned by info lookup
                assert all(isinstance(t, Track) for t in found_tracks), (
                    "Info lookup should return iterable of Track instances"
                )

    def test_track_stream(self):
        """Test collections that implement TrackStream."""
        for collection in self.create_collection():
            if isinstance(collection, TrackStream):
                tracks = list(collection.tracks)
                # assumptions on the track returned by track stream
                assert all(isinstance(t, Track) for t in tracks), (
                    "Track Stream should return iterable over Track instances"
                )

    def test_match_method(self):
        """Test the collection's match method."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            matches = collection.match(track)
            assert isinstance(matches, Matches), (
                "Match method should return Matches instance"
            )
            # Further tests could include verifying the contents of Matches


class LibraryCollectionTestBase(CollectionTestBase, ABC):
    @abstractmethod
    def create_collection(self, *args, **kwargs) -> Iterable[LibraryCollection]:
        """Create a collection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pass

    @property
    @abstractmethod
    def known_playlists(self) -> Iterable[tuple[str, Any]]:
        """Know playlist for lookup by [key, value].

        E.g. ["uri", "spotify:asdasdasd"]
        will call get_playlist(uri="spotify:asdasdasd")
        """
        pass

    @property
    @abstractmethod
    def unknown_playlists(self) -> Iterable[tuple[str, Any]]:
        """Unknow playlist for lookup by [key, value].

        E.g. ["uri", "spotify:not_found"]
        will call get_playlist(uri="spotify:asdasdasd") -> check None
        and get_playlist_or_raise(uri="spotify:asdasdasd") -> check raises
        """

        pass

    def test_playlists_property(self):
        """Test that the playlists property returns the expected results."""
        for library_collection in self.create_collection():
            playlists = library_collection.playlists
            assert isinstance(playlists, Iterable), "Playlists should be iterable"
            # Optionally: further assertions based on expected behavior, e.g., length, types
            for pl in playlists:
                assert isinstance(pl, PlaylistCollection)

    def test_get_playlist_known(self):
        """Test retrieval of playlists by name or identifier."""
        for library_collection in self.create_collection():
            for key, identifier in self.known_playlists:
                playlist = library_collection.get_playlist(**{key: identifier})
                assert playlist is not None, "Known playlist should be found"

    def test_get_playlist_unknown(self):
        """Test retrieval of unknown playlists by name or identifier."""
        for library_collection in self.create_collection():
            for key, identifier in self.unknown_playlists:
                playlist = library_collection.get_playlist(**{key: identifier})
                assert playlist is None, "Unknown playlist should not be found"

                with pytest.raises(ValueError):
                    playlist = library_collection.get_playlist_or_raise(
                        **{key: identifier}
                    )
