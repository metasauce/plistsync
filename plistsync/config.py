"""Plistsync configuration management using YAML files.

We use the `eyconf` library to handle configuration loading and validation.
For more information see `EYConf <https://github.com/semohr/eyconf>`_.
"""

from __future__ import annotations

import os
from abc import ABC
from dataclasses import dataclass, field, make_dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, Self

from eyconf import EYConf
from eyconf.decorators import allow_additional
from platformdirs import user_config_dir

from plistsync.logger import log
from plistsync.services import ServiceLoader
from plistsync.services.registry import Registry

# ---------------------------------------------------------------------------- #
#                            Schema building-block                             #
# ---------------------------------------------------------------------------- #


@dataclass
class ServiceConfig(ABC, Registry):
    """Base class for service configurations.

    Classes that inherit from this class will automatically be included in the config
    schema and can be validated/used.
    """

    @classmethod
    def get(cls) -> Self:
        """Get the service config instance from the global config.

        Convenience classmethod so that callers can write
        ``PlexConfig.get()`` instead of manually plumbing the
        singleton :class:`Config` instance.
        """
        config: Config = Config()

        for service_name, config_classes in cls.registry().items():
            if cls in config_classes:
                service_config = config.get_service_config(service_name)
                return service_config  # type: ignore[return-value]

        raise ValueError(f"Service config {cls.__name__} is not registered.")


@dataclass
class LoggingConfig:
    level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"],
        "Log level to set when `enabled=True` (one of: DEBUG, INFO, WARNING, ERROR,"
        "CRITICAL, NOTSET); INFO is recommended for production, DEBUG is useful for "
        "troubleshooting.",
    ] = field(default="INFO")
    handler: Annotated[
        Literal["basic", "rich"],
        "Logging backend to initialize when `enabled=True`: 'basic' uses standard "
        "library logging with plain text output to stderr, while 'rich' uses "
        "RichHandler for nicer console formatting (and richer tracebacks if enabled).",
    ] = field(default="rich")


@dataclass
class BaseConfigSchema:
    """The configuration schema for plistsync.

    The static fields (``logging``, ``redirect_port``) are always present.
    The ``services`` field is dynamically populated at runtime from registered
    :class:`ServiceConfig` subclasses.  The schema is reconstructed — and the
    configuration reloaded — every time a new service is first accessed.

    This class serves as the type-hint base so that ``config.data.logging``
    and ``config.data.redirect_port`` are properly typed.  The
    ``services: dict[str, ServiceConfig]`` annotation is a placeholder for
    type-checkers; at runtime the field is overridden by a dynamically-built
    dataclass with one named field per service (e.g. ``plex: PlexConfig | None``).
    """

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    redirect_port: Annotated[int, "The port used for authentication callbacks"] = field(
        default=5001
    )
    services: dict[str, ServiceConfig] = field(default_factory=dict)


# ---------------------------------------------------------------------------- #
#                                 Config class                                 #
# ---------------------------------------------------------------------------- #
# Uses the eyconf library to handle configuration


class Config(EYConf[BaseConfigSchema]):
    """Plistsync configuration class.

    This class is responsible for loading and validating the configuration.
    For more information see `EYConf <https://github.com/semohr/eyconf>`_.

    Services referenced in the config file are auto-discovered at init time
    by importing their packages via :class:`~plistsync.services.ServiceLoader`.
    Any service that cannot be imported (e.g. missing optional dependency) is
    silently ignored.

    Type hints for static fields (``logging``, ``redirect_port``) come
    from :class:`BaseConfigSchema`.  The ``services`` section is built
    dynamically and is therefore typed as ``Any``.
    """

    # ---------- instantiation -------------------------------------------------

    def __init__(self, preload_services: bool = False) -> None:
        log.debug(f"Using config dir: {self.get_dir()}")

        if preload_services:
            log.debug("Preloading all discoverable services...")
            ServiceLoader.all()

        super().__init__(self._build_schema())

    # ------------------------------ Config helpers ------------------------------ #

    @property
    def redirect_port(self) -> int:
        return self.data.redirect_port

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

        DynamicServicesConfig: type = allow_additional(  # noqa: N806
            make_dataclass(
                "ServicesConfig",
                services_fields,
                namespace={
                    # dict like access to the services dataclass
                    "get": lambda self, key, default=None: getattr(self, key, default),
                    "__getitem__": lambda self, key: getattr(self, key),
                    "__contains__": lambda self, key: hasattr(self, key),
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
        )

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

    # ---------------------- Overwrites for config location ---------------------- #
    # Eyconf uses the get_file method but we also add a get_dir as we allow storing
    # additional files in the main config dir

    @staticmethod
    @cache
    def get_dir() -> Path:
        """Get the path to the config directory.

        We check if the following folders exist to
        determine the config directory:

        1. PSYCNC_CONFIG_DIR environment variable
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
        """Get OS-specific global config directory."""
        dir = Config.get_dir()
        return dir / "config.yaml"


__all__ = [
    "BaseConfigSchema",
    "Config",
    "LoggingConfig",
    "ServiceConfig",
]
