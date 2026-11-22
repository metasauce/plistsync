"""Tests for the ConfigIO base helpers."""

from __future__ import annotations

from typing import Any, TypeVar, cast

from plistsync.core.config import ConfigIO, ServiceConfig
from tests.core.mock_playlist import MockPlaylistID

T = TypeVar("T", bound=ServiceConfig)


class _FakeConfigIO(ConfigIO):
    def __init__(self, config: ServiceConfig) -> None:
        self.config = config
        self.loaded: list[type[ServiceConfig]] = []

    def load(self, service_config_cls: type[T]) -> T:
        self.loaded.append(service_config_cls)
        return cast(T, self.config)

    def save(self, service_config: ServiceConfig) -> None:
        pass


class _FakeLibrary:
    def __init__(self, config: ServiceConfig | None) -> None:
        self.config = config

    @classmethod
    def from_config(cls, config: ServiceConfig | None) -> _FakeLibrary:
        return cls(config)

    def get_playlist_or_raise(self, id: Any) -> tuple[str, Any, Any]:
        return ("playlist", id, self.config)


class _FakeService:
    def __init__(
        self,
        library_cls: type[_FakeLibrary] | None,
        config_cls: type[ServiceConfig] | None,
    ) -> None:
        self._library_cls = library_cls
        self._config_cls = config_cls

    def library(self) -> type[_FakeLibrary] | None:
        return self._library_cls

    def config(self) -> type[ServiceConfig] | None:
        return self._config_cls


def test_resolve_library_playlist_loads_config() -> None:
    config = ServiceConfig()
    config_io = _FakeConfigIO(config)
    service = _FakeService(_FakeLibrary, ServiceConfig)
    playlist_id = MockPlaylistID("abc")

    result = config_io.resolve_library_playlist(cast(Any, service), playlist_id)

    assert config_io.loaded == [ServiceConfig]
    assert result == ("playlist", playlist_id, config)


def test_resolve_library_playlist_without_library_returns_none() -> None:
    config_io = _FakeConfigIO(ServiceConfig())
    service = _FakeService(None, ServiceConfig)

    assert (
        config_io.resolve_library_playlist(cast(Any, service), MockPlaylistID("abc"))
        is None
    )


def test_resolve_library_playlist_without_config_uses_none() -> None:
    config_io = _FakeConfigIO(ServiceConfig())
    service = _FakeService(_FakeLibrary, None)
    playlist_id = MockPlaylistID("abc")

    result = config_io.resolve_library_playlist(cast(Any, service), playlist_id)

    assert config_io.loaded == []
    assert result == ("playlist", playlist_id, None)
