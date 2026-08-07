"""Sync workflow subcommands.

Commands for creating named synced playlists, linking playlists across
services, inspecting track availability, diffing, and running
synchronisations.
"""

from __future__ import annotations

import typer

from plistsync.logger import log

sync_app = typer.Typer(
    name="sync",
    help="Manage and run playlist synchronisations.",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


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
) -> None:
    """Create a named synced playlist.

    A synced playlist links playlists from different services together so
    they can be compared and synchronised.
    """
    log.info("Creating synced playlist '%s' with description '%s'", name, description)
    raise NotImplementedError("Creating synced playlists is not yet implemented.")


@sync_app.command(name="list")
def list(
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
