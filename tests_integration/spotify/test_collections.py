"""Live Spotify collections scenario."""

from __future__ import annotations

from tests_integration.abc import CollectionsTestBase


class TestSpotifyCollections(CollectionsTestBase):
    """Runs the shared, ordered collections scenario against Spotify."""

    # Spotify removes playlists from the library instead of deleting them.
    deletes_playlist = False
