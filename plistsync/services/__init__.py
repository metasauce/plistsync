# We do not import from the different submodules as they
# might raise with check_dependencies.

import importlib
import inspect
import pkgutil
from abc import ABC
from functools import cache
from typing import ClassVar

from plistsync.core import Library, Playlist, Track
from plistsync.errors import DependencyError


class Service(ABC):
    """Abstraction for discoverable service plugins.

    Subclasses in `services/<name>/` modules are automatically
    discovered by the ServiceRegistry.

    Each concrete Service exposes the key types that belong to its
    service: the library/collection class and the track class.
    Optionally a playlist class for playlist-capable services.
    """

    track_cls: ClassVar[type[Track]]
    library_cls: ClassVar[type[Library] | None] = None
    playlist_cls: ClassVar[type[Playlist] | None] = None

    @property
    def name(self) -> str:
        """Service name, inferred from the module (e.g. 'spotify', 'plex')."""
        return self.__module__.split(".")[-1]


class ServiceRegistry:
    """Central registry for dynamic service discovery and instantiation.

    Automatically discovers Service subclasses in services/* modules
    using pkgutil + importlib. Lazy-loaded with @cache for performance.
    Handles missing dependencies gracefully.

    Usage:
        >>> service = ServiceRegistry.get_service('spotify')
        >>> services = ServiceRegistry.list()  # {'spotify': SpotifyService(), ...}
    """

    @classmethod
    @cache
    def get(cls, name: str) -> Service | None:
        """Dynamically import services.NAME module, find Service ABC, instantiate."""
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except (DependencyError, ModuleNotFoundError):
            return None

        # Find first Service subclass (assumes 1/module)
        service_cls: None | type[Service] = None
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Service) and obj != Service:
                service_cls = obj
                break

        return service_cls() if service_cls else None

    @classmethod
    @cache
    def dict(cls) -> dict[str, Service]:
        """All importable services {name: instance}.

        Scans services/* modules via pkgutil, filters valid ones.
        """
        services: dict[str, Service] = {}
        # REQUIRES: ServiceRegistry in package with __path__ (services/__init__.py)
        for module_info in pkgutil.iter_modules(__path__, __name__ + "."):
            short_name = module_info.name.rsplit(".", 1)[-1]
            service = cls.get(short_name)
            if service is not None:
                services[short_name] = service
        return services
