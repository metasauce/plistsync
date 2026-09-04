"""Tests for the CLI entrypoint (__main__.py)."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from plistsync.cli import app

runner = CliRunner()


class TestCliInvocation:
    """Test CLI invocation using CliRunner."""

    def test_cli_help(self):
        """Test that CLI shows help message."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "plistsync" in result.output
        assert "Command line tool" in result.output

    def test_config_help(self):
        """Test that config subcommand shows help."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()

    def test_version(self):
        """Test that --version prints version info."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "plistsync" in result.output.lower()


class TestLoggingSetup:
    """Test the logging_callback function."""

    @pytest.mark.parametrize(
        ("verbose", "expected_offset"),
        [
            (None, 0),
            (1, 1),
            (2, 2),
            (3, 3),
        ],
    )
    def test_init_logging_offset(self, plist_config, verbose, expected_offset):
        """Test that init_logging is called with the correct log_level_offset."""
        from plistsync.cli.app import logging_callback

        with (
            patch("plistsync.cli.app.init_logging") as mock_init,
            patch("plistsync.cli.app.Config"),
            patch("plistsync.cli.app.logging.basicConfig"),
            patch(
                "plistsync.cli.app.logging.getLogger",
                return_value=MagicMock(handlers=[]),
            ),
        ):
            logging_callback(verbose=verbose)
            mock_init.assert_called_once()
            # init_logging(config, log_level_offset) — second positional arg
            offset = mock_init.call_args[0][1]
            assert offset == expected_offset

    @pytest.mark.parametrize(
        ("verbose", "expect_root_debug"),
        [
            (None, False),
            (1, False),
            (2, False),
            (3, True),
        ],
    )
    def test_root_logger_level(self, plist_config, verbose, expect_root_debug):
        """Test that root logger is set to DEBUG when verbose >= 3."""
        from plistsync.cli.app import logging_callback

        mock_root = MagicMock()
        mock_root.handlers = []  # no RichHandler → skip handler adjustments

        with (
            patch("plistsync.cli.app.init_logging"),
            patch("plistsync.cli.app.Config"),
            patch("plistsync.cli.app.logging.basicConfig"),
            patch("plistsync.cli.app.logging.getLogger", return_value=mock_root),
        ):
            logging_callback(verbose=verbose)
            if expect_root_debug:
                mock_root.setLevel.assert_called_once_with(logging.DEBUG)
            else:
                mock_root.setLevel.assert_not_called()

    def test_config_load_error_is_caught(self):
        """Config load failure is caught and logged; init_logging gets None."""
        from plistsync.cli.app import logging_callback

        with (
            patch("plistsync.cli.app.init_logging") as mock_init,
            patch("plistsync.cli.app.Config") as mock_config_cls,
            patch("plistsync.cli.app.logging.basicConfig"),
            patch(
                "plistsync.cli.app.logging.getLogger",
                return_value=MagicMock(handlers=[]),
            ),
        ):
            mock_config_cls.side_effect = RuntimeError("config boom")

            # Should not raise.
            logging_callback(verbose=0)

            mock_init.assert_called_once()
            assert mock_init.call_args[0][0] is None

    @pytest.mark.parametrize("verbose", [0, 1])
    def test_rich_handler_low_verbosity(self, verbose):
        """RichHandler present + verbose < 2 → traceback.install with defaults."""
        from rich.logging import RichHandler

        from plistsync.cli.app import logging_callback

        mock_handler = MagicMock()
        mock_handler.__class__ = RichHandler  # type: ignore[assignment]
        mock_handler.name = "rich"
        mock_root = MagicMock()
        mock_root.handlers = [mock_handler]

        with (
            patch("plistsync.cli.app.init_logging"),
            patch("plistsync.cli.app.Config"),
            patch("plistsync.cli.app.logging.basicConfig"),
            patch("plistsync.cli.app.logging.getLogger", return_value=mock_root),
            patch("rich.traceback.install") as mock_install,
        ):
            logging_callback(verbose=verbose)

        mock_install.assert_called_once_with(show_locals=False, extra_lines=0)

    @pytest.mark.parametrize("verbose", [2, 3])
    def test_rich_handler_high_verbosity(self, verbose):
        """RichHandler present + verbose >= 2 → show_path and locals enabled."""
        from rich.logging import RichHandler

        from plistsync.cli.app import logging_callback

        mock_handler = MagicMock()
        mock_handler.__class__ = RichHandler  # type: ignore[assignment]
        mock_handler.name = "rich"
        mock_handler._log_render = MagicMock()
        mock_root = MagicMock()
        mock_root.handlers = [mock_handler]

        with (
            patch("plistsync.cli.app.init_logging"),
            patch("plistsync.cli.app.Config"),
            patch("plistsync.cli.app.logging.basicConfig"),
            patch("plistsync.cli.app.logging.getLogger", return_value=mock_root),
        ):
            logging_callback(verbose=verbose)

        assert mock_handler._log_render.show_path is True
        assert mock_handler.tracebacks_show_locals is True

    def test_version_callback_early_return(self):
        """version_callback returns None when value is falsy."""
        from plistsync.cli.app import version_callback

        assert version_callback(False) is None  # type: ignore[func-returns-value]


class TestAuthRegistration:
    """Test that auth subcommands are registered from discoverable services.

    Auth registration runs at module-import time in ``auth.py``.
    """

    def test_auth_app_has_commands(self):
        """All importable services should register an auth subcommand."""
        from plistsync.cli.commands.auth import auth_app

        registered = list(auth_app.registered_commands)
        # At least one service should be importable in any test environment;
        # in the full dev environment all three (plex, spotify, tidal) are.
        assert len(registered) >= 1

    def test_dependency_error_is_caught(self):
        """DependencyError during import is caught and logged, not raised."""
        import importlib

        from plistsync.errors import DependencyError
        import plistsync.cli.commands.auth as auth_module
        import plistsync.logger  # ensure module is loaded for patching

        # The module-level loop already executed; reload with mocked
        # stdlib ``importlib.import_module`` and ``plistsync.logger.log``.
        # Patching at those global targets survives the re-import
        # statements inside the reloaded module.
        try:
            with (
                patch("importlib.import_module") as mock_import,
                patch.object(plistsync.logger, "log") as mock_log,
            ):
                mock_import.side_effect = DependencyError("test", ["test-package"])
                importlib.reload(auth_module)

            mock_log.debug.assert_called()
            logged_msg = mock_log.debug.call_args[0][0]
            assert "Skipping" in logged_msg
        finally:
            # Restore the module to its original (real imports) state.
            importlib.reload(auth_module)
