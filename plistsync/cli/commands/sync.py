"""Sync workflow subcommands.

Commands for creating named synced playlists, linking playlists across
services, inspecting track availability, diffing, and running
synchronisations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from platformdirs import user_config_dir
from rich.console import Console
from rich.table import Table

from plistsync.logger import log
from plistsync.services import ServiceLoader
from plistsync.services.sync import SyncedPlaylist

if TYPE_CHECKING:
    from collections.abc import Iterable

    from plistsync.core import PlaylistID
    from plistsync.services import Service


sync_app = typer.Typer(
    name="sync",
    help="Manage and run playlist synchronisations.",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


def _echo_markup(message: str) -> None:
    """Echo `message` using rich markup, colored only when stdout is a terminal.

    The console is created per call so it picks up the current stdout
    (e.g. the one patched by typer's ``CliRunner`` in tests) and renders
    plain text when output is redirected.
    """
    Console(file=sys.stdout, highlight=False).print(message)


def __sync_dir() -> Path:
    """Return the path to the sync directory in the user config dir."""
    sync_dir = Path(user_config_dir("plistsync", appauthor=False)) / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)
    return sync_dir


def __iter_all() -> Iterable[SyncedPlaylist]:
    """Yield every registered synced playlist from the sync directory."""
    sync_dir = __sync_dir()

    for id_path in sync_dir.glob("*.json"):
        try:
            yield SyncedPlaylist.load_from(id_path)
        except Exception:
            log.debug("Skipping unreadable sync file '%s'.", id_path.name)
            continue


def __find_synced_by_name_or_id(name_or_id: str) -> SyncedPlaylist:
    """Return the synced playlist matching the given name or ID."""
    matches = [
        playlist
        for playlist in __iter_all()
        if playlist.name == name_or_id or str(playlist.id) == name_or_id
    ]
    if len(matches) > 1:
        raise typer.BadParameter(
            f"Multiple synced playlists match {name_or_id!r}. "
            "Please specify the ID instead."
        )
    if not matches:
        raise typer.BadParameter(f"No synced playlist found matching {name_or_id!r}.")
    return matches[0]


@sync_app.command(name="mk", hidden=True)
@sync_app.command(name="create")
def create(
    name: str = typer.Argument(
        help="Name for the synced playlist.",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Optional description of the synced playlist.",
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output the result as JSON."
    ),
) -> None:
    """Create a named synced playlist.

    A synced playlist links playlists from different services together so
    they can be compared and synchronised.
    """
    sync_dir = __sync_dir()

    # Warn if a playlist with the same name already exists; IDs disambiguate.
    for path in sync_dir.glob("*.json"):
        try:
            existing = SyncedPlaylist.load_from(path)
        except Exception:
            log.warning("Skipping unreadable sync file '%s'.", path.name)
            continue
        if existing.name == name:
            log.warning(
                "A synced playlist named '%s' already exists (ID '%s').",
                name,
                existing.id,
            )

    synced_playlist = SyncedPlaylist(name=name, description=description)
    synced_playlist.save_to(sync_dir / f"{synced_playlist.id}.json")

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "id": str(synced_playlist.id),
                    "name": synced_playlist.name,
                    "description": synced_playlist.description,
                    "path": str(sync_dir / f"{synced_playlist.id}.json"),
                }
            )
        )
        return

    _echo_markup(
        f"Created synced playlist [bold]{synced_playlist.name}[/bold]\n"
        f"  ID:   [cyan]{synced_playlist.id}[/cyan]\n"
        f"  Next: [dim]plistsync sync register --id {synced_playlist.id}[/dim]"
    )


def _autocomplete_name_or_id(
    incomplete: str,
) -> list[str]:
    """Shell-complete the names and IDs of all synced playlists."""
    completions = []
    for playlist in __iter_all():
        if incomplete and not (
            playlist.name.startswith(incomplete)
            or str(playlist.id).startswith(incomplete)
        ):
            continue
        completions.append(playlist.name)
        completions.append(str(playlist.id))
    return completions


@sync_app.command(name="rm", hidden=True)
@sync_app.command(name="remove")
def remove(
    name_or_id: Annotated[
        str,
        typer.Argument(
            help="Name or ID of the synced playlist to remove.",
            autocompletion=_autocomplete_name_or_id,
        ),
    ],
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output the result as JSON."
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        "-y",
        help="Confirm removal without prompting.",
    ),
) -> None:
    """Remove a synced playlist.

    Deletes the JSON file of the synced playlist identified by its name or ID.
    """
    sync_dir = __sync_dir()
    plist = __find_synced_by_name_or_id(name_or_id)

    # Confirmation prompt
    if not confirm:
        _echo_markup(
            f"Are you sure you want to remove synced playlist [bold]{plist.name}[/bold]"
            f"(ID: [cyan]{plist.id}[/cyan])?\n[red]This cannot be undone![/red]"
        )
        if not typer.confirm("Confirm removal"):
            log.info("Aborting removal of synced playlist '%s'.", plist.name)
            raise typer.Exit(code=1)

    # Remove pl
    plist_path = sync_dir / f"{plist.id}.json"
    plist_path.unlink()

    # Print result
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "id": str(plist.id),
                    "name": plist.name,
                    "description": plist.description,
                    "path": str(plist_path),
                    "removed": True,
                }
            )
        )
    else:
        _echo_markup(
            f"Removed synced playlist [bold]{plist.name}[/bold] "
            f"(ID: [cyan]{plist.id}[/cyan])."
        )


@sync_app.command(name="ls", hidden=True)
@sync_app.command(name="list")
def list_(
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output synced playlists in JSON format.",
    ),
) -> None:
    """List all registered synced playlists."""
    log.debug("Listing all synced playlists")
    playlists = list(__iter_all())

    if json_output:
        typer.echo(
            json.dumps(
                [
                    {
                        "id": str(playlist.id),
                        "name": playlist.name,
                        "description": playlist.description,
                        "registered": playlist.n_linked,
                    }
                    for playlist in playlists
                ]
            )
        )
        return

    if not playlists:
        _echo_markup(
            "No synced playlists registered yet. "
            "Create one with [bold]plistsync sync create[/bold]."
        )
        return

    table = Table(title="Synced playlists")
    table.add_column("Name", style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Description")
    table.add_column("Registered")

    for playlist in playlists:
        table.add_row(
            playlist.name,
            str(playlist.id),
            playlist.description or "",
            str(playlist.n_linked),
        )

    Console(file=sys.stdout, highlight=False).print(table)


@sync_app.command(name="register")
def register(
    name_or_id: Annotated[
        str,
        typer.Argument(
            help="Name or ID of the synced playlist to show.",
            autocompletion=_autocomplete_name_or_id,
        ),
    ],
    playlist: Annotated[
        str,
        typer.Argument(
            help="Playlist to register: URL, URI, serial, or raw ID.",
        ),
    ],
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output the result as JSON."
    ),
) -> None:
    """Link a existing service playlist to a synced playlist.

    Merges the playlist's tracks into the synced playlist and pushes the
    internal state back to the linked playlist.
    """
    sync = __find_synced_by_name_or_id(name_or_id)

    # Parse service playlist
    id_matches: list[tuple[Service, PlaylistID]] = list()
    for service in ServiceLoader.all().values():
        for pl_id in service.playlist_ids():
            try:
                id_matches.append(
                    (
                        service,
                        pl_id.parse(playlist),
                    )
                )
            except Exception:
                log.debug(
                    "Failed to parse playlist '%s' as %s.%s",
                    playlist,
                    service.name,
                    pl_id.__name__,
                )

    # If multiple potential matches were found, raise an error.
    # If none were found, raise an error.
    if len(id_matches) > 1:
        raise typer.BadParameter(
            f"Multiple services could parse playlist {playlist!r}: "
            f"{', '.join(str(pl_id) for pl_id in id_matches)}.\n"
            "Please specify the full URL or URI."
        )
    if not id_matches:
        raise typer.BadParameter(
            f"No service could parse playlist {playlist!r}. "
            "Please specify a valid URL, URI, serial, or raw ID."
        )
    service, playlist_id = id_matches.pop()

    # Create live playlists from id
    if (library := service.library()) is None:
        raise ValueError(f"Service {service.name} does not support library operations.")
    service_playlist = library().get_playlist_or_raise(id=playlist_id)

    # Register the service playlist with the synced playlist and update on disk
    playlist_name = service_playlist.name
    sync.register(service_playlist)
    sync.sync()
    sync.save_to(__sync_dir() / f"{sync.id}.json")

    if json_output:
        typer.echo(
            json.dumps(
                {
                    "id": str(sync.id),
                    "name": sync.name,
                    "playlist": service_playlist.id.serial,
                    "tracks": len(sync.tracks),
                }
            )
        )
        return

    _echo_markup(
        f"Registered playlist [bold]{playlist_name}[/bold] "
        f"([cyan]{service_playlist.id.serial}[/cyan], "
        f"{len(service_playlist)} tracks) with synced playlist "
        f"[bold]{sync.name}[/bold] (ID: [cyan]{sync.id}[/cyan]).\n"
        f"  Next: [dim]plistsync sync show {sync.id}[/dim]"
    )


@sync_app.command(name="show")
def show(
    name_or_id: Annotated[
        str,
        typer.Argument(
            help="Name or ID of the synced playlist to show.",
            autocompletion=_autocomplete_name_or_id,
        ),
    ],
) -> None:
    """Show the track overview of a synced playlist.

    Lists every track of the synced playlist and its linked playlists, with one
    column per linked playlist (plus the synced playlist itself) indicating
    whether the track is present there.
    """
    sync = __find_synced_by_name_or_id(name_or_id)

    # list of associated plists
    plists = list(sync._linked_playlists.values())
    table = Table(
        title=f"Synced playlist: {sync.name} (ID: {sync.id})",
        caption=sync.description,
    )
    table.add_column("Title")
    table.add_column("Artist")
    for plist in plists:
        table.add_column(f"{plist.service} ({plist.id.serial})", justify="center")

    for track, associated in sync.track_associations():
        row: list[str | None] = [track.title, ",".join(track.artists)]
        for plist in plists:
            row.append("✓" if plist in associated else "✗")
        table.add_row(*row)

    Console(file=sys.stdout, highlight=False).print(table)
