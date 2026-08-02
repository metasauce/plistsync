# We do not import from the different submodules as they
# might raise with check_dependencies.

from __future__ import annotations

from abc import ABC
from functools import cache
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from plistsync.errors import DependencyError

from .registry import Registry

if TYPE_CHECKING:
    from collections.abc import Sequence

    from plistsync.config import ServiceConfig
    from plistsync.core import Library, Playlist, Track
    from plistsync.core.ids import PlaylistID, TrackID


class Service(ABC, Registry):
    """Abstraction for discoverable service plugins.

    Concrete service implementations register their identifier classes at
    class-definition time. Importing a service module is sufficient to make
    its classes discoverable.

    Each service exposes the identifier classes associated with it, including
    track identifiers and optionally playlist identifiers.
    """

    @property
    def name(self) -> str:
        """Service name, inferred from the module (e.g. 'spotify', 'plex')."""
        return self.__module__.split(".")[-1]

    def config(self) -> type[ServiceConfig] | None:
        """Return the service config class registered for this service, if any."""
        from plistsync.config import ServiceConfig

        return ServiceConfig.registry().get(self.name, (None,))[0]

    def playlist_ids(self) -> Sequence[type[PlaylistID]]:
        """Return playlist identifier classes registered for this service."""

        from plistsync.core.ids import PlaylistID

        return PlaylistID.registry().get(self.name, ())

    def track_ids(self) -> Sequence[type[TrackID]]:
        """Return track identifier classes registered for this service."""

        from plistsync.core.ids import TrackID

        return TrackID.registry().get(self.name, ())

    def library(self) -> type[Library] | None:
        """Return the library class registered for this service, if any."""
        from plistsync.core import Library

        return Library.registry().get(self.name, (None,))[0]

    def tracks(self) -> Sequence[type[Track]]:
        """Return the track class registered for this service, if any."""
        from plistsync.core import Track

        return Track.registry().get(self.name, ())

    def playlists(self) -> Sequence[type[Playlist]]:
        """Return the playlist class registered for this service, if any."""
        from plistsync.core import Playlist

        return Playlist.registry().get(self.name, ())


class ServiceLoader:
    """Lazy access to discoverable services specific classes."""

    GROUP = "plistsync.services"
    """Entry point group for discoverable services. Defined in the pyproject.toml to
    allow registering a service.

    This improves discoverability and avoids importing service modules just to check if
    they exist, which is pretty slow.
    """

    @classmethod
    @cache
    def get(cls, name: str) -> Service | None:
        """Load and return a service by name.

        Importing the service module triggers class registration. Returns
        ``None`` if the service cannot be imported or no service class exists.
        """
        eps = entry_points(
            group=cls.GROUP,
            name=name,
        )

        if not eps:
            return None
        try:
            service_cls = next(iter(eps)).load()
        except (DependencyError, ModuleNotFoundError):
            return None

        return service_cls()

    @classmethod
    @cache
    def all(cls) -> dict[str, Service]:
        """Return a mapping of service names to service instances.

        This will import all available service modules to trigger registration.
        """
        services: dict[str, Service] = {}

        for ep in entry_points(group=cls.GROUP):
            try:
                service_cls: type[Service] = ep.load()
            except (DependencyError, ModuleNotFoundError):
                continue

            services[ep.name] = service_cls()

        return services
