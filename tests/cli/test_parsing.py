"""Tests for shared CLI argument and identifier helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plistsync.cli.parsing import (
    autocompletion_playlist,
    parse_playlist,
    parse_track_id,
)
from plistsync.core.ids import ISRC
from tests.core.mock_collections import MockLibrary

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.core.mock_playlist import MockServicePlaylist


@pytest.fixture
def library() -> Iterator[MockLibrary]:
    """An empty mock library, with its playlist state reset afterwards."""
    MockLibrary.created.clear()
    yield MockLibrary()
    MockLibrary.created.clear()


@pytest.fixture
def playlist(library: MockLibrary) -> MockServicePlaylist:
    """A playlist known to the mock library."""
    return library.create_playlist("Party Mix", description="Chill")


class TestParseTrackId:
    """``parse_track_id`` resolves track serials."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("isrc:USRC17607839", ISRC("USRC17607839")),
            ("USRC17607839", ISRC("USRC17607839")),
            ("not-a-track", None),
        ],
    )
    def test_parse(self, value: str, expected: ISRC | None) -> None:
        assert parse_track_id(value) == expected


class TestParsePlaylist:
    """``parse_playlist`` resolves playlists by name or serial."""

    def test_by_name(self, library: MockLibrary, playlist: MockServicePlaylist) -> None:
        assert parse_playlist("Party Mix", library) is playlist

    def test_by_serial(
        self, library: MockLibrary, playlist: MockServicePlaylist
    ) -> None:
        assert parse_playlist(playlist.id.serial, library) is playlist

    def test_not_found(self, library: MockLibrary) -> None:
        assert parse_playlist("nope", library) is None


class TestPlaylistAutocompletion:
    """``autocompletion_playlist`` suggests names and serials."""

    def test_lists_names_and_serials(
        self, library: MockLibrary, playlist: MockServicePlaylist
    ) -> None:
        assert autocompletion_playlist("", library) == [
            "Party Mix",
            playlist.id.serial,
        ]
        assert autocompletion_playlist("Party", library) == ["Party Mix"]
        assert autocompletion_playlist("test:playlist:", library) == [
            playlist.id.serial
        ]
        assert autocompletion_playlist("nope", library) == []
