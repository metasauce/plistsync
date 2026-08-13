"""Sync workflow subcommands.

Commands for creating named synced playlists, linking playlists across
services, inspecting track availability, diffing, and running
synchronisations.
"""

from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from platformdirs import user_config_dir
from rich.console import Console

from plistsync.logger import log
from plistsync.services.sync import SyncedPlaylist

if TYPE_CHECKING:
    from collections.abc import Iterable

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


@cache
def __iter_all() -> Iterable[SyncedPlaylist]:
    """Shell-complete the names and IDs of all synced playlists."""
    sync_dir = __sync_dir()

    for id_path in sync_dir.glob("*.json"):
        try:
            yield SyncedPlaylist.load_from(id_path)
        except Exception:
            log.debug("Skipping unreadable sync file '%s'.", id_path.name)
            continue


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
) -> Iterable[str]:
    """Shell-complete the names and IDs of all synced playlists."""
    for playlist in __iter_all():
        if incomplete and not (
            playlist.name.startswith(incomplete)
            or str(playlist.id).startswith(incomplete)
        ):
            continue
        yield playlist.name
        yield str(playlist.id)


@sync_app.command(name="remove")
def remove(
    name_or_id: str = typer.Argument(
        help="Name or ID of the synced playlist to remove.",
        autocompletion=_autocomplete_name_or_id,
    ),
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

    # Find plist
    plists = [
        p for p in __iter_all() if p.name == name_or_id or str(p.id) == name_or_id
    ]
    if len(plists) > 1:
        log.error(
            "Multiple synced playlists match '%s'. Please specify the ID instead.",
            name_or_id,
        )
        log.error(
            "Matching playlists: %s",
            ", ".join(f"{p.name} (ID: {p.id})" for p in plists),
        )
        raise typer.Exit(code=1)

    if len(plists) == 0:
        raise typer.BadParameter(
            f"No synced playlist found matching NAME_OR_ID:{name_or_id!r}."
        )

    plist = plists[0]

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


@sync_app.command(name="list")
def list_(
    json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output synced playlists in JSON format.",
    ),
) -> None:
    """List all registered synced playlists."""
    log.debug("Listing all synced playlists")
    raise NotImplementedError("Listing synced playlists is not yet implemented.")


@sync_app.command(name="update")
def update(
    name: str | None = typer.Option(
        None,
        "--name",
        help="Playlist name. Exactly one of --name / --id must be provided.",
    ),
    id: str | None = typer.Option(
        None,
        "--id",
        help="Playlist ID. Exactly one of --name / --id must be provided.",
    ),
) -> None:
    """Execute a synchronisation.

    Updates the synced playlist with the latest tracks from the linked playlists and
    pushes any changes to the respective linked services.
    """

    if name is None and id is None:
        raise typer.BadParameter("You must specify either --name or --id.")

    if name is not None and id is not None:
        raise typer.BadParameter(
            "Cannot use both --name and --id. Specify exactly one."
        )

    raise NotImplementedError("Updating synced playlists is not yet implemented.")
