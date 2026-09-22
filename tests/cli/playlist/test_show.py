"""Tests for ``plistsync <service> playlist show``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer._click._compat import strip_ansi

from plistsync.core.ids import ISRC
from plistsync.core.track import OfflineTrack, TrackInfo

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


class TestShow:
    def test_shows_name_description_and_track_count(
        self, show: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = show("Party Mix")
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output
        assert "Chill" in output
        assert "Tracks" in output

    def test_lists_tracks(self, show: Invoke, playlist: MockServicePlaylist) -> None:
        playlist.tracks = [
            OfflineTrack(
                TrackInfo(title="Found by id", artists=["Artist"]),
                ids={ISRC("USRC17607839")},
            )
        ]

        result = show("Party Mix")
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Found by id" in output
        assert "Artist" in output
        assert "USRC17607839" in output

    def test_shows_by_serial(self, show: Invoke, playlist: MockServicePlaylist) -> None:
        result = show(playlist.id.serial)
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output

    def test_unknown_playlist_fails(self, show: Invoke) -> None:
        result = show("No Such Mix")

        assert result.exit_code != 0
        assert "No playlist found matching" in strip_ansi(result.output)
