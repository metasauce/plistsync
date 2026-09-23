"""Tests for ``plistsync <service> playlist update``."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from typer._click._compat import strip_ansi

from plistsync.core.ids import ISRC
from plistsync.core.track import OfflineTrack, TrackInfo
from tests.core.mock_collections import MockLibrary

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    from plistsync.core import TrackID
    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


def _track(title: str, *ids: TrackID) -> OfflineTrack:
    """An offline track with the given title and identifiers."""
    return OfflineTrack(TrackInfo(title=title, artists=["Artist"]), ids=ids)


def _prepare_update(playlist: MockServicePlaylist, *tracks: OfflineTrack) -> Mock:
    """Point the playlist at the mock library, set its tracks, mock the commit."""
    playlist.library = MockLibrary()
    playlist.tracks = list(tracks)
    playlist.update = Mock()  # type: ignore[method-assign]
    return playlist.update


class TestUpdate:
    """``plistsync <service> playlist update``."""

    @pytest.mark.parametrize("option", ["--add", "-a", "--remove", "-r", "--yes", "-y"])
    def test_help_lists_options(self, update: Invoke, option: str) -> None:
        result = update(["--help"])

        assert result.exit_code == 0
        assert option in strip_ansi(result.output)

    def test_confirmation_lists_removed(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        commit = _prepare_update(playlist, _track("Old One"), _track("Old Two"))

        result = update(["Party Mix", "--remove", "0"], "n\n")
        output = strip_ansi(result.output)

        assert result.exit_code != 0
        assert "removed" in output
        assert "Old One" in output
        # Only the changed tracks are shown, not the untouched ones.
        assert "Old Two" not in output
        assert "Continue?" in output
        assert "Aborted" in output
        commit.assert_not_called()

    def test_yes_skips_confirmation(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        commit = _prepare_update(playlist, _track("Old One"))

        result = update(["Party Mix", "--remove", "0", "-y"])

        assert result.exit_code == 0, result.output
        assert "Continue?" not in result.output
        assert "removed" not in result.output
        commit.assert_called_once()

    def test_no_changes_reports_none(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        commit = _prepare_update(playlist)

        result = update(["Party Mix"], "n\n")

        assert result.exit_code != 0
        assert "No track changes" in strip_ansi(result.output)
        commit.assert_not_called()

    def test_removes_track_by_id(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        commit = _prepare_update(playlist, _track("Old One", ISRC("USRC17607839")))

        result = update(["Party Mix", "--remove", "isrc:USRC17607839", "-y"])

        assert result.exit_code == 0, result.output
        assert playlist.tracks == []
        commit.assert_called_once()

    def test_remove_index_out_of_range(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        _prepare_update(playlist, _track("Old One"))

        result = update(["Party Mix", "--remove", "5", "-y"])

        assert result.exit_code != 0
        assert "out of range" in strip_ansi(result.output)

    def test_remove_unknown_track(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        _prepare_update(playlist, _track("Old One", ISRC("USRC17607839")))

        result = update(["Party Mix", "--remove", "isrc:GBUM71029604", "-y"])

        assert result.exit_code != 0
        assert "not found in playlist" in strip_ansi(result.output)

    def test_adds_track_by_id(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        commit = _prepare_update(playlist)

        result = update(["Party Mix", "--add", "isrc:USRC17607839", "-y"])

        assert result.exit_code == 0, result.output
        assert [track.title for track in playlist.tracks] == ["Found by id"]
        commit.assert_called_once()

    def test_add_shows_insert_in_confirmation(
        self, update: Invoke, playlist: MockServicePlaylist
    ) -> None:
        _prepare_update(playlist)

        result = update(["Party Mix", "--add", "isrc:USRC17607839"], "y\n")
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "added" in output
        assert "Found by id" in output
