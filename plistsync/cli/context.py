"""Service-scoped CLI context."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from plistsync.core import Library
    from plistsync.core.config import ServiceConfig
    from plistsync.services import Service


@dataclass(frozen=True)
class ServiceContext:
    """Service of the current CLI invocation."""

    service: Service

    @cached_property
    def library(self) -> Library | None:
        """Instantiate the service's library, if it supports one."""
        library_cls = self.service.library()
        if library_cls is None:
            return None

        config_cls = self.service.config()
        config = Config().get_config_for(config_cls) if config_cls is not None else None
        return library_cls.from_config(config)

    @cached_property
    def config(self) -> ServiceConfig | None:
        """Resolve the service's config, if it supports one."""
        from plistsync.cli.config import UserDirConfigIO

        config_cls = self.service.config()
        if config_cls is None:
            return None
        return UserDirConfigIO().load(config_cls)

    @property
    def name(self) -> str:
        """Service name, inferred from the module (e.g. 'spotify', 'plex')."""
        return self.service.name


class ServiceCommandContext(typer.Context):
    """Typer context for service commands, with a typed service object."""

    obj: ServiceContext
