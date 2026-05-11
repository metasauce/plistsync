from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from plistsync.errors import DependencyError
from plistsync.services import Service, ServiceRegistry


class TestDiscovery:
    """ServiceRegistry discovers Service subclasses and infers names."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        ServiceRegistry.get.cache_clear()
        yield
        ServiceRegistry.get.cache_clear()

    def test_get_service_returns_instance_with_correct_name(self):
        """Discovered service has name matching its module."""
        fake_module = ModuleType("plistsync.services._test_fake")

        class FakeService(Service):
            track_cls = int  # type: ignore[assignment]

        FakeService.__module__ = "plistsync.services._test_fake"
        fake_module.FakeService = FakeService  # type: ignore[assignment]

        with patch.object(
            sys, "modules", {**sys.modules, fake_module.__name__: fake_module}
        ):
            with patch("importlib.import_module", return_value=fake_module):
                service = ServiceRegistry.get("_test_fake")

        assert service is not None
        assert service.name == "_test_fake"

    def test_get_service_returns_none_for_missing_dependency(self):
        with patch(
            "importlib.import_module",
            side_effect=DependencyError("svc", ["pkg"]),
        ):
            assert ServiceRegistry.get("svc") is None

    def test_get_service_returns_none_when_no_service_subclass(self):
        empty = ModuleType("plistsync.services._test_empty")
        with patch.object(sys, "modules", {**sys.modules, empty.__name__: empty}):
            with patch("importlib.import_module", return_value=empty):
                assert ServiceRegistry.get("_test_empty") is None

    def test_dict_keys_are_module_names(self):
        result = ServiceRegistry.dict()
        for name in result:
            assert result[name].name == name

    def test_dict_filters_broken_modules(self):
        with patch(
            "pkgutil.iter_modules",
            return_value=[MagicMock(name="_test_broken")],
        ):
            with patch(
                "importlib.import_module",
                side_effect=DependencyError("_test_broken", ["pkg"]),
            ):
                result = ServiceRegistry.dict()
        assert "_test_broken" not in result
