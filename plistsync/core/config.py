"""Service configuration base classes.

Defines :class:`ServiceConfig`, the dataclass base that services subclass to
declare their settings. Library consumers construct these in code; the CLI
loads them from the YAML configuration file (see :mod:`plistsync.cli.config`).
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING

from plistsync.services.registry import Registry

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ServiceConfig(ABC, Registry):
    """Base class for service configurations.

    Classes that inherit from this class will automatically be included in the
    CLI config schema and can be validated/used.
    """

    @property
    def token_path(self) -> Path:
        """Path to the stored authentication token for this service.

        Token storage is a plistsync-wide convention, but the config directory
        itself is resolved by the CLI, which is why the import is lazy. A bit
        inconsistent but the best I could come up with right now!
        """
        from plistsync.cli.config import Config

        return Config.get_dir() / f"{self.service().lower()}_token.json"
