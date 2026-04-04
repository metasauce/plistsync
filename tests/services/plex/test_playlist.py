import pytest
from plistsync.services.plex.library import PlexLibrarySectionCollection
from plistsync.services.plex.playlist import PlexPlaylistCollection
from tests.abc.playlist import TestMultiRequestServicePlaylistBase


class TestPlexPlaylist(TestMultiRequestServicePlaylistBase):
    """Unit tests for the plex playlist collection."""

    @pytest.fixture(autouse=True)
    def setup(self, plex_library_collection_mock: PlexLibrarySectionCollection):
        self.library = plex_library_collection_mock

    def create_playlist(self) -> PlexPlaylistCollection:
        return PlexPlaylistCollection.create_new(
            "A name", "some description", None, self.library
        )

    # TODO: Add tests for remote_method implementations
