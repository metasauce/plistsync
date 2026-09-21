"""Shared fixtures for the CLI tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from plistsync.cli import app as plist_app
from plistsync.cli.service_commands import cli_service_factory
from plistsync.config import Config

if TYPE_CHECKING:
    from collections.abc import Callable

    import typer

    from plistsync.services import Service


@pytest.fixture
def runner() -> CliRunner:
    """A runner for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def cli_app() -> typer.Typer:
    """The root plistsync CLI app. Services are loaded lazily."""
    return plist_app


@pytest.fixture
def service_app() -> Callable[[Service], typer.Typer]:
    """Build a single service's command app, as the CLI mounts it."""
    return cli_service_factory


@pytest.fixture
def config() -> Config:
    """A loaded config, so resolving service configs does not bootstrap one."""
    return Config()
