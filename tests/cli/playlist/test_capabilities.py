"""Capability-gated options are removed from the CLI surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer._click._compat import strip_ansi

if TYPE_CHECKING:
    import typer
    from typer.testing import CliRunner


class TestCapabilityFiltering:
    """Options gated on library capabilities are removed from the CLI surface."""

    def test_create_help_hides_add(
        self, runner: CliRunner, no_lookup_app: typer.Typer
    ) -> None:
        result = runner.invoke(no_lookup_app, ["playlist", "create", "--help"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "--add" not in output
        assert all(option in output for option in ("--name", "--description", "--yes"))
        # Custom signature filtering must keep the Annotated metadata.
        assert all(option in output for option in ("-n", "-d", "-y"))

    def test_update_help_hides_add(
        self, runner: CliRunner, no_lookup_app: typer.Typer
    ) -> None:
        result = runner.invoke(no_lookup_app, ["playlist", "update", "--help"])
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "--add" not in output
        assert all(option in output for option in ("--remove", "--yes"))
        assert all(option in output for option in ("-r", "-y"))

    def test_create_rejects_add(
        self, runner: CliRunner, no_lookup_app: typer.Typer
    ) -> None:
        result = runner.invoke(
            no_lookup_app,
            ["playlist", "create", "--name", "N", "-y", "--add", "isrc:USRC17607839"],
        )

        assert result.exit_code == 2
        assert "--add" in strip_ansi(result.output)

    def test_update_rejects_add(
        self, runner: CliRunner, no_lookup_app: typer.Typer
    ) -> None:
        result = runner.invoke(
            no_lookup_app,
            ["playlist", "update", "Party Mix", "--add", "isrc:USRC17607839"],
        )

        assert result.exit_code == 2
        assert "--add" in strip_ansi(result.output)
