"""Library command factory and its terminal interaction.

Services with a library expose ``plistsync <service> library``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated

import typer

from plistsync.core.collection import InfoLookup

if TYPE_CHECKING:
    from plistsync.services import Service


def library_typer_factory(service: Service):
    library_app = typer.Typer(
        name="library",
        help="Work with the library.",
        pretty_exceptions_show_locals=False,
        no_args_is_help=True,
    )

    if library_cls := service.library():
        library = library_cls()
    else:
        return library_app

    @library_app.command()
    def list_playlists():
        for p in library.playlists:
            typer.echo(f"{p!r}")

    @library_app.command()
    def search_playlist(
        query: Annotated[
            str,
            typer.Argument(
                help="How to search for playlists in your library",
            ),
        ],
    ):
        try:
            pattern = re.compile(query)
        except re.error as exc:
            raise typer.BadParameter(f"Invalid regular expression: {exc}") from exc

        for p in library.playlists:
            if pattern.search(p.name) or (
                p.description is not None and pattern.search(p.description)
            ):
                typer.echo(f"{p!r}")

    if isinstance(library, InfoLookup):

        @library_app.command()
        def search_track(
            query: Annotated[
                str,
                typer.Argument(
                    help="How to search for tracks in your library",
                ),
            ],
        ):
            results = library.find_many_by_info([{"title": query}])
            count = 0
            for tracks in results:
                for track in tracks:
                    typer.echo(f"{track.ids!r} {track!r}")
                    count += 1
                    if count == 3:
                        return

    return library_app
