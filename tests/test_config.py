from __future__ import annotations
from dataclasses import dataclass
import sys
from unittest.mock import MagicMock, patch
import pytest
import os
import yaml
from importlib.metadata import entry_points
from importlib.util import find_spec
from plistsync.config import Config, ServiceConfig
from plistsync.services import ServiceLoader
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def temp_config_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    os.environ["PSYNC_CONFIG_DIR"] = str(tmp_path)
    # The first get_dir() call is cached for the whole process
    Config.get_dir.cache_clear()
    return config_file, tmp_path


def _reload_service_configs() -> None:
    """Re-register all discoverable service configs from scratch."""
    ServiceConfig.registry().clear()
    # Evicts cached per-service packages from ``sys.modules`` so that
    #   ``ServiceLoader.all()`` re-imports them fresh — which re-executes their
    #   ``__init__`` modules and re-registers their ``ServiceConfig`` subclasses.
    for ep in entry_points(group=ServiceLoader.GROUP):
        pkg_prefix = f"plistsync.services.{ep.name}"
        for key in list(sys.modules):
            if key == pkg_prefix or key.startswith(pkg_prefix + "."):
                del sys.modules[key]
    ServiceLoader.all.cache_clear()
    ServiceLoader.all()


def test_create_default_config(temp_config_file):
    config = Config()
    assert temp_config_file[0].exists()

    # Default values from the schema
    assert config.path == temp_config_file[0]
    assert config.data.logging.level == "INFO"


class TestServiceConfig:
    """Tests that dynamically registered services are added to the schema."""

    @dataclass
    class MyConfig(ServiceConfig, service="test"):
        my_option: str = "default_value"

    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch):
        """Keep the global ServiceConfig registry clean for these tests.

        Config.default_yaml() calls ServiceLoader.all() to include every
        discoverable service in the generated default config file. That imports
        and registers all core service configs in the global registry, leaking
        them into tests that expect a clean state.
        """
        monkeypatch.setattr(ServiceLoader, "all", lambda: {})

        ServiceConfig.registry().clear()
        ServiceConfig.registry()["test"] = [self.MyConfig]
        yield
        monkeypatch.undo()
        _reload_service_configs()

    def test_service_config_registry(self):
        registry = ServiceConfig.registry()
        assert len(registry) == 1
        assert "test" in registry
        assert registry["test"][0] is self.MyConfig

    def test_get_service_config(self):
        config = Config()
        service_config = config.get_service_config("test")
        assert isinstance(service_config, self.MyConfig)
        assert service_config.my_option == "default_value"
        # No core services may leak in from the global registry
        assert "beets" not in config.data.services

    def test_config_schema_includes_service(self):
        config = Config()
        assert "test" in config.data.services
        assert isinstance(config.data.services["test"], self.MyConfig)
        assert config.data.services["test"].my_option == "default_value"
        # No core services may leak in from the global registry
        assert "beets" not in config.data.services

    def test_default_yaml_includes_service(self):
        config = Config()
        default_yaml = config.default_yaml()
        assert "test" in default_yaml
        assert "my_option" in default_yaml

    def test_default_config_file_includes_service(self, temp_config_file):
        # Remove file if it exists to force Config to write a new default config
        if temp_config_file[0].exists():
            temp_config_file[0].unlink()
        Config()
        with open(temp_config_file[0]) as f:
            content = f.read()
        assert "test" in content
        assert "my_option" in content

    def test_get_returns_config(self):
        """ServiceConfig subclass can retrieve its own instance from Config."""
        cfg = self.MyConfig.get()
        assert isinstance(cfg, self.MyConfig)
        assert cfg.my_option == "default_value"

    def test_get_raises_when_not_registered(self):
        """ServiceConfig.get() raises ValueError if the class is not registered."""
        with patch.dict("plistsync.config.ServiceConfig._REGISTRY", {}, clear=True):
            with pytest.raises(ValueError, match="is not registered"):
                TestServiceConfig.MyConfig.get()


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
        # get_dir() is cached for the whole process; must be cleared after
        # patching so the next call recomputes with the new environment
        Config.get_dir.cache_clear()

        yield

        # Stop patches
        Config.get_dir.cache_clear()
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


class TestDefaultConfigWithServices:
    """The generated default config must contain all discoverable services.

    Counterpart to :class:`TestServiceConfig`: no ``ServiceLoader.all()`` stub
    here. Creating an initial config (no file present) must trigger service
    discovery via ``Config.default_yaml()`` and write every registered service
    config into the YAML.
    """

    def _has_config(self, service_name: str) -> bool:
        """Check if a service ships a config module that can be imported."""
        try:
            return find_spec(f"plistsync.services.{service_name}.config") is not None
        except Exception:
            # Missing dependency (e.g. traktor → lxml) or import error
            return False

    def test_default_yaml_contains_all_services(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PSYNC_CONFIG_DIR", str(tmp_path))
        Config.get_dir.cache_clear()

        # Every entry-point service that ships a config module must appear
        expected = sorted(
            ep.name
            for ep in entry_points(group=ServiceLoader.GROUP)
            if self._has_config(ep.name)
        )
        assert expected, "no discoverable services with a config module"

        # No config file exists -> default_yaml() runs the real discovery
        Config()
        config_file = Config.get_file()
        assert config_file.exists()

        services_in_yaml = (yaml.safe_load(config_file.read_text()) or {}).get(
            "services"
        ) or {}
        for name in expected:
            assert name in services_in_yaml, (
                f"{name!r} missing from default YAML services section"
            )

        # Also check that a reloaded config exposes them as instances
        reloaded = Config()
        for name in expected:
            assert name in reloaded.data.services
            config_cls = ServiceConfig.registry().get(name, (None,))[0]
            assert config_cls is not None
            assert isinstance(reloaded.data.services[name], config_cls)

        Config.get_dir.cache_clear()


class TestConfigEdgeCases:
    """Edge-case behaviour of Config itself."""

    def test_preload_services_calls_service_loader(self):
        with patch.object(ServiceLoader, "all") as mock_all:
            Config(preload_services=True)
            mock_all.assert_called_once()

    def test_redirect_port_default(self):
        assert Config().redirect_port == 5001


class TestGetServiceConfigSlowPath:
    """The slow path of get_service_config (service not yet in the schema)."""

    def test_service_not_registered(self):
        config = Config()
        with patch.object(ServiceLoader, "get", return_value=None):
            with pytest.raises(ValueError, match="is not registered"):
                config.get_service_config("unknown")

    def test_service_has_no_config_schema(self):
        mock_service = MagicMock()
        mock_service.config.return_value = None
        config = Config()
        with patch.object(ServiceLoader, "get", return_value=mock_service):
            with pytest.raises(ValueError, match="has no config schema"):
                config.get_service_config("unknown")

    def test_slow_path_lazily_discovers_service(self):
        """When a service is not yet in the schema, get_service_config triggers
        discovery, rebuilds the schema, reloads the file, and returns it."""
        ServiceLoader.all()  # ensure the real service is registered
        cfg_entry = ServiceConfig.registry().pop("spotify")
        config = Config()  # schema built without spotify
        assert "spotify" not in config.data.services

        # Restore the config class so ServiceLoader.get() -> service.config()
        # can find it, but the schema was already built — slow path incoming
        ServiceConfig.registry()["spotify"] = cfg_entry
        result = config.get_service_config("spotify")  # slow path (re-discovers)
        assert isinstance(result, cfg_entry[0])
        assert "spotify" in config.data.services
