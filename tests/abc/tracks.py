from abc import ABC, abstractmethod
from pathlib import PurePath

from plistsync.core.track import Track


class TestTrack(ABC):
    """Abstract base class for testing 'Track' implementations."""

    @abstractmethod
    def create_track(self, *args, **kwargs) -> Track:
        """Create a track for testing.

        This method should create a track with some dummy data. Has to be implemented by the subclass.
        """
        pass

    # --------------------------------- Contracts -------------------------------- #

    def test_property_info(self):
        track = self.create_track()
        assert isinstance(track.info, dict), "info should be a dict"

    def test_property_global_ids(self):
        track = self.create_track()
        assert isinstance(track.global_ids, dict), "global_ids should be a dict"

    def test_property_local_ids(self):
        track = self.create_track()
        assert isinstance(track.local_ids, dict), "local_ids should be a dict"

    # -------------------------- Derived from contracts -------------------------- #

    def test_property_title(self):
        track = self.create_track()
        assert isinstance(track.title, str), "Title should be a string"

    def test_property_artists(self):
        track = self.create_track()
        assert isinstance(track.artists, list), "Artists should be a list"

    def test_property_albums(self):
        track = self.create_track()
        assert isinstance(track.albums, list), "Albums should be a list"

    def test_property_isrc(self):
        track = self.create_track()
        assert isinstance(track.isrc, (str, type(None))), (
            "ISRC should be a string or None"
        )

    def test_property_primary_artist(self):
        track = self.create_track()
        assert isinstance(track.primary_artist, (str, type(None))), (
            "Primary artist should be a string or None"
        )

    def test_property_path(self):
        track = self.create_track()
        assert isinstance(track.path, (PurePath, type(None))), (
            "Path should be a PurePath or None"
        )
