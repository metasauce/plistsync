"""``search playlist`` command."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import typer

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.parsing import parse_playlist_id
from plistsync.cli.visualization import render_playlists, stdout_console
from plistsync.errors import HowTheForkDidYouEndUpHereError

if TYPE_CHECKING:
    from plistsync.core import Library


def register_playlist_search_command(
    app: typer.Typer,
    *,
    command_name: str = "playlist",
) -> None:
    """Register the ``playlist`` search command."""

    @app.command(name=command_name, no_args_is_help=True)
    def search_playlist(
        ctx: ServiceCommandContext,
        arg: str | None = typer.Argument(
            None,
            help="Service playlist ID or URL.",
        ),
        playlist_id: str | None = typer.Option(
            None,
            "--id",
            help="Service playlist ID or URL.",
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            "-n",
            help="Regular expression matching the playlist name.",
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            "-d",
            help="Regular expression matching the playlist description.",
        ),
    ) -> None:
        """Search playlists by ID, name, or description patterns.

        ID and pattern criteria can be combined; playlists matching any
        provided criterion are returned.
        """
        library: Library | None = ctx.obj.library
        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {ctx.obj.name!r} provides no library, but the "
                "'search playlist' command was invoked."
            )

        console = stdout_console()

        playlists = []
        id_value = playlist_id or arg
        if id_value is not None:
            parsed_id = parse_playlist_id(id_value, ctx.obj.service)
            if parsed_id is None:
                raise typer.BadParameter(
                    f"Invalid playlist ID for {ctx.obj.name}: {id_value!r}",
                    param_hint="--id",
                )

            if (playlist := library.get_playlist(id=id_value)) is not None:
                playlists.append(playlist)

        if id_value is None and name is None and description is None:
            raise typer.BadParameter(
                "At least one of --id, --name, or --description must be provided."
            )

        try:
            name_pattern = re.compile(name) if name is not None else None
            description_pattern = (
                re.compile(description) if description is not None else None
            )
        except re.error as exc:
            raise typer.BadParameter(f"Invalid regular expression: {exc}") from exc

        for playlist in library.playlists:
            matches_pattern = (
                name_pattern is not None and name_pattern.search(playlist.name)
            ) or (
                description_pattern is not None
                and playlist.description is not None
                and description_pattern.search(playlist.description)
            )
            if matches_pattern and playlist not in playlists:
                playlists.append(playlist)

        console.print(render_playlists(playlists, title=f"{ctx.obj.name} playlists"))
