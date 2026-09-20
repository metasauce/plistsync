"""CLI commands for each plistsync services.

Commands are based on the services capabilities, and are only available if the service
is installed and configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ..context import ServiceContext
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

    @app.callback()
    def _service_context(ctx: typer.Context) -> None:
        ctx.obj = ServiceContext(service)

    if (auth_provider_cls := service.auth()) is not None:
        app.command()(auth_command_factory(auth_provider_cls))

    return app
