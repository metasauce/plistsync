"""Playlist management commands for a service."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Annotated, TypeVar

import typer
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt
from rich.table import Table

from plistsync.core import TrackID
from plistsync.core.collection import IDLookup
from plistsync.logger import log

if TYPE_CHECKING:
    from collections.abc import Sequence

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

    return app
