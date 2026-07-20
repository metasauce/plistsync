from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable
from typing import Any, Self
from unittest.mock import MagicMock, patch

import pytest

from plistsync.core import Library, Track, TrackInfo
from plistsync.core.ids import PlaylistID, TrackID
from plistsync.errors import DependencyError
from plistsync.services import Service, ServiceLoader
from plistsync.services.registry import Registry

SERVICE_MODULE = "plistsync.services._test"
SERVICE_NAME = "_test"


# ------------------------------ Test fixtures ------------------------------ #


class Root(ABC, Registry):
    """Independent registry root, so tests don't touch core abstractions."""


class FakePlaylistID(PlaylistID):
    __module__ = SERVICE_MODULE

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls()

    @property
    def serial(self) -> str:
        return f"{SERVICE_NAME}:playlist:fake"


class FakeTrackID(TrackID):
    __module__ = SERVICE_MODULE

    @classmethod
    def parse(cls, value: str) -> Self:
        return cls()

    @property
    def serial(self) -> str:
        return f"{SERVICE_NAME}:track:fake"


class FakeTrack(Track):
    __module__ = SERVICE_MODULE

    @property
    def info(self) -> TrackInfo:
        return {}

    @property
    def ids(self) -> frozenset[TrackID]:
        return frozenset()


class FakeLibrary(Library[Any, Any]):
    __module__ = SERVICE_MODULE

    @property
    def playlists(self) -> Iterable[Any]:
        return []

    def get_playlist(self, *, id: PlaylistID | str | None = None) -> Any | None:
        return None

    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: list[Any] | None = None,
    ) -> Any:
        raise NotImplementedError


class FakeService(Service):
    __module__ = SERVICE_MODULE


@pytest.fixture(autouse=True)
def isolate_registry() -> Generator[None, None, None]:
    """Restore the global registry to its pre-test state.

    Concrete classes register themselves at definition time into the global
    ``Registry._REGISTRY``. Snapshot and restore it so classes defined inside
    tests don't leak into other tests.
    """
    snapshot = {
        root: {service: list(classes) for service, classes in bucket.items()}
        for root, bucket in Registry._REGISTRY.items()
    }
    yield
    Registry._REGISTRY.clear()
    Registry._REGISTRY.update(snapshot)


# ------------------------------- Test Registry ------------------------------ #


class TestRegistry:
    """Registry registers concrete subclasses by service at definition time."""

    def test_concrete_subclasses_register_under_root(self) -> None:
        class ImplA(Root):
            __module__ = "plistsync.services._test_a"

        class ImplB(Root):
            __module__ = "plistsync.services._test_b"

        assert Root.registry() == {"_test_a": [ImplA], "_test_b": [ImplB]}

    def test_multiple_implementations_accumulate_per_service(self) -> None:
        class ImplA(Root):
            __module__ = SERVICE_MODULE

        class ImplB(Root):
            __module__ = SERVICE_MODULE

        assert Root.registry()[SERVICE_NAME] == [ImplA, ImplB]

    def test_explicit_service_kwarg_overrides_module_derivation(self) -> None:
        class Impl(Root, service="custom"):
            pass

        assert Root.registry() == {"custom": [Impl]}

    def test_abstract_root_is_not_registered(self) -> None:
        assert Root.registry() == {}
        assert Root._registry is Root

    def test_abc_subclass_becomes_new_root(self) -> None:
        class SubRoot(Root, ABC):
            pass

        class Impl(SubRoot):
            __module__ = SERVICE_MODULE

        assert SubRoot._registry is SubRoot
        assert SubRoot.registry() == {SERVICE_NAME: [Impl]}
        assert Root.registry() == {}

    def test_subclass_with_abstract_methods_becomes_new_root(self) -> None:
        class SubRoot(Root):
            @abstractmethod
            def abstract_meth(self) -> None: ...

        class Impl(SubRoot):
            __module__ = SERVICE_MODULE

            def abstract_meth(self) -> None: ...

        assert SubRoot.registry() == {SERVICE_NAME: [Impl]}
        assert Root.registry() == {}

    def test_service_derivation_fails_outside_services_namespace(self) -> None:
        with pytest.raises(ValueError, match="Cannot derive service name"):

            class ForeignImpl(Root):
                pass

    def test_direct_subclass_without_root_fails(self) -> None:
        with pytest.raises(ValueError, match="does not define a registry key"):

            class Orphan(Registry):
                pass

    def test_registry_accessor_without_root_fails(self) -> None:
        with pytest.raises(ValueError, match="not defined"):
            Registry.registry()


