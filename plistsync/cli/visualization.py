"""Rich rendering for plistsync domain objects."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, overload

import typer
from rich.console import Console, Group
from rich.markup import escape
from rich.prompt import Confirm
from rich.protocol import rich_cast
from rich.table import Table
from rich.text import Text

from plistsync.core.diff import DeleteOp, InsertOp, MoveOp, Operations
from plistsync.core.ids import PlaylistID, TrackID
from plistsync.core.playlist import Snapshot

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rich.console import RenderableType

    from plistsync.core.playlist import Playlist
    from plistsync.core.track import Track

__all__ = [
    "confirm_or_abort",
    "render_playlists",
    "render_tracks",
    "stdout_console",
    "to_rich",
]


def stdout_console() -> Console:
    """Console writing to stdout without highlighting."""
    return Console(file=sys.stdout, highlight=False)


def confirm_or_abort(
    console: Console,
    *renderables: RenderableType,
    yes: bool,
    default: bool,
    prompt: str = "Continue?",
) -> None:
    """Print the pending change and ask for confirmation unless ``yes``.

    Parameters
    ----------
    console
        Console used for output and the prompt.
    *renderables
        What the command is about to do; printed above the prompt.
    yes
        Skip the prompt entirely (``--yes``).
    default
        Default answer if the user just presses enter.
    prompt
        Prompt text.

    Raises
    ------
    typer.Exit
        With code 1 if the user declines.
    """
    if yes:
        return

    for renderable in renderables:
        console.print(renderable)

    if not Confirm.ask(prompt, default=default, console=console):
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit(code=1)


def _table(title: str | None = None) -> Table:
    return Table(
        title=title,
        title_justify="left",
        title_style="bold cyan",
        show_header=True,
        box=None,
        padding=(0, 2),
        header_style="dim",
    )


@overload
def to_rich(obj: TrackID | PlaylistID) -> Text: ...
@overload
def to_rich(obj: object) -> RenderableType: ...
def to_rich(obj: object) -> RenderableType:
    """Render common plistsync objects, passing unknown objects through."""
    if isinstance(obj, (TrackID, PlaylistID)):
        return _render_id(obj)
    if isinstance(obj, Snapshot):
        return _render_snapshot(obj)
    if isinstance(obj, Operations):
        return _render_operations(obj)
    return rich_cast(obj)


def _render_id(obj: TrackID | PlaylistID) -> Text:
    if url := getattr(obj, "url", None):
        return Text(obj.serial, style=f"link {url}")
    return Text(obj.serial)


def _render_snapshot(obj: Snapshot) -> RenderableType:
    details = Table.grid(padding=(0, 2))
    details.add_column(style="bold cyan", no_wrap=True)
    details.add_column()
    details.add_row("Name", escape(obj.name))
    details.add_row("Description", escape(obj.description or "-"))
    details.add_row("Tracks", str(len(obj.tracks)))
    if not obj.tracks:
        return details
    return Group(details, render_tracks(obj.tracks))


def _render_operations(obj: Operations) -> RenderableType:
    ops = [step.op for step in obj.iter()]
    if not ops:
        return Text("No track changes.", style="yellow")

    deletes = sorted(
        (op for op in ops if isinstance(op, DeleteOp)), key=lambda op: op.idx
    )
    inserts = [op for op in ops if isinstance(op, InsertOp)]
    moves = [op for op in ops if isinstance(op, MoveOp)]

    table = _table()
    table.add_column("Change", no_wrap=True)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Artist", style="bold")
    table.add_column("Title")
    table.add_column("ID", style="cyan", overflow="fold")

    def add_row(change: str, index: str, track: Track) -> None:
        table.add_row(
            change,
            index,
            escape(track.primary_artist or ""),
            escape(track.title or ""),
            _render_track_ids(track.ids),
        )

    for op in deletes:
        add_row("[red]removed[/red]", str(op.idx), op.item)
    for op in inserts:
        add_row("[green]added[/green]", str(op.idx), op.item)
    for op in moves:
        add_row("[blue]moved[/blue]", f"{op.old_idx} \u2192 {op.new_idx}", op.item)

    return table


def _render_track_ids(ids: Iterable[TrackID]) -> Text:
    """All ids, linkable first, comma separated."""
    ordered = sorted(
        ids,
        key=lambda identifier: (
            getattr(identifier, "url", None) is None,
            identifier.serial,
        ),
    )
    if not ordered:
        return Text("-")

    text = Text()
    for index, identifier in enumerate(ordered):
        if index:
            text.append(", ")
        text.append_text(to_rich(identifier))
    return text


def render_tracks(tracks: Iterable[Track], *, title: str | None = None) -> Table:
    """Build a table listing tracks with artist and title."""
    table = _table(title)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Artist", style="bold")
    table.add_column("Title")
    table.add_column("ID", style="cyan", overflow="fold")

    for index, track in enumerate(tracks):
        table.add_row(
            str(index),
            escape(track.primary_artist or ""),
            escape(track.title or ""),
            _render_track_ids(track.ids),
        )

    return table


def render_playlists(
    playlists: Iterable[Playlist], *, title: str | None = None
) -> Table:
    """Build a table listing playlists with name, description and linked id."""
    table = _table(title)
    table.add_column("Name", style="bold", max_width=40, overflow="fold")
    table.add_column("Description", max_width=40, overflow="fold")
    table.add_column("Tracks")
    table.add_column("ID", style="cyan", no_wrap=True)

    for playlist in playlists:
        table.add_row(
            escape(playlist.name),
            escape(playlist.description or "-"),
            str(len(playlist)),
            to_rich(playlist.id),
        )

    return table
