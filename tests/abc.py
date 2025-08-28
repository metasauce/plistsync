import pytest
from pathlib import Path, PurePath
from typing import Generator
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


class TrackTestBase(ABC):
    """Base class for testing tracks.

    Implements some basic tests for tracks which should be the same for all tracks.
    """

    track_class: type[Track]

    test_config = {
        "has_path": False,
    }

    @abstractmethod
    def create_track(self, *args, **kwargs) -> Generator[Track, None, None]:
        """Create a track for testing.

        This method should create a track with some dummy data. Has to be implemented by the subclass.
        """
        pass

    # ---------------------------------------------------------------------------- #
    #                             Test abstract methods                            #
    # ---------------------------------------------------------------------------- #

    def test_title(self):
        for track in self.create_track():
            assert isinstance(track.title, str), "Title should be a string"

    def test_artists(self):
        for track in self.create_track():
            assert isinstance(track.artists, list), "Artists should be a list"

    def test_albums(self):
        for track in self.create_track():
            assert isinstance(track.albums, list), "Albums should be a list"

    def test_identifiers(self):
        for track in self.create_track():
            assert isinstance(track.global_ids, dict), "Identifiers should be a dict"

    # ---------------------------------------------------------------------------- #
    #                              Test Common methods                             #
    # ---------------------------------------------------------------------------- #

    def test_isrc(self):
        for track in self.create_track():
            assert isinstance(track.isrc, (str, type(None))), (
                "ISRC should be a string or None"
            )

    def test_primary_artist(self):
        for track in self.create_track():
            assert isinstance(track.primary_artist, (str, type(None))), (
                "Primary artist should be a string or None"
            )

    # ---------------------------------------------------------------------------- #

    def test_path(self):
        for track in self.create_track():
            if self.test_config["has_path"]:
                assert isinstance(track.path, PurePath), "Path should be a Path object"
            else:
                with pytest.raises(NotImplementedError):
                    track.path


class CollectionTestBase(ABC):
    """Base class for testing collections.

    Implements some basic tests for collections that should be the same for all types of collections.
    """

    collection_class: type[Collection]

    @abstractmethod
    def create_collection(self, *args, **kwargs) -> Generator[Collection, None, None]:
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
                tracks = list(collection)
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
    def create_collection(
        self, *args, **kwargs
    ) -> Generator[LibraryCollection, None, None]:
        """Create a collection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pass

    @property
    @abstractmethod
    def known_playlist_names(self) -> Iterable[str | Path]:
        pass

    @property
    @abstractmethod
    def unknown_playlist_names(self) -> Iterable[str | Path]:
        pass

    def test_playlists_property(self):
        """Test that the playlists property returns the expected results."""
        for library_collection in self.create_collection():
            playlists = library_collection.playlists
            assert isinstance(playlists, Iterable), "Playlists should be iterable"
            # Optionally: further assertions based on expected behavior, e.g., length, types

    def test_get_playlist_known(self):
        """Test retrieval of playlists by name or identifier."""
        for library_collection in self.create_collection():
            for known_playlist_name in self.known_playlist_names:
                playlist = library_collection.get_playlist(known_playlist_name)
                assert playlist is not None, "Known playlist should be found"

    def test_get_playlist_unknown(self):
        """Test retrieval of unknown playlists by name or identifier."""
        for library_collection in self.create_collection():
            for unknown_playlist_name in self.unknown_playlist_names:
                playlist = library_collection.get_playlist(unknown_playlist_name)
                assert playlist is None, "Unknown playlist should not be found"