# ------------------------------- Test Service ------------------------------- #


class TestService:
    """Service exposes the classes registered for its module-derived name."""

    def test_name_inferred_from_module(self) -> None:
        assert FakeService().name == SERVICE_NAME

    def test_playlist_ids_returns_registered_classes(self) -> None:
        assert list(FakeService().playlist_ids()) == [FakePlaylistID]

    def test_track_ids_returns_registered_classes(self) -> None:
        assert list(FakeService().track_ids()) == [FakeTrackID]

    def test_tracks_returns_registered_classes(self) -> None:
        assert list(FakeService().tracks()) == [FakeTrack]

    def test_library_returns_registered_class(self) -> None:
        assert FakeService().library() is FakeLibrary

    def test_library_returns_none_when_unregistered(self) -> None:
        class LibraryLessService(Service):
            __module__ = "plistsync.services._test_nolib"

        assert LibraryLessService().library() is None

    def test_unregistered_service_lookups_return_empty(self) -> None:
        class LonelyService(Service):
            __module__ = "plistsync.services._test_lonely"

        service = LonelyService()
        assert service.playlist_ids() == ()
        assert service.track_ids() == ()
        assert service.tracks() == ()
        assert service.library() is None


# ----------------------------- Test ServiceLoader ---------------------------- #


def _make_entry_point(name: str, loaded: type[Service]) -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.load.return_value = loaded
    return ep


class TestServiceLoader:
    """ServiceLoader discovers services through entry points."""

    @pytest.fixture(autouse=True)
    def clear_loader_cache(self) -> Generator[None, None, None]:
        ServiceLoader.get.__func__.cache_clear()
        ServiceLoader.all.__func__.cache_clear()
        yield
        ServiceLoader.get.__func__.cache_clear()
        ServiceLoader.all.__func__.cache_clear()

    def test_get_returns_service_instance(self) -> None:
        ep = _make_entry_point(SERVICE_NAME, FakeService)
        with patch("plistsync.services.entry_points", return_value=[ep]):
            service = ServiceLoader.get(SERVICE_NAME)

        assert isinstance(service, FakeService)
        assert service.name == SERVICE_NAME
        ep.load.assert_called_once()

    def test_get_returns_none_for_unknown_service(self) -> None:
        with patch("plistsync.services.entry_points", return_value=[]):
            assert ServiceLoader.get("_nonexistent") is None

    def test_get_returns_none_when_dependencies_missing(self) -> None:
        ep = _make_entry_point("_test_broken", FakeService)
        ep.load.side_effect = DependencyError("_test_broken", ["missing_pkg"])
        with patch("plistsync.services.entry_points", return_value=[ep]):
            assert ServiceLoader.get("_test_broken") is None

    def test_get_returns_none_when_module_missing(self) -> None:
        ep = _make_entry_point("_test_broken", FakeService)
        ep.load.side_effect = ModuleNotFoundError("No module named 'missing_pkg'")
        with patch("plistsync.services.entry_points", return_value=[ep]):
            assert ServiceLoader.get("_test_broken") is None

    def test_all_returns_mapping_of_available_services(self) -> None:
        class OtherService(Service):
            __module__ = "plistsync.services._test_other"

        eps = [
            _make_entry_point(SERVICE_NAME, FakeService),
            _make_entry_point("_test_other", OtherService),
        ]
        with patch("plistsync.services.entry_points", return_value=eps):
            result = ServiceLoader.all()

        assert set(result) == {SERVICE_NAME, "_test_other"}
        assert isinstance(result[SERVICE_NAME], FakeService)
        assert isinstance(result["_test_other"], OtherService)
        for name, service in result.items():
            assert service.name == name

    def test_all_skips_services_with_missing_dependencies(self) -> None:
        good = _make_entry_point(SERVICE_NAME, FakeService)
        broken = _make_entry_point("_test_broken", FakeService)
        broken.load.side_effect = DependencyError("_test_broken", ["missing_pkg"])

        with patch("plistsync.services.entry_points", return_value=[good, broken]):
            result = ServiceLoader.all()

        assert SERVICE_NAME in result
        assert "_test_broken" not in result
