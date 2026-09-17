"""CLI commands for each plistsync services.

Commands are based on the services capabilities, and are only available if the service
is installed and configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from plistsync.cli.service_commands.library import library_typer_factory
from plistsync.errors import HowTheForkDidYouEndUpHereError

from .auth import auth_command_factory

if TYPE_CHECKING:
    from plistsync.services import Service


def cli_service_factory(service: Service) -> typer.Typer:
    """Build the Typer app with all commands supported by a service."""
    app = typer.Typer(
        name=service.name,
        help=f"Commands for the {service.name} service.",
        no_args_is_help=True,
    )

    # Resolve the service config once, here, so the commands below receive
    # configured providers instead of looking their config up themselves.
    config_cls = service.config()
    config = config_cls.get() if config_cls is not None else None

    if (auth_provider_cls := service.auth()) is not None:
        if config is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service.name!r} provides auth but no config."
            )
        app.command()(auth_command_factory(auth_provider_cls, config))

    app.add_typer(library_typer_factory(service))

    return app
