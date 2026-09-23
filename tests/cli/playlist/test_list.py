"""Tests for ``plistsync <service> playlist list``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer._click._compat import strip_ansi

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


class TestList:
    """``plistsync <service> playlist list``."""

    def test_lists_name_description_and_serial(
        self, list_playlists: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = list_playlists()
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output
        assert "Chill" in output
        assert playlist.id.serial in output

    def test_empty_library_message(self, list_playlists: Invoke) -> None:
        result = list_playlists()

        assert result.exit_code == 0, result.output
        assert "No playlists found" in strip_ansi(result.output)
