"""Tests for ``plistsync <service> playlist create``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer._click._compat import strip_ansi

from tests.core.mock_collections import MockLibrary

if TYPE_CHECKING:
    from collections.abc import Callable

    from typer.testing import Result

    Invoke = Callable[..., Result]


class TestCreate:
    """``plistsync <service> playlist create``."""

    @pytest.mark.parametrize(
        "option",
        ["--name", "-n", "--description", "-d", "--add", "-a", "--yes", "-y"],
    )
    def test_help_lists_options(self, create: Invoke, option: str) -> None:
        result = create(["--help"])

        assert result.exit_code == 0
        assert option in strip_ansi(result.output)

    @pytest.mark.parametrize(
        ("args", "user_input", "expected"),
        [
            ([], "My Playlist\nMy Description\n\n", ("My Playlist", "My Description")),
            ([], "My Playlist\n\n\n", ("My Playlist", None)),
            (["--name", "N", "--description", "D"], "\n", ("N", "D")),
        ],
    )
    def test_prompts_for_metadata(
        self,
        create: Invoke,
        args: list[str],
        user_input: str,
        expected: tuple[str, str | None],
    ) -> None:
        result = create(args, user_input)

        assert result.exit_code == 0, result.output
        created = MockLibrary.created[0]
        assert (created.name, created.description) == expected

    def test_confirmation_lists_metadata_and_tracks(self, create: Invoke) -> None:
        result = create(
            ["--name", "N", "--description", "D", "--add", "isrc:USRC17607839"], "\n"
        )
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert all(
            text in output
            for text in (
                "Name",
                "'N'",
                "Description",
                "Tracks",
                "Artist",
                "Found by id",
                "Continue?",
            )
        )
        assert [track.title for track in MockLibrary.created[0].tracks] == [
            "Found by id"
        ]

    @pytest.mark.parametrize(
        ("value", "expected_titles"),
        [
            ("isrc:USRC17607839", ["Found by id"]),
            ("not-a-track", []),
        ],
    )
    def test_add_option(
        self, create: Invoke, value: str, expected_titles: list[str]
    ) -> None:
        result = create(["--name", "N", "--description", "D", "-y", "--add", value])

        assert result.exit_code == 0, result.output
        assert [t.title for t in MockLibrary.created[0].tracks] == expected_titles

    def test_yes_skips_confirmation(self, create: Invoke) -> None:
        result = create(["--name", "N", "--description", "D", "-y"])

        assert result.exit_code == 0, result.output
        assert "Continue?" not in result.output

    def test_declining_confirmation_aborts(self, create: Invoke) -> None:
        result = create([], "N\nD\nn\n")

        assert result.exit_code != 0
        assert "Aborted" in strip_ansi(result.output)
        assert MockLibrary.created == []
