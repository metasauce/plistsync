"""``playlist remove`` command."""

from __future__ import annotations

import typer
from rich.markup import escape

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.options import (
    YesOption,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.parsing import autocompletion_playlist, parse_playlist
from plistsync.cli.visualization import confirm_or_abort, stdout_console
from plistsync.errors import HowTheForkDidYouEndUpHereError


def _autocompletion_playlist(ctx: ServiceCommandContext, incomplete: str) -> list[str]:
    library = ctx.obj.library
    if library is None:
        return []

    return autocompletion_playlist(incomplete, library)


def register_remove_command(app: typer.Typer) -> None:
    """Register the ``remove`` command (and its ``rm`` alias)."""

    @app.command(name="rm", hidden=True)
    @app.command(name="remove")
    def remove(
        ctx: ServiceCommandContext,
        playlist: str = typer.Argument(
            ...,
            help="Playlist to remove (name, serial, URL or URI).",
            autocompletion=_autocompletion_playlist,
        ),
        yes: YesOption = False,
    ) -> None:
        """Remove a playlist from the service library."""
        service_name = ctx.obj.name
        library = ctx.obj.library

        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service_name!r} provides no library, but the 'remove'"
                "command was invoked."
            )

        service_playlist = parse_playlist(playlist, library)
        if service_playlist is None:
            raise typer.BadParameter(f"No playlist found matching {playlist!r}.")

        console = stdout_console()

        confirm_or_abort(
            console,
            f"Removing playlist [bold]{escape(repr(service_playlist.name))}[/bold] "
            f"(id: [cyan]{service_playlist.id.serial}[/cyan]).",
            yes=yes,
            default=False,
        )

        removed = service_playlist.delete()

        console.print(
            f"Removed playlist [bold]{escape(repr(removed.name))}[/bold] "
            f"(id: [cyan]{removed.id.serial}[/cyan])."
        )
