from __future__ import annotations

import inspect
from abc import ABC
from functools import cache
from typing import ClassVar, Self


class Registry:
    """Automatically register concrete subclasses by service.

    Each abstract subclass of :class:`Registry` defines its own independent
    registry. Concrete implementations are automatically registered when the
    class is created.

    The service name is derived from the module path::

        plistsync.services.<service>.*

    Subclasses may override this by providing an explicit ``service`` value.

    Example:

        .. code-block:: python

            class PlaylistId(ABC, Registry):
                ...

            # plistsync.services.spotify.ids
            class SpotifyPlaylistId(PlaylistId):
                ...

            # plistsync.services.apple.ids
            class ApplePlaylistId(PlaylistId):
                ...

            PlaylistId.registry() == {
                "spotify": [SpotifyPlaylistId],
                "apple": [ApplePlaylistId],
            }

    Abstract subclasses become registry roots and are not registered
    themselves. Only concrete subclasses are added to the registry.
    """

    _REGISTRY: ClassVar[dict[type, dict[str, list[type]]]] = {}
    """Global registry for storing **all** registered classes."""

    _registry: ClassVar[type[Registry] | None] = None
    """Semi global registry key for this class and its subclasses.
    Subclasses must define this but this can be overridden in subclasses to
    register under a different key."""

    def __init_subclass__(
        cls,
        *,
        service: str | None = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)

        # Abstract bases become the registry key for their concrete subclasses.
        if inspect.isabstract(cls) or ABC in cls.__bases__:
            cls._registry = cls
            return

        if cls._registry is None:
            raise ValueError(
                f"Cannot register {cls.__name__!r}, it does not define a registry key."
            )

        service_name = service or cls.service()

        registry_bucket = cls._REGISTRY.setdefault(cls._registry, {})
        registry_bucket.setdefault(service_name, []).append(cls)

    @classmethod
    @cache
    def service(cls) -> str:
        """Return the service name for this class."""
        module_str = cls.__module__
        if not module_str.startswith("plistsync.services."):
            raise ValueError(f"Cannot derive service name for {cls.__name__!r}")

        return module_str.split(".")[2]

    @classmethod
    def registry(cls) -> dict[str, list[type[Self]]]:
        """Return the registry for this class."""
        if cls._registry is None:
            raise ValueError(f"Cannot get registry for {cls.__name__!r}, not defined!")
        return cls._REGISTRY.setdefault(cls._registry, {})
