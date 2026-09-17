"""CLI commands for each plistsync services.

Commands are based on the services capabilities, and are only available if the service
is installed and configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ..context import ServiceContext
from plistsync.cli.service_commands.library import library_typer_factory
from plistsync.errors import HowTheForkDidYouEndUpHereError

from .auth import auth_command_factory
from .playlist import playlist_command_factory

if TYPE_CHECKING:
    from plistsync.services import Service


def cli_service_factory(service: Service) -> typer.Typer:
    """Build the Typer app with all commands supported by a service."""
    app = typer.Typer(
        name=service.name,
        help=f"Commands for the {service.name} service.",
        no_args_is_help=True,
    )

    @app.callback()
    def _service_context(ctx: typer.Context) -> None:
        ctx.obj = ServiceContext(service)

    if (auth_provider_cls := service.auth()) is not None:
        app.command()(auth_command_factory(auth_provider_cls))

    if (library_cls := service.library()) is not None:
        app.add_typer(playlist_command_factory(library_cls))

    app.add_typer(library_typer_factory(service))

    return app
