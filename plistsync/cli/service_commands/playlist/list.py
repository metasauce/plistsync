"""``playlist list`` command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.visualization import render_playlists, stdout_console
from plistsync.errors import HowTheForkDidYouEndUpHereError

if TYPE_CHECKING:
    import typer


def register_list_command(app: typer.Typer) -> None:
    """Register the ``list`` command (and its ``ls`` alias)."""

    @app.command(name="ls", hidden=True)
    @app.command(name="list")
    def list_playlists(ctx: ServiceCommandContext) -> None:
        """List all playlists in the service library."""
        service_name = ctx.obj.name
        library = ctx.obj.library

        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service_name!r} provides no library, but the 'list'"
                "command was invoked."
            )

        console = stdout_console()

        playlists = list(library.playlists)
        if not playlists:
            console.print(f"No playlists found in your {service_name} library.")
            return

        console.print(render_playlists(playlists, title=f"{service_name} playlists"))
