"""YAML configuration management for the plistsync CLI.

Uses the ``eyconf`` library to load and validate the configuration file. The
plain dataclasses live in :mod:`plistsync.core.config` and
:mod:`plistsync.logger`; this module owns everything that is specific to the
CLI: file locations and the disk-backed loading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, make_dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, TypeVar

from eyconf import EYConf
from eyconf.decorators import allow_additional
from platformdirs import user_config_dir

from plistsync.core.config import ServiceConfig
from plistsync.logger import LoggingConfig, log
from plistsync.services import ServiceLoader

C = TypeVar("C", bound=ServiceConfig)


@dataclass
class BaseConfigSchema:
    """The configuration schema for plistsync.

    The ``services`` field is dynamically populated at runtime from registered
    :class:`ServiceConfig` subclasses. The schema is reconstructed and the
    configuration reloaded every time a new service is first accessed.

    This class serves as the type-hint base so that ``config.data.logging``
    is properly typed. The ``services: dict[str, ServiceConfig]`` annotation is
    a placeholder for type-checkers; at runtime the field is overridden by a
    dynamically-built dataclass with one named field per service (e.g.
    ``plex: PlexConfig | None``).
    """

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    services: dict[str, ServiceConfig] = field(default_factory=dict)


class Config(EYConf[BaseConfigSchema]):
    """Plistsync configuration class.

    This class is responsible for loading and validating the configuration.
    For more information see `EYConf <https://github.com/semohr/eyconf>`_.

    Services referenced in the config file are auto-discovered at init time
    by importing their packages via :class:`~plistsync.services.ServiceLoader`.
    Any service that cannot be imported (e.g. missing optional dependency) is
    silently ignored.

    The ``services`` section is built dynamically and is therefore typed as ``Any``.
    """

    @staticmethod
    @cache
    def get_dir() -> Path:
        """Return the path to the plistsync config directory.

        The configuration file and stored authentication tokens live here.
        We check if the following folders exist to determine the config
        directory:

        1. PSYNC_CONFIG_DIR environment variable
        2. OS-specific global config directory
        """
        if env_dir := os.getenv("PSYNC_CONFIG_DIR"):
            path = Path(env_dir)
        else:
            path = Path(user_config_dir("plistsync", appauthor=False))

        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    @staticmethod
    def get_file() -> Path:
        """Return the path to the configuration file.

        Overrides the eyconf default so the config lives in the plistsync
        config directory. Called by eyconf during instantiation.
        """
        return Config.get_dir() / "config.yaml"

    # ---------- instantiation -------------------------------------------------

    def __init__(self, preload_services: bool = False) -> None:
        log.debug(f"Using config dir: {Config.get_dir()}")

        if preload_services:
            log.debug("Preloading all discoverable services...")
            ServiceLoader.all()

        super().__init__(self._build_schema())

    # ------------------------------ Dynamic schema ------------------------------ #
    # To allow lazy loading our config from different services we need
    # to be able to dynamically build our schema

    @classmethod
    def _build_schema(cls) -> type:
        """Build the full ``ConfigSchema`` dataclass from the current registry.

        Only :class:`ServiceConfig` subclasses that have already been imported
        (and therefore registered via ``__init_subclass__``) are included.
        """
        services_fields: list[tuple[str, type[ServiceConfig], ServiceConfig]] = []
        for service_name, config_classes in ServiceConfig.registry().items():
            config_cls = config_classes[0]
            services_fields.append(
                (service_name, config_cls, field(default_factory=config_cls))
            )

        """
        Dynamically build a dataclass that holds all services, looks roughtly like this:

        class ServiceConfig
            spotify: SpotifyConfig
            tidal: TidalConfig
            ... remaining services_fields

        `allow_additional(...)` is needed, because we do not want to crash when config
        options exist e.g. for spotify, but the service is not loaded/installed.
        """
        DynamicServicesConfig: type = allow_additional(  # noqa: N806
            make_dataclass(
                "ServicesConfig",
                services_fields,
                namespace={
                    # dict like access to the services dataclass
                    "get": lambda self, key, default=None: getattr(self, key, default),
                    "__getitem__": lambda self, key: getattr(self, key),
                    "__contains__": lambda self, key: hasattr(self, key),
                    # `__module__` is required for forward-reference
                    # resolution on Python < 3.12, where
                    # `make_dataclass` does not set it automatically.
                    "__module__": cls.__module__,
                },
            )
        )

        return make_dataclass(
            "ConfigSchema",
            [
                (
                    "services",
                    Annotated[
                        DynamicServicesConfig,
                        "Optional services:",
                        "plistsync works without any of the services but using",
                        "some of them will improve matching tremendously",
                        "See the setup guide for more information!",
                    ],
                    field(default_factory=DynamicServicesConfig),
                ),
            ],
            bases=(BaseConfigSchema,),
            namespace={"__module__": cls.__module__},
        )

    def get_config_for(self, config_cls: type[C]) -> C:
        """Get the config instance for a service config class.

        Convenience for callers that know the config class but not the
        service name.

        Raises
        ------
        ValueError
            If the config class is not registered.
        """
        for service_name, config_classes in ServiceConfig.registry().items():
            if config_cls in config_classes:
                return self.get_service_config(service_name)  # type: ignore[return-value]

        raise ValueError(f"Service config {config_cls.__name__} is not registered.")

    def get_service_config(self, service_name: str) -> ServiceConfig:
        """Get the service config instance for a given service name.

        On first access, the service package is imported (triggering
        :class:`ServiceConfig` registration), the schema is rebuilt to include
        the new service, the configuration file is re-read and re-validated,
        and the resulting instance is returned.

        Parameters
        ----------
        service_name : str
            The name of the service (e.g. ``"plex"``, ``"spotify"``).

        Returns
        -------
        ServiceConfig
            The concrete service config instance.

        Raises
        ------
        ValueError
            If the service is not registered or has no config schema.
        ConfigurationError
            If the service is not enabled in the configuration.
        """
        # Already in the schema: fast return
        if service_config := self.data.services.get(service_name):
            return service_config

        # Discover the service (loads its module, registers config class)
        service = ServiceLoader.get(service_name)
        if service is None:
            raise ValueError(f"Service {service_name!r} is not registered.")

        config_cls = service.config()
        if config_cls is None:
            raise ValueError(
                f"Service {service_name!r} has no config schema registered."
            )

        # Append the new service to the schema and reload
        self._schema = self._build_schema()
        self.reload()

        # Now the config should be loaded and accessible
        if service_config := self.data.services.get(service_name):
            return service_config

        raise ValueError(
            f"Service {service_name!r} is registered but has no config instance."
        )

    def default_yaml(self):
        """Overwrite to load all optional services.

        We load all optional services to make it easier for users to see what
        services are available and how to configure them.
        """
        ServiceLoader.all()
        self._schema = self._build_schema()
        return super().default_yaml()


__all__ = [
    "BaseConfigSchema",
    "Config",
]
