"""Playlist management commands for a service."""

from __future__ import annotations

import sys
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, TypeVar

import typer
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Typer vendors its own click fork, so the parameter type must come from there.
from typer._click.shell_completion import CompletionItem
from typer._click.types import ParamType

from plistsync.core import ServicePlaylist, TrackID
from plistsync.core.collection import IDLookup
from plistsync.logger import log

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

    from typer._click import Context, Parameter

    from plistsync.core import Library, Track

    T = TypeVar("T", bound=Track)


def print_summary(
    console: Console,
    name: str,
    description: str | None,
    tracks: Sequence[T],
) -> None:
    """Print the playlist that is about to be created, with all its tracks."""
    details = Table.grid(padding=(0, 2))
    details.add_column(style="bold cyan", no_wrap=True)
    details.add_column()
    details.add_row("Name", escape(repr(name)))
    details.add_row("Description", escape(description or "-"))
    details.add_row("Tracks", str(len(tracks)))
    console.print(details)

    if not tracks:
        return

    table = Table(show_header=True, box=None, padding=(0, 2), header_style="dim")
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Artist", style="bold")
    table.add_column("Title")
    for idx, track in enumerate(tracks):
        table.add_row(
            str(idx),
            escape(track.primary_artist or ""),
            escape(track.title or ""),
        )
    console.print(table)


def parse_track_id(
    value: str, track_id_cls: Sequence[type[TrackID]] = ()
) -> TrackID | None:
    """Try to parse a track identifier from a string.

    TODO: Maybe we want to move this into the service layer
    """
    for id_cls in track_id_cls:
        try:
            return id_cls.parse(value)
        except ValueError:
            continue

    return TrackID.from_serial(value)


class PlaylistArgument(ParamType):
    """Turn a playlist name, serial, URL or URI into a ``ServicePlaylist``."""

    name = "playlist"

    def __init__(self, library_cls: type[Library]) -> None:
        self.library_cls = library_cls

    @cached_property
    def library(self) -> Library:
        return self.library_cls()

    def convert(
        self, value: Any, param: Parameter | None, ctx: Context | None
    ) -> ServicePlaylist:
        if isinstance(value, ServicePlaylist):
            return value

        name_or_id = str(value)

        if playlist := self.library.get_playlist(id=name_or_id):
            return playlist

        if playlist := self.library.get_playlist(name=name_or_id):
            return playlist

        self.fail(f"No playlist found matching {name_or_id!r}.", param, ctx)

    def shell_complete(
        self, ctx: Context, param: Parameter, incomplete: str
    ) -> list[CompletionItem]:
        try:
            playlists = list(self.library.playlists)
        except Exception as e:
            # Completion runs inside the user's shell; never let it crash.
            log.debug("Playlist completion failed: %s", e)
            return []

        return [
            CompletionItem(value)
            for playlist in playlists
            for value in (playlist.name, playlist.id.serial)
            if not incomplete or value.startswith(incomplete)
        ]


def playlist_command_factory(
    library_cls: type[Library[T]], track_id_cls: Sequence[type[TrackID]]
) -> typer.Typer:
    """Build the ``playlist`` command group for a library."""
    library_name = library_cls.__name__.removesuffix("Library")

    app = typer.Typer(
        name="playlist",
        help=f"Create playlists in your {library_name} library.",
        no_args_is_help=True,
    )

    @app.command()
    def create(
        name: Annotated[
            str | None,
            typer.Option("--name", "-n", help="Name of the new playlist."),
        ] = None,
        description: Annotated[
            str | None,
            typer.Option("--description", "-d", help="Description of the playlist."),
        ] = None,
        add: Annotated[
            list[str] | None,
            typer.Option(
                "--add",
                "-a",
                help="Track to add: id/uri/url (repeatable).",
            ),
        ] = None,
        yes: Annotated[
            bool,
            typer.Option(
                "--yes",
                "-y",
                help="Skip the confirmation prompt.",
            ),
        ] = False,
    ) -> None:
        """Create a playlist in the service library.

        Prompts for missing name and description, then asks for confirmation.
        """
        library = library_cls()

        assert isinstance(library, IDLookup), (
            f"{library_cls!r} does not support lookup by track identifier."
        )

        console = Console(file=sys.stdout, highlight=False)

        if name is None:
            name = Prompt.ask("Playlist name", console=console)

        if description is None:
            description = (
                Prompt.ask(
                    "Description (optional)",
                    default="",
                    show_default=False,
                    console=console,
                )
                or None
            )

        # TODO: Allow to prompt for tracks

        # Parse ids: string -> TrackID
        ids: list[TrackID] = []
        for track_id_str in add or []:
            if track_id := parse_track_id(track_id_str, track_id_cls):
                ids.append(track_id)
            else:
                log.warning(
                    f"Could not parse track identifier {track_id_str!r}. Skipping."
                )

        # Parse tracks: TrackID -> Track
        tracks: list[T] = []
        for track, track_id in zip(library.find_many_by_ids([[id] for id in ids]), ids):
            if track is not None:
                tracks.append(track)
            else:
                log.warning(
                    f"Could not find track {track_id.serial!r} in library. Skipping."
                )

        # Confirmation prompt
        if not yes:
            print_summary(console, name, description, tracks)
            if not Confirm.ask("Continue?", default=True, console=console):
                console.print("[yellow]Aborted.[/yellow]")
                raise typer.Exit(code=1)

        playlist = library.create_playlist(
            name=name,
            description=description,
            tracks=tracks or None,
        )

        console.print(
            f"Created playlist [bold]{escape(repr(playlist.name))}[/bold] "
            f"(id: [cyan]{playlist.id.serial}[/cyan]) "
            f"with {len(playlist)} track(s)."
        )

    @app.command(name="rm", hidden=True)
    @app.command(name="remove")
    def remove(
        playlist: ServicePlaylist = typer.Argument(
            ...,
            help="Playlist to remove (name, serial, URL or URI).",
            click_type=PlaylistArgument(library_cls),
        ),
        yes: Annotated[
            bool,
            typer.Option(
                "--yes",
                "-y",
                help="Skip the confirmation prompt.",
            ),
        ] = False,
    ) -> None:
        """Remove a playlist from the service library."""
        console = Console(file=sys.stdout, highlight=False)

        if not yes:
            console.print(
                f"Removing playlist [bold]{escape(repr(playlist.name))}[/bold] "
                f"(id: [cyan]{playlist.id.serial}[/cyan])."
            )
            if not Confirm.ask("Continue?", default=False, console=console):
                console.print("[yellow]Aborted.[/yellow]")
                raise typer.Exit(code=1)

        removed = playlist.delete()

        console.print(
            f"Removed playlist [bold]{escape(repr(removed.name))}[/bold] "
            f"(id: [cyan]{removed.id.serial}[/cyan])."
        )

    return app
