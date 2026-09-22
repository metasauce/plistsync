"""Tests for service playlist and track search commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer._click._compat import strip_ansi

from tests.cli.playlist.conftest import (  # noqa: F401
    _mock_library,
    app,
    playlist,
    playlist_search,
    search_playlist,
    search_track,
)
from tests.core.mock_collections import MockLibrary

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


class TestPlaylistSearch:
    """``plistsync <service> search playlist`` and its alias."""

    def test_searches_by_name_pattern(
        self,
        search_playlist: Invoke,  # noqa: F811
        playlist: MockServicePlaylist,  # noqa: F811
    ) -> None:
        result = search_playlist(["--name", "Party"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output
        assert playlist.id.serial in output

    def test_searches_by_description_pattern(
        self,
        search_playlist: Invoke,  # noqa: F811
        playlist: MockServicePlaylist,  # noqa: F811
    ) -> None:
        result = search_playlist(["--description", "Chill"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output

    def test_searches_by_id(
        self,
        search_playlist: Invoke,  # noqa: F811
        playlist: MockServicePlaylist,  # noqa: F811
    ) -> None:
        result = search_playlist(["--id", playlist.id.serial])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output

    def test_id_and_pattern_matches_are_combined(
        self,
        search_playlist: Invoke,  # noqa: F811
        playlist: MockServicePlaylist,  # noqa: F811
    ) -> None:
        other = MockLibrary().create_playlist("Work Mix", description="Focus")

        result = search_playlist(["--id", playlist.id.serial, "--name", "Work"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output
        assert "Work Mix" in output
        assert output.count("test:playlist:") == 2
        assert other.id.serial in output

    def test_playlist_search_alias(
        self,
        playlist_search: Invoke,  # noqa: F811
        playlist: MockServicePlaylist,  # noqa: F811
    ) -> None:
        result = playlist_search(["--name", "Party"])

        assert result.exit_code == 0, result.output
        assert "Party Mix" in strip_ansi(result.output)

    def test_help_when_no_criterion(self, search_playlist: Invoke) -> None:  # noqa: F811
        result = search_playlist()

        assert result.exit_code == 2, result.output
        assert "Usage:" in strip_ansi(result.output)


class TestTrackSearch:
    """``plistsync <service> search track``."""

    def test_searches_by_isrc(self, search_track: Invoke) -> None:  # noqa: F811
        result = search_track(["--isrc", "USRC17607839"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Found by id" in output
        assert "USRC17607839" in output

    def test_id_options_are_visible(self, search_track: Invoke) -> None:  # noqa: F811
        result = search_track(["--help"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "--isrc" in output
        assert "--max-results" in output
