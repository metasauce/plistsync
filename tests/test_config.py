from pathlib import Path
from unittest.mock import patch
from plistsync.errors import ConfigurationError
import pytest
import os
from plistsync.config import Config


@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "config.yml"
    os.environ["PSYNC_CONFIG_DIR"] = str(tmp_path)
    return config_file, tmp_path


def test_create_default_config(temp_config_file):
    config = Config()
    assert temp_config_file[0].exists()

    # Default values from the schema
    assert config.path == temp_config_file[0]
    assert config.data.logging.level == "INFO"


class TestServiceConfig:
    @pytest.mark.parametrize("service", ["beets", "plex", "tidal", "spotify"])
    def test_service_not_enabled_by_default(self, temp_config_file, service):
        config = Config()
        assert temp_config_file[0].exists()
        with pytest.raises(ConfigurationError):
            getattr(config, service)

    @pytest.mark.parametrize(
        ("service", "config_data"),
        [
            (
                "beets",
                (
                    "services:\n"
                    "    beets:\n"
                    "        enabled: true\n"
                    "        database: ./test.db"
                ),
            ),
            (
                "plex",
                (
                    "services:\n"
                    "    plex:\n"
                    "        enabled: true\n"
                    "        server_url: http://localhost:32400"
                ),
            ),
            (
                "tidal",
                (
                    "services:\n"
                    "    tidal:\n"
                    "        enabled: true\n"
                    "        client_id: testuser\n"
                    "        country_code: DE\n"
                ),
            ),
            (
                "spotify",
                (
                    "services:\n"
                    "    spotify:\n"
                    "        enabled: true\n"
                    "        client_id: testclientid\n"
                ),
            ),
        ],
    )
    def test_enable_service_in_config(self, temp_config_file, service, config_data):
        config_data = "logging:\n    level: DEBUG\nredirect_port: 5000\n" + config_data
        temp_config_file[0].write_text(
            config_data,
            encoding="utf-8",
        )
        config = Config()
        assert temp_config_file[0].exists()
        service_config = getattr(config, service)
        assert service_config.enabled is True

    def test_properties(self, temp_config_file):
        """This test is mainly for test coverage tbh"""
        config_data = (
            "logging:\n"
            "    level: DEBUG\n"
            "redirect_port: 5000\n"
            "services:\n"
            "    plex:\n"
            "        enabled: true\n"
            "        server_url: http://localhost:32400"
        )
        temp_config_file[0].write_text(
            config_data,
            encoding="utf-8",
        )
        config = Config()
        plex_config = config.plex
        assert config.redirect_port == 5000
        assert plex_config.enabled is True
        assert plex_config.server_url == "http://localhost:32400"
        assert plex_config.app_name is not None
        assert plex_config.client_identifier is not None
        assert plex_config.token_path == temp_config_file[1] / "plex_token.json"


class TestConfigDirectory:
    """Tests for config directory hierarchy."""

    global_config_dir: Path

    @pytest.fixture(autouse=True)
    def setup_mocks(self, tmp_path, monkeypatch):
        """Setup common mocks for all tests in this class."""
        cwd_dir = tmp_path / "project"
        self.global_config_dir = tmp_path / "user_config_dir"

        # Store patches as instance variables
        cwd_patcher = patch("plistsync.config.Path.cwd", return_value=cwd_dir)
        user_config_patcher = patch(
            "plistsync.config.user_config_dir",
            return_value=self.global_config_dir,
        )

        # Start patches
        cwd_patcher.start()
        user_config_patcher.start()
        monkeypatch.delenv("PSYNC_CONFIG_DIR", raising=False)

        yield

        # Stop patches
        cwd_patcher.stop()
        user_config_patcher.stop()

    @pytest.mark.parametrize(
        "env_var_value, should_use_env",
        [
            # Empty string should not use env
            ("", False),
            ("  ", False),
            # Valid path should use env
            ("/valid/path", True),
        ],
    )
    def test_env_var_dir(self, tmp_path, monkeypatch, env_var_value, should_use_env):
        """Test edge cases for environment variable handling."""
        # Create a valid env directory within tmp_path for the valid path case
        if env_var_value == "/valid/path":
            env_dir = tmp_path / "valid_env_config"
            env_dir.mkdir()
            env_var_value = str(env_dir)

        monkeypatch.setenv("PSYNC_CONFIG_DIR", env_var_value)

        result = Config.get_dir()

        if should_use_env:
            assert str(result) == env_var_value
        else:
            assert str(result) != env_var_value

    def test_global_dir(self):
        """If local and env not given use global dir"""

        result = Config.get_dir()
        assert result == self.global_config_dir.resolve()
