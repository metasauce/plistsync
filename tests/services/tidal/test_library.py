"""Tests for TidalLibrary, including InfoLookup (find_by_info)."""

from unittest.mock import MagicMock, patch

import pytest

from plistsync.core.track import TrackInfo
from plistsync.services.tidal.api_types import (
    LinkObject,
    MultiRelationshipDataDocument,
    ResourceIdentifier,
    TrackAttributes,
    TrackResource,
)
from plistsync.services.tidal.library import TidalLibrary
from plistsync.services.tidal.track import TidalTrack


class TestTidalLibraryFindByInfo:
    """Tests for the find_by_info InfoLookup method."""

    @pytest.fixture
    def library(self) -> TidalLibrary:
        """Create a TidalLibrary with mocked API."""
        with patch.object(TidalLibrary, "__init__", lambda self: None):
            lib = TidalLibrary()
        lib.api = MagicMock()
        return lib

    def test_find_by_info_with_title_only(self, library):
        """Test searching by track title only."""
        library.api.tracks.search.return_value = []

        info = TrackInfo(title="Stairway to Heaven")
        results = list(library.find_by_info(info))

        library.api.tracks.search.assert_called_once_with("Stairway to Heaven")
        assert results == []

    def test_find_by_info_with_all_fields(self, library):
        """Test searching with title, artist, and album."""
        library.api.tracks.search.return_value = []

        info = TrackInfo(
            title="Stairway to Heaven",
            artists=["Led Zeppelin"],
            albums=["Led Zeppelin IV"],
        )
        results = list(library.find_by_info(info))

        library.api.tracks.search.assert_called_once_with(
            "Stairway to Heaven Led Zeppelin Led Zeppelin IV"
        )
        assert results == []

    def test_find_by_info_returns_tracks(self, library):
        """Test that results are converted to TidalTrack instances."""
        track_resource = TrackResource(
            id="track-001",
            type="TRACKS",
            attributes=TrackAttributes(
                title="Stairway to Heaven",
                duration=482000,
                explicit=False,
                isrc="GBUM71002904",
                bpm=82.5,
                key="E",
                keyScale="MAJOR",
                mediaTags=["LOSSLESS"],
                popularity=0.95,
                externalLinks=[],
            ),
            relationships={
                "albums": MultiRelationshipDataDocument(
                    data=[ResourceIdentifier(id="album-001", type="ALBUMS")],
                    links=LinkObject(),
                ),
                "artists": MultiRelationshipDataDocument(
                    data=[ResourceIdentifier(id="artist-001", type="ARTISTS")],
                    links=LinkObject(),
                ),
                "credits": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "genres": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "lyrics": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "owners": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "providers": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "radio": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "shares": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "similarTracks": MultiRelationshipDataDocument(data=[], links=LinkObject()),
                "replacement": {"data": {"id": "", "type": ""}},
                "sourceFile": {"data": {"id": "", "type": ""}},
                "trackStatistics": {"data": {"id": "", "type": ""}},
            },
        )
        lookup = {
            ("ALBUMS", "album-001"): {
                "id": "album-001",
                "type": "ALBUMS",
                "attributes": {"title": "Led Zeppelin IV"},
            },
            ("ARTISTS", "artist-001"): {
                "id": "artist-001",
                "type": "ARTISTS",
                "attributes": {"name": "Led Zeppelin"},
            },
        }
        library.api.tracks.search.return_value = [(track_resource, lookup)]

        info = TrackInfo(title="Stairway to Heaven")
        results = list(library.find_by_info(info))

        assert len(results) == 1
        assert isinstance(results[0], TidalTrack)
        assert results[0].id == "track-001"
        assert results[0].info["title"] == "Stairway to Heaven"

    def test_find_by_info_no_title_or_artists(self, library):
        """Test searching with empty info."""
        library.api.tracks.search.return_value = []

        info = TrackInfo()
        results = list(library.find_by_info(info))

        library.api.tracks.search.assert_not_called()
        assert results == []

    def test_find_by_info_multiple_artists_uses_first(self, library):
        """Test that only the first artist is used for search."""
        library.api.tracks.search.return_value = []

        info = TrackInfo(
            title="Song",
            artists=["Artist A", "Artist B"],
        )
        list(library.find_by_info(info))

        library.api.tracks.search.assert_called_once_with("Song Artist A")

    def test_find_by_info_multiple_albums_uses_first(self, library):
        """Test that only the first album is used for search."""
        library.api.tracks.search.return_value = []

        info = TrackInfo(
            title="Song",
            albums=["Album A", "Album B"],
        )
        list(library.find_by_info(info))

        library.api.tracks.search.assert_called_once_with("Song Album A")

