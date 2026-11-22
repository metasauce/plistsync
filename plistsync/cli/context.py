"""Service-scoped CLI context."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache, cached_property
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from plistsync.core import Library
    from plistsync.core.config import ConfigIO, ServiceConfig
    from plistsync.services import Service


@cache
def get_config_io() -> ConfigIO:
    """Return the shared CLI config loader."""
    from plistsync.cli.config import UserDirConfigIO

    return UserDirConfigIO()


@dataclass(frozen=True)
class ServiceContext:
    """Service of the current CLI invocation."""

    service: Service

    @property
    def config_io(self) -> ConfigIO:
        """Shared config loader for this CLI invocation."""
        return get_config_io()

    @cached_property
    def library(self) -> Library | None:
        """Instantiate the service's library, if it supports one."""
        library_cls = self.service.library()
        if library_cls is None:
            return None

        return library_cls.from_config(self.config)

    @cached_property
    def config(self) -> ServiceConfig | None:
        """Resolve the service's config, if it supports one."""
        config_cls = self.service.config()
        if config_cls is None:
            return None
        return self.config_io.load(config_cls)

    @property
    def name(self) -> str:
        """Service name, inferred from the module (e.g. 'spotify', 'plex')."""
        return self.service.name


class ServiceCommandContext(typer.Context):
    """Typer context for service commands, with a typed service object."""

    obj: ServiceContext
