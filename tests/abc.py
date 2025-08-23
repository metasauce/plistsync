import pytest
from pathlib import Path
from typing import Generator
from abc import ABC, abstractmethod

from plistsync.core import Track


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
                assert isinstance(track.path, Path), "Path should be a Path object"
            else:
                with pytest.raises(NotImplementedError):
                    track.path
