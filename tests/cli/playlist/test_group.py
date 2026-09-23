"""Tests for the playlist command group wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.main import get_group

if TYPE_CHECKING:
    import typer
    from typer.testing import CliRunner

    from tests.core.mock_playlist import MockServicePlaylist


class TestPlaylistGroup:
    """``plistsync <service> playlist``."""

    def test_mounted_only_with_library(
        self, app: typer.Typer, no_library_app: typer.Typer
    ) -> None:
        group = get_group(app)

        assert set(group.commands) == {"playlist"}
        assert set(group.commands["playlist"].commands) == {
            "create",
            "remove",
            "rm",
            "list",
            "ls",
            "update",
            "show",
        }
        assert get_group(no_library_app).commands == {}

    def test_ls_alias(self, runner: CliRunner, app: typer.Typer) -> None:
        result = runner.invoke(app, ["playlist", "ls"])

        assert result.exit_code == 0, result.output

    def test_rm_alias(
        self, runner: CliRunner, app: typer.Typer, playlist: MockServicePlaylist
    ) -> None:
        result = runner.invoke(app, ["playlist", "rm", "Party Mix", "-y"])

        assert result.exit_code == 0, result.output
        assert ("remote_delete",) in playlist.log
