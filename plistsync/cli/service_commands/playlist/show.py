"""``playlist show`` command."""

from __future__ import annotations

import typer

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.parsing import autocompletion_playlist, parse_playlist
from plistsync.cli.visualization import stdout_console, to_rich
from plistsync.errors import HowTheForkDidYouEndUpHereError


def _autocompletion_playlist(ctx: ServiceCommandContext, incomplete: str) -> list[str]:
    library = ctx.obj.library
    if library is None:
        return []

    return autocompletion_playlist(incomplete, library)


def register_show_command(app: typer.Typer) -> None:
    """Register the ``show`` command."""

    @app.command(name="show")
    def show(
        ctx: ServiceCommandContext,
        playlist: str = typer.Argument(
            ...,
            help="Playlist to update (name, serial, URL or URI).",
            autocompletion=_autocompletion_playlist,
        ),
    ) -> None:
        """List all playlists in the service library."""
        service_name = ctx.obj.name
        library = ctx.obj.library

        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service_name!r} provides no library, but the 'list'"
                "command was invoked."
            )

        console = stdout_console()
        service_playlist = parse_playlist(playlist, library)
        if service_playlist is None:
            raise typer.BadParameter(f"No playlist found matching {playlist!r}.")

        console.print(to_rich(service_playlist.get_snapshot()))
