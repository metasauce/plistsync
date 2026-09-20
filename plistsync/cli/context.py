"""Service-scoped CLI context."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from plistsync.config import ServiceConfig
    from plistsync.core import Library
    from plistsync.services import Service


@dataclass(frozen=True)
class ServiceContext:
    """Service of the current CLI invocation."""

    service: Service

    @cached_property
    def library(self) -> Library | None:
        """Instantiate the service's library, if it supports one."""
        library_cls = self.service.library()
        return library_cls() if library_cls is not None else None

    @cached_property
    def config(self) -> ServiceConfig | None:
        """Resolve the service's config, if it supports one."""
        config_cls = self.service.config()
        return config_cls.get() if config_cls is not None else None

    @property
    def name(self) -> str:
        """Service name, inferred from the module (e.g. 'spotify', 'plex')."""
        return self.service.name


class ServiceCommandContext(typer.Context):
    """Typer context for service commands, with a typed service object."""

    obj: ServiceContext
