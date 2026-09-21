"""Tests for ``plistsync <service> playlist remove``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer._click._compat import strip_ansi

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


class TestRemove:
    """``plistsync <service> playlist remove``."""

    def test_help_lists_yes(self, remove: Invoke) -> None:
        result = remove(["--help"])

        assert result.exit_code == 0
        assert "--yes" in strip_ansi(result.output)
        assert "-y" in strip_ansi(result.output)

    def test_removes_by_name(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove(["Party Mix", "-y"])

        assert result.exit_code == 0, result.output
        assert "Removed playlist 'Party Mix'" in strip_ansi(result.output)
        assert ("remote_delete",) in playlist.log

    def test_removes_by_serial(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove([playlist.id.serial, "-y"])

        assert result.exit_code == 0, result.output
        assert ("remote_delete",) in playlist.log

    def test_confirmation_aborts(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove(["Party Mix"], "n\n")

        assert result.exit_code != 0
        assert "Aborted" in strip_ansi(result.output)
        assert ("remote_delete",) not in playlist.log

    def test_unknown_playlist_fails(self, remove: Invoke) -> None:
        result = remove(["nope", "-y"])

        assert result.exit_code != 0
        assert "No playlist found" in strip_ansi(result.output)
