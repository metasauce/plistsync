"""Tests for the CLI entrypoint (__main__.py)."""

from unittest.mock import patch, MagicMock

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
    """Test the logging_setup callback function."""

    def test_verbose_flag_level_1(self, plist_config):
        """Test that -v sets log level to INFO."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=1)
            mock_set_level.assert_called_once_with(20)

    def test_verbose_flag_level_2(self, plist_config):
        """Test that -vv sets log level to DEBUG."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=2)
            mock_set_level.assert_called_once_with(10)

    def test_verbose_flag_level_3(self, plist_config):
        """Test that -vvv sets log level to DEBUG."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=3)
            mock_set_level.assert_called_once_with(10)

    def test_verbose_flag_zero(self, plist_config):
        """Test that no -v flag returns None without setting level."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=0)
            mock_set_level.assert_not_called()

    def test_verbose_flag_negative(self, plist_config):
        """Test that negative verbose returns None without setting level."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=-1)
            mock_set_level.assert_not_called()

    def test_verbose_over_max(self, plist_config):
        """Test that verbose > 3 returns None without setting level."""
        with patch("plistsync.__main__.set_log_level") as mock_set_level:
            main.logging_callback(verbose=10)
            mock_set_level.assert_not_called()


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
