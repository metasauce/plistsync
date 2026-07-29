"""Tests for the CLI entrypoint (__main__.py)."""

import logging
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

import plistsync.__main__ as main


runner = CliRunner()


class TestCliInvocation:
    """Test CLI invocation using CliRunner."""

    def test_cli_help(self):
        """Test that CLI shows help message."""
        result = runner.invoke(main.cli, ["--help"])
        assert result.exit_code == 0
        assert "plistsync" in result.output
        assert "Command line tool" in result.output

    def test_config_help(self):
        """Test that config subcommand shows help."""
        result = runner.invoke(main.cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_version(self):
        """Test that config subcommand shows help."""
        result = runner.invoke(main.cli, ["--version"])
        assert result.exit_code == 0
        assert "plistsync" in result.output.lower()


class TestLoggingSetup:
    """Test the logging_callback function."""

    @pytest.mark.parametrize(
        ("verbose", "expected_offset"),
        [
            (None, 0),  # verbose=None → or 0 → 0
            (0, 0),  # no -v flag
            (1, 1),  # -v
            (2, 2),  # -vv
            (3, 3),  # -vvv
            (10, 10),  # -vvvvvvvvvv
        ],
    )
    def test_init_logging_offset(self, plist_config, verbose, expected_offset):
        """Test that init_logging is called with the correct log_level_offset."""
        with (
            patch("plistsync.__main__.init_logging") as mock_init,
            patch.object(main, "Config"),
            patch("plistsync.__main__.logging.basicConfig"),
        ):
            main.logging_callback(verbose=verbose)
            mock_init.assert_called_once()
            _, offset = mock_init.call_args.args
            assert offset == expected_offset

    @pytest.mark.parametrize(
        ("verbose", "expect_root_debug"),
        [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (10, True),
        ],
    )
    def test_root_logger_level(self, plist_config, verbose, expect_root_debug):
        """Test that root logger is set to DEBUG when verbose >= 3."""
        with (
            patch("plistsync.__main__.init_logging"),
            patch.object(main, "Config"),
            patch("plistsync.__main__.logging.basicConfig"),
        ):
            mock_root = MagicMock()
            mock_root.handlers = []  # no RichHandler found → skip handler adjustments
            with patch("plistsync.__main__.logging.getLogger", return_value=mock_root):
                main.logging_callback(verbose=verbose)
                if expect_root_debug:
                    mock_root.setLevel.assert_called_once_with(logging.DEBUG)
                else:
                    mock_root.setLevel.assert_not_called()


class TestRegisterApps:
    """Test the register_apps function."""

    def test_register_apps_with_all_services(self, plist_config):
        """Test registering apps when all services are available."""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module

            main.register_auth(main.cli)

            assert mock_import.call_count >= 3

    def test_register_apps_with_missing_dependency(self, plist_config):
        """Test registering apps when a dependency is missing."""
        from plistsync.errors import DependencyError

        with (
            patch("importlib.import_module") as mock_import,
            patch.object(main, "log") as mock_log,
        ):
            mock_import.side_effect = [
                MagicMock(),
                MagicMock(),
                DependencyError("test", ["test-package"]),
            ]

            main.register_auth(main.cli)

            assert mock_log.debug.call_count >= 1
